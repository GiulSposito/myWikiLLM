"""
Planner: merge all PageMutationPlan items into a single update-plan.json.

Also records:
- optimistic-lock baselines (SHA256 per target page at plan time)
- conflict list
- decision proposals
- deferred items
- source page creation list
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import PageMutationPlan, SourceExtraction
from .state import BatchState


@dataclass
class UpdatePlan:
    batch_id: str
    sources: dict = field(default_factory=lambda: {"create": 0, "update": 0})
    concepts: dict = field(default_factory=lambda: {"create": 0, "update": 0, "defer": 0})
    entities: dict = field(default_factory=lambda: {"create": 0, "update": 0, "defer": 0})
    conflicts: list[str] = field(default_factory=list)
    decision_proposals: list[str] = field(default_factory=list)
    promotion_candidates: list[str] = field(default_factory=list)
    files: list[dict] = field(default_factory=list)  # {path, action, baseline_sha256}

    def to_dict(self) -> dict:
        return {
            "batch_id": self.batch_id,
            "sources": self.sources,
            "concepts": self.concepts,
            "entities": self.entities,
            "conflicts": self.conflicts,
            "decision_proposals": self.decision_proposals,
            "promotion_candidates": self.promotion_candidates,
            "files": self.files,
        }


def _sha256_path(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def build_update_plan(
    state: BatchState,
    vault_root: Path,
) -> UpdatePlan:
    """
    Load all PageMutationPlan JSONs from staging/curation/ and
    merge into a single UpdatePlan. Also includes source page creations.
    """
    curation_dir = state.batch_dir / "curation"
    plan = UpdatePlan(batch_id=state.batch_id)

    mutation_plans: list[PageMutationPlan] = []

    if curation_dir.exists():
        for json_path in sorted(curation_dir.glob("*.json")):
            try:
                mp = PageMutationPlan.model_validate_json(
                    json_path.read_text(encoding="utf-8")
                )
                mutation_plans.append(mp)
            except Exception:
                pass

    # Tally mutation plans
    for mp in mutation_plans:
        bucket = plan.concepts if mp.page_type == "concept" else plan.entities

        if mp.action == "create":
            bucket["create"] += 1
        elif mp.action == "update":
            bucket["update"] += 1
        elif mp.action == "defer":
            bucket["defer"] += 1
            continue

        # Compute target file path
        subdir = "concepts" if mp.page_type == "concept" else "entities"
        target_path = vault_root / "wiki" / subdir / f"{mp.slug}.md"
        action = "create" if mp.action == "create" else "update"
        baseline = _sha256_path(target_path)

        plan.files.append({
            "path": str(target_path.relative_to(vault_root)),
            "action": action,
            "baseline_sha256": baseline,
            "mutation_plan": mp.model_dump(),
        })

        # Collect conflicts
        for conflict in mp.conflicts:
            plan.conflicts.append(f"{mp.slug}:{conflict.conflict_type}")

        # Collect decision proposals
        for dp in mp.proposed_decisions:
            plan.decision_proposals.append(f"{mp.slug}: {dp}")

    # Source pages are one per non-duplicate item
    non_dup_items = [i for i in state.items if i.status not in ("skipped_duplicate", "changed-source")]
    for item in non_dup_items:
        src_path = vault_root / "wiki" / "sources" / f"{item.source_key}.md"
        action = "update" if src_path.exists() else "create"
        plan.sources[action if action == "update" else "create"] += 1
        plan.files.append({
            "path": str(src_path.relative_to(vault_root)),
            "action": action,
            "baseline_sha256": _sha256_path(src_path),
            "source_key": item.source_key,
        })

    # Promotion candidates: pages with 2+ sources
    wiki_dir = vault_root / "wiki"
    for subdir_name in ("concepts", "entities"):
        subdir = wiki_dir / subdir_name
        if not subdir.exists():
            continue
        for page_path in subdir.glob("*.md"):
            try:
                import yaml
                text = page_path.read_text(encoding="utf-8")
                if not text.startswith("---"):
                    continue
                parts = text.split("---", 2)
                if len(parts) < 3:
                    continue
                fm = yaml.safe_load(parts[1]) or {}
                if (
                    fm.get("status") == "draft"
                    and len(fm.get("sources") or []) >= 2
                ):
                    plan.promotion_candidates.append(page_path.stem)
            except Exception:
                pass

    # Save update plan
    plan_path = state.batch_dir / "update-plan.json"
    plan_path.write_text(
        json.dumps(plan.to_dict(), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    return plan


def print_plan_summary(plan: UpdatePlan) -> None:
    """Print a human-readable dry-run summary (spec §37)."""
    print(f"Batch: {plan.batch_id}")
    print()
    total_sources = plan.sources["create"] + plan.sources.get("update", 0)
    print(f"{total_sources} sources will be created/updated")
    print()
    print(f"{plan.concepts['create'] + plan.concepts['update']} concepts:")
    print(f"  + {plan.concepts['create']} create")
    print(f"  ~ {plan.concepts['update']} update")
    if plan.concepts["defer"]:
        print(f"  ? {plan.concepts['defer']} deferred")
    print()
    print(f"{plan.entities['create'] + plan.entities['update']} entities:")
    print(f"  + {plan.entities['create']} create")
    print(f"  ~ {plan.entities['update']} update")
    if plan.entities["defer"]:
        print(f"  ? {plan.entities['defer']} deferred")
    print()
    if plan.conflicts:
        print(f"{len(plan.conflicts)} pages will have conflicts detected:")
        for c in plan.conflicts:
            print(f"  ! {c}")
        print()
    if plan.decision_proposals:
        print(f"{len(plan.decision_proposals)} decision proposals:")
        for d in plan.decision_proposals:
            print(f"  → {d}")
        print()
    create_count = sum(1 for f in plan.files if f["action"] == "create")
    update_count = sum(1 for f in plan.files if f["action"] == "update")
    print(f"Estimated files:")
    print(f"  create: {create_count}")
    print(f"  update: {update_count}")
