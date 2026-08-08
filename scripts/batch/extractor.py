"""
Extractor: builds Anthropic Message Batches requests for Batch A (extraction).

Reads source-reader.md for epistemic rules, adds batch-specific constraints,
and produces one Request per source (with chunking for large transcripts).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from .config import BatchIngestConfig
from .models import SourceExtraction
from .scanner import prepare_transcript
from .state import BatchItem

VAULT_ROOT_DEFAULT = Path(__file__).parent.parent.parent
AGENTS_DIR = ".claude/agents"
SOURCE_READER_PATH = "source-reader.md"

BATCH_EXTRACTION_RULES = """
## BATCH EXTRACTION MODE

Return only information explicitly supported by the transcript.

Prioritize knowledge that remains useful outside the immediate conversation.

Ignore greetings, scheduling logistics, screen-sharing comments, small talk,
acknowledgements and repetitions unless they materially affect a decision,
requirement, risk or commitment.

Every substantive claim must contain a source locator (timestamp or line number).

Do not resolve entities against any external wiki.
Do not infer external facts.
Do not synthesize across sources.

factual_summary must be 180 words or fewer.

Claims to EXCLUDE:
- "Good morning / Hello / See you later"
- "Can you share your screen?"
- "Let's get started"
- "Shall we schedule a follow-up?"

Claims to INCLUDE:
- Decisions made ("We decided to migrate service X to Kubernetes")
- SLAs and constraints ("The maximum SLA was set to 24 hours")
- Responsibilities assigned ("Team Y will own the rollout")
- Dependencies ("The migration depends on security approval")
- Risks identified
- Requirements stated

Concepts to INCLUDE — only extract a concept if ALL of these hold:
- It has a domain-specific meaning (not just a common English word used in passing)
- A 1-sentence definition could be written from the transcript content alone
- It is a named mechanism, framework, methodology, or model with distinct properties
- Examples: causal inference, drift detection, synthetic controls, federated development,
  scenario simulation, unified predictive model, DSP, read-and-write modules

Concepts to EXCLUDE — do not extract:
- Generic quality adjectives used to describe other things: accuracy, granularity, quality,
  explainability, optimization, reconciliation, innovation, scalability
- Common technical nouns without domain-specific meaning in this transcript: data lake,
  business rule, sanity check, lever, departure, co-creation, action menu
- File or tool UI elements: core file, pivot table, spreadsheet column, SharePoint tab
- One-word terms that are properties of something else, not concepts in their own right:
  clustering, accuracy, granularity (unless the meeting defines them as a named methodology)
