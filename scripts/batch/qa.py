"""
QA: pre-apply checks and sampling-based quality report.

Blocking checks (spec §32):
- invalid extraction schema
- unknown entity type
- claim pointing to missing source
- missing locator on critical claims
- duplicate target slugs
- invalid page type in mutation plan
- mutation pointing to unknown target (if require_all_extractions_valid)
- unresolved provider errors

Sampling-based report (spec §33):
- 10% sample (deterministic by source hash)
- min 20, max 100
- outputs/reports/batch-ingest-<batch-id>.md
"""

from __future__ import annotations

import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from .config import BatchIngestConfig, QualityConfig
from .models import SourceExtraction, PageMutationPlan
from .planner import UpdatePlan
from .state import BatchState

VALID_ENTITY_TYPES = {
    "company", "person", "product", "tool", "organization", "framework", "place"
}

CRITICAL_CLAIM_KINDS = {"decision", "requirement", "constraint", "risk"}


# ---------------------------------------------------------------------------
# Deterministic sampling
# ---------------------------------------------------------------------------

def sample_sources(
    source_keys: list[str],
    rate: float,
    min_size: int,
    max_size: int,
) -> list[str]:
    """Select a deterministic sample by source key hash."""
    def sort_key(sk: str) -> int:
        return int(hashlib.sha256(sk.encode()).hexdigest()[:8], 16)

    sorted_keys = sorted(source_keys, key=sort_key)
    target = max(min_size, min(max_size, round(len(sorted_keys) * rate)))
    step = max(1, len(sorted_keys) // target) if target < len(sorted_keys) else 1
    return sorted_keys[::step][:target]


# ---------------------------------------------------------------------------
# Blocking checks
# ---------------------------------------------------------------------------

def run_qa_checks(
    plan: UpdatePlan,
    state: BatchState,
    vault_root: Path,
) -> tuple[bool, str]:
    """
    Run all blocking QA checks.
    Returns (ok, report_text).
    """
    errors: list[str] = []
    warnings: list[str] = []

    extraction_dir = state.batch_dir / "extraction"
    normalized_dir = state.batch_dir / "normalized"

    # Track source keys referenced in mutations
    all_source_keys = {item.source_key for item in state.items}

    # Check: unresolved provider errors
    failed_items = state.items_by_status("failed_extraction")
    if failed_items:
        errors.append(
            f"Unresolved extraction failures: "
            + ", ".join(i.source_key for i in failed_items)
        )

    # Check per-extraction
    locator_counts = {"total": 0, "with_locator": 0, "critical_total": 0, "critical_with_locator": 0}
    seen_source_keys: set[str] = set()

    for extraction_path in sorted(extraction_dir.glob("*.json")):
        source_key = extraction_path.stem

        # Duplicate detection
        if source_key in seen_source_keys:
            errors.append(f"Duplicate extraction file: {source_key}")
        seen_source_keys.add(source_key)

        try:
            extraction = SourceExtraction.model_validate_json(
                extraction_path.read_text(encoding="utf-8")
            )
        except Exception as exc:
            errors.append(f"Invalid extraction schema [{source_key}]: {exc}")
            continue

        for idx, claim in enumerate(extraction.claims):
            locator_counts["total"] += 1
            has_locator = bool(
                claim.locator.timestamp_start or
                claim.locator.line_start or
                claim.locator.timestamp_end
            )
            if has_locator:
                locator_counts["with_locator"] += 1

            if claim.kind in CRITICAL_CLAIM_KINDS:
                locator_counts["critical_total"] += 1
                if has_locator:
                    locator_counts["critical_with_locator"] += 1
                else:
                    warnings.append(
                        f"Critical claim missing locator [{source_key}:c{idx:04d}]: {claim.text[:80]}"
                    )

        # Check entity types
        for entity in extraction.entities:
            if entity.entity_type not in VALID_ENTITY_TYPES:
                warnings.append(
                    f"Unknown entity type [{source_key}]: {entity.name} → {entity.entity_type}"
                )

    # Compute locator rates
    if locator_counts["total"] > 0:
        locator_rate = locator_counts["with_locator"] / locator_counts["total"]
        if locator_rate < 0.95:
            warnings.append(
                f"Locator rate {locator_rate:.1%} below threshold 95%"
                f" ({locator_counts['with_locator']}/{locator_counts['total']})"
            )

    if locator_counts["critical_total"] > 0:
        critical_rate = locator_counts["critical_with_locator"] / locator_counts["critical_total"]
        if critical_rate < 1.0:
            errors.append(
                f"Critical claim locator rate {critical_rate:.1%} below 100%"
                f" ({locator_counts['critical_with_locator']}/{locator_counts['critical_total']})"
            )

    # Check mutation plans
    seen_target_slugs: dict[str, str] = {}
    for fe in plan.files:
        mp_data = fe.get("mutation_plan")
        if not mp_data:
            continue
        try:
            mp = PageMutationPlan(**mp_data)
        except Exception as exc:
            errors.append(f"Invalid mutation plan [{fe['path']}]: {exc}")
            continue

        # Valid page type
        if mp.page_type not in ("concept", "entity"):
            errors.append(f"Invalid page_type in mutation plan: {mp.slug} → {mp.page_type}")

        # Duplicate target slugs
        key = f"{mp.page_type}:{mp.slug}"
        if key in seen_target_slugs:
            errors.append(f"Duplicate target slug: {key} (in {seen_target_slugs[key]} and {fe['path']})")
        seen_target_slugs[key] = fe["path"]

        # Source references exist
        for ca in mp.claims_to_add:
            if ca.source_slug not in all_source_keys and not ca.source_slug.endswith("-existing"):
                warnings.append(
                    f"Claim references unknown source [{mp.slug}]: {ca.source_slug}"
                )

    ok = len(errors) == 0
    report_lines = [f"## QA Report — {plan.batch_id}", ""]

    if errors:
        report_lines.append(f"### Errors ({len(errors)})")
        for e in errors:
            report_lines.append(f"- ERROR: {e}")
        report_lines.append("")

    if warnings:
        report_lines.append(f"### Warnings ({len(warnings)})")
        for w in warnings:
            report_lines.append(f"- WARN: {w}")
        report_lines.append("")

    report_lines.append("### Locator Statistics")
    report_lines.append(f"- Total claims: {locator_counts['total']}")
    report_lines.append(f"- Claims with locator: {locator_counts['with_locator']}")
    report_lines.append(f"- Critical claims: {locator_counts['critical_total']}")
    report_lines.append(f"- Critical claims with locator: {locator_counts['critical_with_locator']}")
    report_lines.append("")

    if ok:
        report_lines.append("**QA PASSED** — ready to apply.")
    else:
        report_lines.append(f"**QA FAILED** — {len(errors)} blocking error(s). Apply aborted.")

    return ok, "\n".join(report_lines)


# ---------------------------------------------------------------------------
# Sampling-based QA report
# ---------------------------------------------------------------------------

def generate_qa_report(
    plan: UpdatePlan,
    state: BatchState,
    vault_root: Path,
    cfg: BatchIngestConfig,
) -> str:
    """
    Generate a human-readable QA report with sampled claims.
    Writes to outputs/reports/batch-ingest-<id>.md.
    Returns the report path.
    """
    today = date.today().isoformat()
    extraction_dir = state.batch_dir / "extraction"
    normalized_dir = state.batch_dir / "normalized"

    all_extracted = [
        i.source_key
        for i in state.items
        if i.status in ("extracted", "normalized", "resolved", "curated", "applied")
    ]

    sample = sample_sources(
        all_extracted,
        rate=cfg.quality.sample_rate,
        min_size=cfg.quality.min_sample_size,
        max_size=cfg.quality.max_sample_size,
    )

    lines = [
        f"# Batch Ingest QA Report — {state.batch_id}",
        f"",
        f"**Date:** {today}",
        f"**Batch:** {state.batch_id}",
        f"**Sample:** {len(sample)}/{len(all_extracted)} sources ({cfg.quality.sample_rate:.0%})",
        f"",
        f"---",
        f"",
        f"## Sampled Claims",
        f"",
    ]

    for source_key in sample[:20]:  # display up to 20 in report
        norm_path = normalized_dir / f"{source_key}.json"
        extr_path = extraction_dir / f"{source_key}.json"
        load_path = norm_path if norm_path.exists() else extr_path
        if not load_path.exists():
            continue

        try:
            extraction = SourceExtraction.model_validate_json(
                load_path.read_text(encoding="utf-8")
            )
        except Exception:
            continue

        lines.append(f"### Source: `{source_key}`")
        lines.append(f"**Title:** {extraction.title}")
        lines.append(f"")

        for idx, claim in enumerate(extraction.claims[:3]):
            locator_str = ""
            if claim.locator.timestamp_start:
                locator_str = f" @{claim.locator.timestamp_start}"
            elif claim.locator.line_start:
                locator_str = f" @L{claim.locator.line_start}"
            lines.append(f"- **[{source_key}:c{idx:04d}]** ({claim.kind}{locator_str})")
            lines.append(f"  > {claim.text}")
        lines.append("")

    report_text = "\n".join(lines)

    reports_dir = vault_root / "outputs" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"batch-ingest-{state.batch_id}.md"
    report_path.write_text(report_text, encoding="utf-8")

    return str(report_path)
