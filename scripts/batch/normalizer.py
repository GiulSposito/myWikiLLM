"""
Normalizer: post-extraction deterministic cleanup.

Operations:
- Unicode normalization (NFC)
- Trim whitespace
- Case folding for comparison (not for display)
- Slugify for candidate lookup
- Entity-type validation against taxonomy
- Exact dedup of mentions within a source
- Alias lookup from manifests/aliases.yml

Does NOT modify the original claim text.
"""

from __future__ import annotations

import json
import unicodedata
import re
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise ImportError("pyyaml is required") from exc

from .models import SourceExtraction, EntityMention, ConceptMention
from .state import BatchState

VAULT_ROOT_DEFAULT = Path(__file__).parent.parent.parent

VALID_ENTITY_TYPES = {
    "company", "person", "product", "tool", "organization", "framework", "place"
}


# ---------------------------------------------------------------------------
# Text normalization utilities
# ---------------------------------------------------------------------------

def normalize_unicode(text: str) -> str:
    return unicodedata.normalize("NFC", text)


def fold_case(text: str) -> str:
    return normalize_unicode(text).strip().lower()


def slugify(text: str) -> str:
    text = fold_case(text)
    # Transliterate accented characters: NFD decomposes them, then we strip
    # combining marks (category Mn) so "ã" → "a", "é" → "e", etc.
    text = unicodedata.normalize("NFD", text)
    text = "".join(c for c in text if unicodedata.category(c) != "Mn")
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# ---------------------------------------------------------------------------
# Alias index
# ---------------------------------------------------------------------------

def load_alias_index(vault_root: Path) -> dict[str, str]:
    """Return {normalized_name: canonical_slug} from aliases.yml."""
    aliases_path = vault_root / "manifests" / "aliases.yml"
    if not aliases_path.exists():
        return {}

    raw = yaml.safe_load(aliases_path.read_text(encoding="utf-8")) or {}
    index: dict[str, str] = {}

    for slug, alias_list in raw.items():
        if not isinstance(alias_list, list):
            continue
        # The slug itself resolves to itself
        index[fold_case(str(slug))] = str(slug)
        index[slugify(str(slug))] = str(slug)
        for alias in alias_list:
            index[fold_case(str(alias))] = str(slug)
            index[slugify(str(alias))] = str(slug)

    return index


# ---------------------------------------------------------------------------
# Per-source normalization
# ---------------------------------------------------------------------------

def normalize_extraction(
    extraction: SourceExtraction,
    alias_index: dict[str, str],
) -> SourceExtraction:
    """Return normalized copy of extraction (in-place mutation for efficiency)."""
    # Normalize entity mentions
    seen_entities: dict[str, int] = {}
    deduped_entities: list[EntityMention] = []

    for entity in extraction.entities:
        name_norm = fold_case(entity.name)

        # Validate entity type
        if entity.entity_type not in VALID_ENTITY_TYPES:
            continue

        # Exact dedup
        if name_norm in seen_entities:
            # Merge aliases into existing
            idx = seen_entities[name_norm]
            existing_aliases = set(fold_case(a) for a in deduped_entities[idx].aliases)
            for alias in entity.aliases:
                if fold_case(alias) not in existing_aliases:
                    deduped_entities[idx].aliases.append(alias)
            continue

        # Alias lookup
        resolved_slug = alias_index.get(name_norm) or alias_index.get(slugify(entity.name))
        if resolved_slug:
            entity = EntityMention(
                name=entity.name,
                entity_type=entity.entity_type,
                aliases=entity.aliases + [resolved_slug],
            )

        seen_entities[name_norm] = len(deduped_entities)
        deduped_entities.append(entity)

    extraction.entities = deduped_entities

    # Normalize concept mentions
    seen_concepts: dict[str, int] = {}
    deduped_concepts: list[ConceptMention] = []

    for concept in extraction.concepts:
        name_norm = fold_case(concept.name)

        if name_norm in seen_concepts:
            idx = seen_concepts[name_norm]
            existing_aliases = set(fold_case(a) for a in deduped_concepts[idx].aliases)
            for alias in concept.aliases:
                if fold_case(alias) not in existing_aliases:
                    deduped_concepts[idx].aliases.append(alias)
            continue

        resolved_slug = alias_index.get(name_norm) or alias_index.get(slugify(concept.name))
        if resolved_slug:
            concept = ConceptMention(
                name=concept.name,
                aliases=concept.aliases + [resolved_slug],
            )

        seen_concepts[name_norm] = len(deduped_concepts)
        deduped_concepts.append(concept)

    extraction.concepts = deduped_concepts

    return extraction


# ---------------------------------------------------------------------------
# Batch normalization
# ---------------------------------------------------------------------------

def normalize_batch(state: BatchState, vault_root: Path) -> int:
    """Normalize all extracted items. Returns count normalized."""
    from .progress import Progress

    alias_index = load_alias_index(vault_root)
    extraction_dir = state.batch_dir / "extraction"
    normalized_dir = state.batch_dir / "normalized"
    normalized_dir.mkdir(exist_ok=True)

    items = state.items_by_status("extracted")
    progress = Progress("Normalize", total=len(items))
    count = 0

    for item in items:
        src_path = extraction_dir / f"{item.source_key}.json"
        if not src_path.exists():
            continue

        extraction = SourceExtraction.model_validate_json(
            src_path.read_text(encoding="utf-8")
        )
        normalized = normalize_extraction(extraction, alias_index)

        out_path = normalized_dir / f"{item.source_key}.json"
        out_path.write_text(normalized.model_dump_json(indent=2), encoding="utf-8")
        state.update_status(item.source_key, "normalized")
        count += 1
        n_entities = len(normalized.entities)
        n_concepts = len(normalized.concepts)
        progress.step(count, label=item.source_key,
                      detail=f"{n_entities} entities, {n_concepts} concepts")

    progress.done(f"{count} items")
    return count
