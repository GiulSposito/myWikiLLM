"""
LiteLLM synchronous adapter for batch ingest pipeline.

Used when `provider: litellm` is set in manifests/batch-ingest.yml.

NOTE: The Anthropic Message Batches API is NOT supported by litellm.
With this adapter, extraction runs as N sequential synchronous calls
(no async, no 50% batch discount). Use `provider: anthropic` for
production workloads.

litellm resolves model names automatically:
  claude-haiku-4-5-20251001  → passed through to Anthropic
  gpt-4o-mini                → routes to OpenAI
  gemini/gemini-1.5-flash    → routes to Google AI
etc.
"""

from __future__ import annotations

import json
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

from .config import BatchIngestConfig
from .models import PageMutationPlan, SourceExtraction
from .extractor import (
    build_extraction_requests,
    merge_source_extraction,
    get_system_prompt,
)
from .grouper import TargetGroup
from .state import BatchItem, BatchState


def _litellm_call(
    model: str,
    system: str,
    user: str,
    max_tokens: int,
    json_schema: dict | None = None,
) -> str:
    """Single synchronous litellm call. Returns the text of the first content block."""
    try:
        import litellm
    except ImportError as exc:
        raise ImportError(
            "litellm is required for provider: litellm. "
            "Install with: pip install 'mywikillm[litellm]' or pip install litellm"
        ) from exc

    messages = [
        {"role": "system", "content": system},
        {"role": "user", "content": user},
    ]

    kwargs: dict[str, Any] = {
        "model": model,
        "messages": messages,
        "max_tokens": max_tokens,
    }

    if json_schema:
        kwargs["response_format"] = {
            "type": "json_schema",
            "json_schema": {
                "name": json_schema.get("title", "response"),
                "schema": json_schema,
                "strict": True,
            },
        }

    response = litellm.completion(**kwargs)
    return response.choices[0].message.content or ""


def run_extraction_sync(
    items: list[BatchItem],
    state: BatchState,
    cfg: BatchIngestConfig,
    vault_root: Path,
) -> tuple[int, int]:
    """
    Run extraction synchronously via litellm (one call per item).
    Returns (collected, failed).
    """
    from .extractor import prepare_transcript, chunk_transcript, BATCH_EXTRACTION_RULES
    from .scanner import prepare_transcript as scan_prepare
    from .progress import Progress

    system_prompt = get_system_prompt(vault_root)
    schema = SourceExtraction.model_json_schema()
    extraction_dir = state.batch_dir / "extraction"
    extraction_dir.mkdir(exist_ok=True)

    collected = 0
    failed = 0
    progress = Progress("Extraction", total=len(items))

    def _extract_one(item: BatchItem) -> tuple[str, str | None]:
        """Returns (source_key, error_or_None). Writes output to disk on success."""
        if not item.files:
            return item.source_key, "no files"
        source_path = vault_root / item.files[0]
        if not source_path.exists():
            return item.source_key, "source file not found"
        try:
            transcript = scan_prepare(source_path)
            chunks = chunk_transcript(
                transcript,
                target_tokens=cfg.chunking.target_tokens,
                overlap_tokens=cfg.chunking.overlap_tokens,
            )
            chunk_extractions: list[SourceExtraction] = []
            for chunk in chunks:
                user_msg = (
                    f"Extract structured knowledge from this transcript:\n\n"
                    f"Source path: {item.files[0]}\n"
                    f"Source key: {item.source_key}\n\n"
                    f"{chunk}"
                )
                raw = _litellm_call(
                    model=cfg.models.extraction,
                    system=system_prompt,
                    user=user_msg,
                    max_tokens=cfg.tokens.extraction_max_output,
                    json_schema=schema,
                )
                chunk_extractions.append(SourceExtraction.model_validate_json(raw))

            merged = merge_source_extraction(chunk_extractions)
            for idx, claim in enumerate(merged.claims):
                claim._claim_id = f"{item.source_key}:c{idx:04d}"

            out_path = extraction_dir / f"{item.source_key}.json"
            out_path.write_text(merged.model_dump_json(indent=2), encoding="utf-8")
            return item.source_key, None
        except Exception as exc:
            errors_dir = state.batch_dir / "errors"
            errors_dir.mkdir(exist_ok=True)
            (errors_dir / f"{item.source_key}.json").write_text(
                json.dumps({"source_key": item.source_key, "error": str(exc)},
                           ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return item.source_key, str(exc)

    workers = min(4, len(items)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_extract_one, item): item for item in items}
        for future in as_completed(futures):
            item = futures[future]
            source_key, error = future.result()
            if error:
                state.update_status(source_key, "failed_extraction", error=error)
                failed += 1
                progress.fail(source_key, error[:80])
            else:
                state.update_status(source_key, "extracted")
                item.provider_batch_id = "litellm-sync"
                collected += 1
                progress.step(collected + failed, label=source_key)

    progress.done(f"{collected} extracted, {failed} failed")
    return collected, failed


def run_resolution_sync(
    mention_name: str,
    mention_kind: str,
    candidates: list[dict],
    evidence_texts: list[str],
    cfg: BatchIngestConfig,
) -> dict:
    """Resolve an ambiguous mention via litellm. Returns ResolutionDecision dict."""
    from .resolver import RESOLUTION_SYSTEM_PROMPT
    from .models import ResolutionDecision

    schema = ResolutionDecision.model_json_schema()
    payload = {
        "mention": {"kind": mention_kind, "name": mention_name},
        "candidates": [
            {
                "slug": c["slug"],
                "title": c["title"],
                "aliases": c.get("aliases", []),
                "abstract": c.get("abstract", ""),
            }
            for c in candidates[:5]
        ],
        "evidence": evidence_texts[:3],
    }

    try:
        raw = _litellm_call(
            model=cfg.models.resolution,
            system=RESOLUTION_SYSTEM_PROMPT,
            user=json.dumps(payload, ensure_ascii=False),
            max_tokens=cfg.tokens.resolution_max_output,
            json_schema=schema,
        )
        data = json.loads(raw)
        decision = ResolutionDecision(**data)
        return decision.model_dump()
    except Exception:
        return {"action": "defer", "confidence": "low"}


def run_curation_sync(
    groups: list[TargetGroup],
    state: BatchState,
    cfg: BatchIngestConfig,
    vault_root: Path,
) -> list[PageMutationPlan]:
    """Run curation synchronously via litellm. Returns list of PageMutationPlan."""
    from .curator import _build_curation_system_prompt, build_curation_requests

    schema = PageMutationPlan.model_json_schema()
    requests = build_curation_requests(groups, cfg)
    curation_dir = state.batch_dir / "curation"
    curation_dir.mkdir(exist_ok=True)
    plans: list[PageMutationPlan] = []

    def _curate_one(req: dict) -> PageMutationPlan | None:
        params = req["params"]
        try:
            raw = _litellm_call(
                model=params["model"],
                system=params["system"][0]["text"],
                user=params["messages"][0]["content"],
                max_tokens=cfg.tokens.curation_max_output,
                json_schema=schema,
            )
            plan = PageMutationPlan.model_validate_json(raw)
            out = curation_dir / f"{plan.page_type}_{plan.slug}.json"
            out.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
            return plan
        except Exception:
            return None

    workers = min(4, len(requests)) or 1
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for plan in pool.map(_curate_one, requests):
            if plan is not None:
                plans.append(plan)

    return plans