- Anything for which you cannot write a 1-sentence definition using only the transcript
"""


# ---------------------------------------------------------------------------
# Load source-reader prompt
# ---------------------------------------------------------------------------

def _load_source_reader(vault_root: Path) -> str:
    path = vault_root / AGENTS_DIR / SOURCE_READER_PATH
    if not path.exists():
        return "Extract factual information from the source. Do not interpret beyond what is stated."
    text = path.read_text(encoding="utf-8")
    # Strip YAML frontmatter
    if text.startswith("---"):
        parts = text.split("---", 2)
        if len(parts) >= 3:
            return parts[2].strip()
    return text.strip()


_LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "source": (
        "## Language\n\n"
        "Write all extracted text fields (factual_summary, claim texts, title, "
        "entity names, concept names, open question texts) in the same language "
        "as the source document. Do not translate content."
    ),
    "pt": (
        "## Language\n\n"
        "Write all extracted text fields in Portuguese (pt-BR). Do not translate."
    ),
    "en": (
        "## Language\n\n"
        "Write all extracted text fields in English."
    ),
}

_cached_source_reader: str | None = None


def get_system_prompt(vault_root: Path, wiki_language: str = "source") -> str:
    global _cached_source_reader
    if _cached_source_reader is None:
        _cached_source_reader = _load_source_reader(vault_root)
    lang_instruction = _LANGUAGE_INSTRUCTIONS.get(
        wiki_language, _LANGUAGE_INSTRUCTIONS["source"]
    )
    return _cached_source_reader + "\n\n" + BATCH_EXTRACTION_RULES + "\n\n" + lang_instruction


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def _estimate_tokens(text: str) -> int:
    """Very rough token estimate: ~4 chars per token."""
    return len(text) // 4


def chunk_transcript(
    text: str,
    target_tokens: int = 100_000,
    overlap_tokens: int = 1_500,
) -> list[str]:
    """Split transcript into overlapping chunks if needed."""
    if _estimate_tokens(text) <= target_tokens:
        return [text]

    chars_per_chunk = target_tokens * 4
    overlap_chars = overlap_tokens * 4
    chunks = []
    start = 0
    while start < len(text):
        end = start + chars_per_chunk
        chunk = text[start:end]
        chunks.append(chunk)
        start = end - overlap_chars
        if start >= len(text):
            break
    return chunks


def merge_source_extraction(parts: list[SourceExtraction]) -> SourceExtraction:
    """Merge multi-chunk extractions into one, deduplicating claims."""
    if len(parts) == 1:
        return parts[0]

    base = parts[0]
    seen_claim_texts: set[str] = {c.text.lower() for c in base.claims}
    seen_entities: dict[str, int] = {e.name.lower(): 0 for e in base.entities}
    seen_concepts: set[str] = {c.name.lower() for c in base.concepts}

    for part in parts[1:]:
        for claim in part.claims:
            norm = claim.text.lower()
            if norm not in seen_claim_texts:
                base.claims.append(claim)
                seen_claim_texts.add(norm)

        for entity in part.entities:
            norm = entity.name.lower()
            if norm not in seen_entities:
                base.entities.append(entity)
                seen_entities[norm] = len(base.entities) - 1
            else:
                # Merge aliases
                idx = seen_entities[norm]
                existing_aliases = set(a.lower() for a in base.entities[idx].aliases)
                for alias in entity.aliases:
                    if alias.lower() not in existing_aliases:
                        base.entities[idx].aliases.append(alias)

        for concept in part.concepts:
            norm = concept.name.lower()
            if norm not in seen_concepts:
                base.concepts.append(concept)
                seen_concepts.add(norm)

        for oq in part.open_questions:
            base.open_questions.append(oq)

    # Combine summaries (simplified: concatenate with separator)
    if len(parts) > 1:
        summaries = [p.factual_summary for p in parts if p.factual_summary]
        base.factual_summary = " ".join(summaries)[:900]  # keep under limit

    return base


# ---------------------------------------------------------------------------
# Build requests
# ---------------------------------------------------------------------------

def build_extraction_requests(
    items: list[BatchItem],
    cfg: BatchIngestConfig,
    vault_root: Path,
) -> list[dict[str, Any]]:
    """Build Anthropic batch request dicts for each item."""
    system_prompt = get_system_prompt(vault_root, cfg.wiki_language)
    schema = SourceExtraction.model_json_schema()
    requests = []

    for item in items:
        if not item.files:
            continue
        source_path = vault_root / item.files[0]
        if not source_path.exists():
            continue

        transcript = prepare_transcript(source_path)
        chunks = chunk_transcript(
            transcript,
            target_tokens=cfg.chunking.target_tokens,
            overlap_tokens=cfg.chunking.overlap_tokens,
        )

        for chunk_idx, chunk in enumerate(chunks):
            chunk_suffix = f"-chunk{chunk_idx:03d}" if len(chunks) > 1 else ""
            custom_id = f"{item.custom_id}{chunk_suffix}"

            system_block: dict[str, Any] = {
                "type": "text",
                "text": system_prompt,
            }
            if cfg.cache.enabled:
                system_block["cache_control"] = {"type": "ephemeral"}

            request = {
                "custom_id": custom_id,
                "params": {
                    "model": cfg.models.extraction,
                    "max_tokens": cfg.tokens.extraction_max_output,
                    "system": [system_block],
                    "messages": [
                        {
                            "role": "user",
                            "content": (
                                f"Extract structured knowledge from this transcript:\n\n"
                                f"Source path: {item.files[0]}\n"
                                f"Source key: {item.source_key}\n\n"
                                f"{chunk}"
                            ),
                        }
                    ],
                    "betas": ["output-128k-2025-02-19"],
                    "output_config": {
                        "format": {
                            "type": "json_schema",
                            "json_schema": {
                                "name": "SourceExtraction",
                                "schema": schema,
                            },
                        }
                    },
                },
                "_meta": {
                    "source_key": item.source_key,
                    "chunk_idx": chunk_idx,
                    "total_chunks": len(chunks),
                },
            }
            requests.append(request)

    return requests
