"""
Curator: runs Batch B (curation) via Anthropic Message Batches.

For each target group, produces a PageMutationPlan.
Contradiction detection is embedded here (one evaluation per target, not per source).
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, TYPE_CHECKING

from .config import BatchIngestConfig
from .grouper import TargetGroup
from .models import PageMutationPlan
from .state import BatchState

_CURATION_SYSTEM_PROMPT_BASE = """You are a knowledge curation agent for a structured wiki.

Your task: given an existing wiki page (if any) and a bundle of new evidence,
produce a PageMutationPlan that appends knowledge without destroying anything.

## Rules

APPEND ONLY. You may:
- CREATE a new page
- ADD claims with source citations
- ADD aliases
- ADD relations between pages
- ADD conflicts (do NOT silently resolve contradictions)
- SET status to "conflict" when contradictions are detected
- PROPOSE open questions
- PROPOSE decisions (do NOT create them automatically)

You may NOT:
- Delete claims or sections
- Replace existing content
- Rename files
- Remove sources
- Auto-promote status from draft to active

## Conflict detection

Compare new claims against existing page content AND against each other.
A conflict exists when two claims from different sources state contradictory
facts (e.g., different SLA values, different technology choices, different
responsibility assignments).

When a conflict is found:
1. Document BOTH positions
2. Cite BOTH sources
3. Set conflict_type appropriately

## Citation requirement

Every claim_to_add must include source_slug and source_claim_id.
Claims without citations are not allowed.

## For new pages

