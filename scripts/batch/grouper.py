"""
Grouper: aggregate resolved evidence by target wiki page.

Produces groups keyed by (page_type, slug) where page_type ∈ {concept, entity}.
Each group contains:
  - the target slug
  - the page_type
  - the current page content (if the page exists)
  - all claims from all sources that reference this target
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .models import SourceExtraction
from .state import BatchState


@dataclass
class EvidenceItem:
    claim_id: str
    source_key: str
    source_path: str
    text: str
    kind: str
    locator: dict


@dataclass
class TargetGroup:
    page_type: str  # "concept" | "entity"
    slug: str
    title: str
    current_content: str | None
    evidence: list[EvidenceItem] = field(default_factory=list)
    source_keys: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "page_type": self.page_type,
            "slug": self.slug,
            "title": self.title,
            "current_content": self.current_content,
            "source_keys": self.source_keys,
            "evidence": [
                {
                    "claim_id": e.claim_id,
                    "source_key": e.source_key,
                    "source_path": e.source_path,
                    "text": e.text,
                    "kind": e.kind,
                    "locator": e.locator,
                }
                for e in self.evidence
            ],
        }


def _read_wiki_page(vault_root: Path, page_type: str, slug: str) -> str | None:
    subdir = "concepts" if page_type == "concept" else "entities"
    path = vault_root / "wiki" / subdir / f"{slug}.md"
    if path.exists():
        return path.read_text(encoding="utf-8")
    return None


def group_evidence(
    state: BatchState,
    vault_root: Path,
) -> list[TargetGroup]:
    """
    Read all resolution outputs and group evidence by target page.
    Also creates groups for new pages (action == 'new').
    """
    normalized_dir = state.batch_dir / "normalized"
    resolution_dir = state.batch_dir / "resolution"
    grouped_dir = state.batch_dir / "grouped"
    grouped_dir.mkdir(exist_ok=True)

    groups: dict[tuple[str, str], TargetGroup] = {}

    for item in state.items_by_status("resolved"):
        res_path = resolution_dir / f"{item.source_key}.json"
        norm_path = normalized_dir / f"{item.source_key}.json"

        if not res_path.exists() or not norm_path.exists():
            continue

        resolution_map: dict[str, dict] = json.loads(
            res_path.read_text(encoding="utf-8")
        )
        extraction = SourceExtraction.model_validate_json(
            norm_path.read_text(encoding="utf-8")
        )

        source_path = item.files[0] if item.files else ""

        # Build name → target mapping for claim routing
        name_to_target: dict[str, tuple[str, str, str]] = {}  # norm_name → (type, slug, title)

        for mention in extraction.entities:
            from .normalizer import fold_case
            norm = fold_case(mention.name)
            decision = resolution_map.get(norm)
            if decision and decision["action"] in ("existing", "new"):
                target_slug = decision.get("target_slug") or decision.get("suggested_slug")
                if target_slug:
                    name_to_target[norm] = ("entity", target_slug, mention.name)

        for mention in extraction.concepts:
            from .normalizer import fold_case
            norm = fold_case(mention.name)
            decision = resolution_map.get(norm)
            if decision and decision["action"] in ("existing", "new"):
                target_slug = decision.get("target_slug") or decision.get("suggested_slug")
                if target_slug:
                    name_to_target[norm] = ("concept", target_slug, mention.name)

        # Route claims to target groups
        for idx, claim in enumerate(extraction.claims):
            claim_id = f"{item.source_key}:c{idx:04d}"

            # Find which targets this claim references
            matched_targets: set[tuple[str, str]] = set()
            claim_text_lower = claim.text.lower()

            for norm_name, (page_type, slug, title) in name_to_target.items():
                # Check if the mention name appears in the claim text
                if norm_name in claim_text_lower or any(
                    t in claim_text_lower for t in norm_name.split()
                    if len(t) > 3
                ):
                    matched_targets.add((page_type, slug))
                    key = (page_type, slug)
                    if key not in groups:
                        current = _read_wiki_page(vault_root, page_type, slug)
                        groups[key] = TargetGroup(
                            page_type=page_type,
                            slug=slug,
                            title=title,
                            current_content=current,
                        )
                    if item.source_key not in groups[key].source_keys:
                        groups[key].source_keys.append(item.source_key)

                    groups[key].evidence.append(EvidenceItem(
                        claim_id=claim_id,
                        source_key=item.source_key,
                        source_path=source_path,
                        text=claim.text,
                        kind=claim.kind,
                        locator=claim.locator.model_dump(),
                    ))

        # Ensure groups exist for all resolved targets (even if no claims matched)
        for norm_name, (page_type, slug, title) in name_to_target.items():
            key = (page_type, slug)
            if key not in groups:
                current = _read_wiki_page(vault_root, page_type, slug)
                groups[key] = TargetGroup(
                    page_type=page_type,
                    slug=slug,
                    title=title,
                    current_content=current,
                )
            if item.source_key not in groups[key].source_keys:
                groups[key].source_keys.append(item.source_key)

    # Save groups to disk
    for (page_type, slug), group in groups.items():
        group_path = grouped_dir / f"{page_type}_{slug}.json"
        group_path.write_text(
            json.dumps(group.to_dict(), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    return list(groups.values())
