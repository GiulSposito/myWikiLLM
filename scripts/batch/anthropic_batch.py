"""
Anthropic Message Batches API wrapper.

Handles:
- Splitting logical batches into provider batches (≤ max_requests)
- Submit, status check, streaming collection
- Retry policy per spec §15
- Storing results to staging/<batch>/extraction/<source_key>.json
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .config import BatchIngestConfig
from .models import SourceExtraction
from .extractor import merge_source_extraction
from .state import BatchState


def _get_client():
    try:
        import anthropic
    except ImportError as exc:
        raise ImportError("anthropic SDK required: pip install anthropic") from exc

    # Let the SDK self-configure from environment variables:
    #   ANTHROPIC_API_KEY        → direct Anthropic (batch API supported)
    #   ANTHROPIC_AUTH_TOKEN +
    #   ANTHROPIC_BASE_URL       → proxy (e.g. litellm gateway); batch API may not be available
    has_auth = (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_MODEL")  # Claude Code proxy sets this
    )
    if not has_auth:
        raise EnvironmentError(
            "No Anthropic credentials found in environment.\n"
            "Set one of:\n"
            "  ANTHROPIC_API_KEY=sk-ant-...       (direct Anthropic)\n"
            "  ANTHROPIC_AUTH_TOKEN + ANTHROPIC_BASE_URL  (proxy / gateway)"
        )
    return anthropic.Anthropic()


# ---------------------------------------------------------------------------
# Submit
# ---------------------------------------------------------------------------

def submit_extraction_batch(
    requests: list[dict[str, Any]],
    state: BatchState,
    cfg: BatchIngestConfig,
) -> list[str]:
    """
    Submit requests as one or more provider batches. Returns list of provider batch IDs.

    If the endpoint returns 404 (proxy does not support batch API), falls back
    automatically to synchronous per-item calls using the same SDK client.
    """
    import anthropic

    client = _get_client()

    # Probe batch API support with first chunk; fall back to sync on 404.
    max_req = cfg.provider_batch.max_requests
    chunks = [requests[i:i + max_req] for i in range(0, len(requests), max_req)]
    provider_ids = []

    for chunk_idx, chunk in enumerate(chunks):
        raw_requests = [
            {"custom_id": r["custom_id"], "params": r["params"]}
            for r in chunk
        ]

        try:
            response = client.beta.messages.batches.create(requests=raw_requests)
            provider_ids.append(response.id)

            for r in chunk:
                meta = r.get("_meta", {})
                source_key = meta.get("source_key")
                if source_key and meta.get("chunk_idx", 0) == 0:
                    item = state.get_item(source_key)
                    if item:
                        item.status = "submitted"
                        item.provider_batch_id = response.id

        except anthropic.NotFoundError:
            # Proxy does not support Message Batches API → run remaining chunks synchronously.
            print("  Batch API not available on this endpoint — switching to sync mode.")
            remaining = chunks[chunk_idx:]
            _run_sync_fallback(
                [r for c in remaining for r in c],
                state, cfg, client,
            )
            return ["sync-fallback"]

    state.provider_batches.setdefault("extraction", []).extend(provider_ids)
    return provider_ids


def _run_sync_fallback(
    requests: list[dict[str, Any]],
    state: BatchState,
    cfg: BatchIngestConfig,
    client: Any,
) -> None:
    """Run extraction synchronously when batch API is unavailable."""
    from .progress import Progress
    from collections import defaultdict

    extraction_dir = state.batch_dir / "extraction"
    extraction_dir.mkdir(exist_ok=True)

    # Group by source_key to merge chunks
    by_source: dict[str, list[dict]] = defaultdict(list)
    for r in requests:
        meta = r.get("_meta", {})
        source_key = meta.get("source_key", r["custom_id"])
        by_source[source_key].append(r)

    progress = Progress("Extraction", total=len(by_source))
    done = 0

    for source_key, reqs in by_source.items():
        reqs_sorted = sorted(reqs, key=lambda r: r.get("_meta", {}).get("chunk_idx", 0))
        chunk_extractions = []
        failed = False

        for req in reqs_sorted:
            params = req["params"]
            # Strip batch-only fields the sync endpoint doesn't accept
            sync_params = {k: v for k, v in params.items()
                          if k not in ("output_config", "betas")}
            # Move structured output into tools for sync API
            output_cfg = params.get("output_config", {})
            json_schema = output_cfg.get("format", {}).get("json_schema", {})
            if json_schema:
                sync_params["tools"] = [{
                    "name": "structured_output",
                    "description": "Return structured data",
                    "input_schema": json_schema.get("schema", {}),
                }]
                sync_params["tool_choice"] = {"type": "tool", "name": "structured_output"}

            try:
                response = client.messages.create(**sync_params)
                # Extract tool use result
                raw = None
                for block in response.content:
                    if block.type == "tool_use":
                        import json as _json
                        raw = _json.dumps(block.input)
                        break
                if raw is None and response.content:
                    raw = response.content[0].text

                if raw:
                    chunk_extractions.append(raw)
            except Exception as exc:
                state.update_status(source_key, "failed_extraction", error=str(exc))
                progress.fail(source_key, str(exc)[:80])
                failed = True
                break

        if failed or not chunk_extractions:
            continue

        import json as _json
        try:
            extractions = [SourceExtraction(**_json.loads(r)) for r in chunk_extractions]
            merged = merge_source_extraction(extractions)
            for idx, claim in enumerate(merged.claims):
                claim._claim_id = f"{source_key}:c{idx:04d}"
            out_path = extraction_dir / f"{source_key}.json"
            out_path.write_text(merged.model_dump_json(indent=2), encoding="utf-8")
            state.update_status(source_key, "extracted")
            done += 1
            n_claims = len(merged.claims)
            progress.step(done, label=source_key, detail=f"{n_claims} claims")
        except Exception as exc:
            state.update_status(source_key, "failed_extraction", error=str(exc))
            progress.fail(source_key, str(exc)[:80])

    failed_count = len(by_source) - done
    progress.done(f"{done} extracted, {failed_count} failed")


# ---------------------------------------------------------------------------
# Status check
# ---------------------------------------------------------------------------

def check_batch_status(batch_id: str) -> dict:
    client = _get_client()
    batch = client.beta.messages.batches.retrieve(batch_id)
    return {
        "id": batch.id,
        "processing_status": batch.processing_status,
        "request_counts": {
            "processing": batch.request_counts.processing,
            "succeeded": batch.request_counts.succeeded,
            "errored": batch.request_counts.errored,
            "canceled": batch.request_counts.canceled,
            "expired": batch.request_counts.expired,
        },
    }


# ---------------------------------------------------------------------------
# Collect results
# ---------------------------------------------------------------------------

def collect_extraction_results(
    state: BatchState,
    vault_root: Path,
) -> tuple[int, int]:
    """Stream and save results. Returns (collected, failed)."""
    client = _get_client()
    extraction_dir = state.batch_dir / "extraction"
    extraction_dir.mkdir(exist_ok=True)

    # Build custom_id → source_key mapping
    cid_to_key: dict[str, str] = {
        item.custom_id: item.source_key
        for item in state.items
    }
    # Also handle chunk IDs: src_foo-chunk001 → src_foo (source_key)
    for item in state.items:
        for chunk_idx in range(100):
            chunk_cid = f"{item.custom_id}-chunk{chunk_idx:03d}"
            cid_to_key[chunk_cid] = item.source_key

    # Accumulate chunks per source_key
    chunk_accumulator: dict[str, list[dict]] = {}

    collected = 0
    failed = 0

    for batch_id in state.provider_batches.get("extraction", []):
        if batch_id == "sync-fallback":
            continue  # already written to disk by _run_sync_fallback
        for result in client.beta.messages.batches.results(batch_id):
            custom_id = result.custom_id
            source_key = cid_to_key.get(custom_id)
            if source_key is None:
                continue

            if result.result.type == "succeeded":
                raw = result.result.message.content[0].text
                try:
                    data = json.loads(raw)
                    chunk_accumulator.setdefault(source_key, []).append(data)
                except json.JSONDecodeError:
                    _save_error(state, source_key, "JSON decode error", raw[:500])
                    state.update_status(source_key, "failed_extraction",
                                        error="JSON decode error")
                    failed += 1

            elif result.result.type == "errored":
                error = result.result.error
                if error.type in ("server_error", "overloaded_error"):
                    state.update_status(source_key, "scanned",
                                        error=f"retry: {error.type}")
                else:
                    state.update_status(source_key, "failed_extraction",
                                        error=str(error))
                    failed += 1

    # Save accumulated chunks (merge multi-chunk sources)
    for source_key, chunks in chunk_accumulator.items():
        try:
            extractions = [SourceExtraction(**c) for c in chunks]
            merged = merge_source_extraction(extractions)

            # Assign deterministic claim IDs
            for idx, claim in enumerate(merged.claims):
                claim._claim_id = f"{source_key}:c{idx:04d}"

            out_path = extraction_dir / f"{source_key}.json"
            out_path.write_text(
                merged.model_dump_json(indent=2),
                encoding="utf-8",
            )
            state.update_status(source_key, "extracted")
            collected += 1
        except Exception as exc:
            _save_error(state, source_key, str(exc), str(chunks)[:500])
            state.update_status(source_key, "failed_extraction", error=str(exc))
            failed += 1

    return collected, failed


# ---------------------------------------------------------------------------
# Retry
# ---------------------------------------------------------------------------

def retry_failed_extraction(
    state: BatchState,
    cfg: BatchIngestConfig,
    vault_root: Path,
) -> list[str]:
    """Build and submit a retry batch for items with retry-eligible errors."""
    from .extractor import build_extraction_requests

    items_to_retry = [
        item for item in state.items
        if item.status == "scanned"
        and item.error
        and item.retry_count < cfg.provider_batch.max_retries
    ]
    if not items_to_retry:
        return []

    for item in items_to_retry:
        item.retry_count += 1
        item.error = None

    requests = build_extraction_requests(items_to_retry, cfg, vault_root)
    return submit_extraction_batch(requests, state, cfg)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _save_error(state: BatchState, source_key: str, error_type: str, detail: str) -> None:
    errors_dir = state.batch_dir / "errors"
    errors_dir.mkdir(exist_ok=True)
    error_path = errors_dir / f"{source_key}.json"
    error_path.write_text(
        json.dumps({"source_key": source_key, "error": error_type, "detail": detail},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