Provide:
- abstract: 1-2 factual sentences
- definition: concise explanation of the concept or entity
- title: canonical name
- aliases_to_add: alternative names found in evidence
"""

_CURATION_LANGUAGE_INSTRUCTIONS: dict[str, str] = {
    "source": (
        "## Language\n\n"
        "Write abstract, definition, claim texts, and all prose in the same "
        "language as the evidence claims provided. Do not translate to English."
    ),
    "pt": (
        "## Language\n\n"
        "Write abstract, definition, claim texts, and all prose in Portuguese (pt-BR)."
    ),
    "en": (
        "## Language\n\n"
        "Write abstract, definition, claim texts, and all prose in English."
    ),
}


def _build_curation_system_prompt(wiki_language: str = "source") -> str:
    lang = _CURATION_LANGUAGE_INSTRUCTIONS.get(
        wiki_language, _CURATION_LANGUAGE_INSTRUCTIONS["source"]
    )
    return _CURATION_SYSTEM_PROMPT_BASE + "\n" + lang


def build_curation_requests(
    groups: list[TargetGroup],
    cfg: BatchIngestConfig,
) -> list[dict[str, Any]]:
    """Build batch request dicts for Batch B."""
    schema = PageMutationPlan.model_json_schema()
    system_prompt = _build_curation_system_prompt(cfg.wiki_language)
    requests = []

    for group in groups:
        custom_id = f"cur_{group.page_type}_{group.slug}"[:64]
        # Sanitize
        import re
        custom_id = re.sub(r"[^a-zA-Z0-9_-]", "_", custom_id)[:64]

        if group.current_content:
            context = f"## Existing page content\n\n{group.current_content[:8000]}\n\n"
        else:
            context = "## This is a NEW page — no existing content.\n\n"

        evidence_text = "## New evidence bundle\n\n"
        for ev in group.evidence[:50]:  # cap per request
            evidence_text += (
                f"**[{ev.claim_id}]** (source: {ev.source_key}, kind: {ev.kind})\n"
                f"> {ev.text}\n"
                f"Locator: {json.dumps(ev.locator)}\n\n"
            )

        user_message = (
            f"Target: {group.page_type} page → `{group.slug}` (title: \"{group.title}\")\n"
            f"Sources contributing: {', '.join(group.source_keys)}\n\n"
            f"{context}"
            f"{evidence_text}"
            f"\nProduce a PageMutationPlan for this target page."
        )

        system_block: dict[str, Any] = {"type": "text", "text": system_prompt}
        if cfg.cache.enabled:
            system_block["cache_control"] = {"type": "ephemeral"}

        model = cfg.models.curation if group.current_content else cfg.models.curation_new

        requests.append({
            "custom_id": custom_id,
            "params": {
                "model": model,
                "max_tokens": cfg.tokens.curation_max_output,
                "system": [system_block],
                "messages": [{"role": "user", "content": user_message}],
                "output_config": {
                    "format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "PageMutationPlan",
                            "schema": schema,
                        },
                    }
                },
            },
            "_meta": {"slug": group.slug, "page_type": group.page_type,
                      "is_new": not bool(group.current_content)},
        })

    return requests


def run_curation_batch(
    groups: list[TargetGroup],
    state: BatchState,
    cfg: BatchIngestConfig,
    vault_root: Path,
) -> list[PageMutationPlan]:
    """
    Submit and collect curation batch. Returns list of PageMutationPlan.

    With provider: litellm → synchronous litellm calls.
    Without ANTHROPIC_API_KEY → offline mode (no API).
    """
    if cfg.provider == "litellm":
        from .litellm_sync import run_curation_sync
        return run_curation_sync(groups, state, cfg, vault_root)

    import anthropic

    has_auth = (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_MODEL")
    )
    if not has_auth:
        return _offline_curation(groups, vault_root)

    client = anthropic.Anthropic()
    requests = build_curation_requests(groups, cfg)
    if not requests:
        return []

    raw_requests = [{"custom_id": r["custom_id"], "params": r["params"]} for r in requests]
    curation_dir = state.batch_dir / "curation"
    curation_dir.mkdir(exist_ok=True)

    try:
        batch = client.beta.messages.batches.create(requests=raw_requests)
    except anthropic.NotFoundError:
        print("  Batch API not available — curating synchronously.")
        return _run_curation_sync_sdk(requests, client, cfg, curation_dir)

    state.provider_batches.setdefault("curation", []).append(batch.id)

    # Poll until ended
    import time
    while True:
        b = client.beta.messages.batches.retrieve(batch.id)
        if b.processing_status == "ended":
            break
        time.sleep(15)

    slug_map = {r["custom_id"]: r["_meta"] for r in requests}
    plans: list[PageMutationPlan] = []

    for result in client.beta.messages.batches.results(batch.id):
        if result.result.type == "succeeded":
            raw = result.result.message.content[0].text
            try:
                plan = PageMutationPlan.model_validate_json(raw)
                out = curation_dir / f"{plan.page_type}_{plan.slug}.json"
                out.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
                plans.append(plan)
            except Exception:
                pass

    return plans


def _run_curation_sync_sdk(
    requests: list[dict],
    client: Any,
    cfg: BatchIngestConfig,
    curation_dir: Path,
) -> list[PageMutationPlan]:
    """Synchronous curation via Anthropic SDK (fallback when batch API unavailable)."""
    from .progress import Progress

    schema = PageMutationPlan.model_json_schema()
    plans: list[PageMutationPlan] = []
    progress = Progress("Curation", total=len(requests))
    done = 0

    for req in requests:
        params = req["params"]
        sync_params = {k: v for k, v in params.items()
                      if k not in ("output_config", "betas")}
        sync_params["tools"] = [{
            "name": "structured_output",
            "description": "Return a PageMutationPlan",
            "input_schema": schema,
        }]
        sync_params["tool_choice"] = {"type": "tool", "name": "structured_output"}
        meta = req.get("_meta", {})
        label = f"{meta.get('page_type', '')} {meta.get('slug', req.get('custom_id', ''))}"

        try:
            response = client.messages.create(**sync_params)
            raw = None
            for block in response.content:
                if block.type == "tool_use":
                    raw = json.dumps(block.input)
                    break
            if raw is None:
                # Proxy returned plain text instead of tool_use block
                for block in response.content:
                    if block.type == "text" and block.text.strip():
                        text = block.text.strip()
                        # Strip markdown code fences if present
                        if text.startswith("```"):
                            text = text.split("```")[1]
                            if text.startswith("json"):
                                text = text[4:]
                        raw = text.strip()
                        break
            if raw is None:
                progress.fail(label, "no structured output in response")
                continue
            plan = PageMutationPlan.model_validate_json(raw)
            out = curation_dir / f"{plan.page_type}_{plan.slug}.json"
            out.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
            plans.append(plan)
            done += 1
            n_claims = len(plan.claims_to_add)
            detail = f"{n_claims} claims"
            if plan.conflicts:
                detail += f", {len(plan.conflicts)} conflicts"
            progress.step(done, label=label, detail=detail)
        except Exception as exc:
            progress.fail(label, str(exc)[:80])

    progress.done(f"{done} curated, {len(requests) - done} failed")
    return plans


def _offline_curation(
    groups: list[TargetGroup],
    vault_root: Path,
) -> list[PageMutationPlan]:
    """
    Produce minimal PageMutationPlans from pre-saved curation JSONs.
    Used when no API key is available (testing, offline).
    """
    plans = []
    for group in groups:
        # Try loading from disk (from a previous run)
        import pathlib
        for state_dir in (vault_root / "staging").iterdir() if (vault_root / "staging").exists() else []:
            curation_path = state_dir / "curation" / f"{group.page_type}_{group.slug}.json"
            if curation_path.exists():
                plan = PageMutationPlan.model_validate_json(
                    curation_path.read_text(encoding="utf-8")
                )
                plans.append(plan)
                break
        else:
            # Create a minimal plan with just the claims
            claim_additions = []
            for ev in group.evidence:
                from .models import ClaimAddition
                claim_additions.append(ClaimAddition(
                    text=ev.text,
                    source_slug=ev.source_key,
                    source_claim_id=ev.claim_id,
                ))
            action = "update" if group.current_content else "create"
            plans.append(PageMutationPlan(
                page_type=group.page_type,
                action=action,
                slug=group.slug,
                title=group.title,
                claims_to_add=claim_additions,
            ))
    return plans
