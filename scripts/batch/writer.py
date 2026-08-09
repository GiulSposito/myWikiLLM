"""
Single Writer: the ONLY module that may modify wiki/ and manifests/sources.yml.

Protocol:
1. Load update-plan.json
2. Optimistic lock check (baseline SHA256 per target file)
3. Write to temp files
4. Validate temp results
5. Atomic replace
6. Update manifests/sources.yml in one transaction
7. Append single log entry to wiki/log.md
8. Call rebuild_index.py
"""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import date
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise ImportError("pyyaml is required") from exc

from .config import BatchIngestConfig
from .models import PageMutationPlan, SourceExtraction
from .planner import UpdatePlan
from .renderer import render_source_page, _LABELS, _get_labels
from .state import BatchState

VAULT_ROOT_DEFAULT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Optimistic locking
# ---------------------------------------------------------------------------

def _sha256_file(path: Path) -> str:
    if not path.exists():
        return ""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class ConcurrentModificationError(Exception):
    pass


def check_optimistic_locks(plan: UpdatePlan, vault_root: Path) -> list[str]:
    """Return list of paths whose baseline hash no longer matches current hash."""
    stale = []
    for file_entry in plan.files:
        current_path = vault_root / file_entry["path"]
        baseline = file_entry.get("baseline_sha256", "")
        current = _sha256_file(current_path)
        if baseline and current and baseline != current:
            stale.append(file_entry["path"])
    return stale


# ---------------------------------------------------------------------------
# Page mutation application
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Split frontmatter and body. Returns (fm_dict, body_text)."""
    if not text.startswith("---"):
        return {}, text
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}, text
    try:
        fm = yaml.safe_load(parts[1]) or {}
    except Exception:
        fm = {}
    return fm, parts[2]


def _serialize_frontmatter(fm: dict) -> str:
    return "---\n" + yaml.dump(fm, allow_unicode=True, sort_keys=False) + "---\n"


def apply_mutation_to_existing_page(
    existing_content: str,
    plan: PageMutationPlan,
    today: str,
    wiki_language: str = "source",
) -> str:
    """Apply append-only mutations to an existing page."""
    L = _get_labels(wiki_language)
    fm, body = _parse_frontmatter(existing_content)

    # Update metadata
    fm["updated"] = today

    if plan.aliases_to_add:
        existing_aliases = set(str(a).lower() for a in (fm.get("aliases") or []))
        for alias in plan.aliases_to_add:
            if alias.lower() not in existing_aliases:
                fm.setdefault("aliases", []).append(alias)

    # Add new sources
    if not isinstance(fm.get("sources"), list):
        fm["sources"] = []
    for ca in plan.claims_to_add:
        if ca.source_slug not in fm["sources"]:
            fm["sources"].append(ca.source_slug)

    # Set conflict status
    if plan.conflicts:
        fm["status"] = "conflict"

    new_content = _serialize_frontmatter(fm) + body

    # Append new claims section
    if plan.claims_to_add:
        claims_block = f"\n\n## {L['key_claims']}\n\n"
        for ca in plan.claims_to_add:
            claims_block += f"- {ca.text} ([[{ca.source_slug}]], claim `{ca.source_claim_id}`)\n"
        new_content += claims_block

    # Append conflicts section
    if plan.conflicts:
        conflict_block = f"\n\n## {L['contradictions']}\n\n"
        for conflict in plan.conflicts:
            conflict_block += (
                f"- **{conflict.conflict_type}**: "
                f"{conflict.explanation} "
                f"(existing: [[{conflict.existing_source or '?'}]], "
                f"new: [[{conflict.new_source}]])\n"
            )
        new_content += conflict_block

    # Append open questions
    if plan.proposed_open_questions:
        oq_block = f"\n\n## {L['open_questions']}\n\n"
        for oq in plan.proposed_open_questions:
            oq_block += f"- {oq}\n"
        new_content += oq_block

    return new_content


_PAGE_SECTION_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "definition": "Definition",
        "key_facts": "Key Facts",
        "related_pages": "Related Pages",
        "contradictions": "Contradictions",
        "open_questions": "Open Questions",
    },
    "pt": {
        "definition": "Definição",
        "key_facts": "Fatos Principais",
        "related_pages": "Páginas Relacionadas",
        "contradictions": "Contradições",
        "open_questions": "Questões Abertas",
    },
}


def _get_page_labels(wiki_language: str) -> dict[str, str]:
    if wiki_language in _PAGE_SECTION_LABELS:
        return _PAGE_SECTION_LABELS[wiki_language]
    return _PAGE_SECTION_LABELS["pt"]


def create_new_page(
    plan: PageMutationPlan,
    today: str,
    wiki_language: str = "source",
) -> str:
    """Generate a new concept or entity page from a mutation plan."""
    PL = _get_page_labels(wiki_language)
    tags = [f"wiki/{plan.page_type}"]
    sources = list({ca.source_slug for ca in plan.claims_to_add})

    fm = {
        "type": plan.page_type,
        "status": "draft",
        "confidence": "low",
        "created": today,
        "updated": today,
        "aliases": list(plan.aliases_to_add),
        "abstract": plan.abstract or "",
        "sources": sources,
        "tags": tags,
    }

    body = f"\n# {plan.title}\n\n"

    if plan.abstract:
        body += f"{plan.abstract}\n\n"

    if plan.definition:
        body += f"## {PL['definition']}\n\n{plan.definition}\n\n"

    if plan.claims_to_add:
        body += f"## {PL['key_facts']}\n\n"
        for ca in plan.claims_to_add:
            body += f"- {ca.text} ([[{ca.source_slug}]])\n"
        body += "\n"

    if plan.relations_to_add:
        body += f"## {PL['related_pages']}\n\n"
        for rel in plan.relations_to_add:
            body += f"- [[{rel.target_slug}]] ({rel.relation_type})\n"
        body += "\n"

    if plan.conflicts:
        fm["status"] = "conflict"
        body += f"## {PL['contradictions']}\n\n"
        for conflict in plan.conflicts:
            body += (
                f"- **{conflict.conflict_type}**: "
                f"{conflict.explanation}\n"
            )
        body += "\n"

    if plan.proposed_open_questions:
        body += f"## {PL['open_questions']}\n\n"
        for oq in plan.proposed_open_questions:
            body += f"- {oq}\n"
        body += "\n"

    return _serialize_frontmatter(fm) + body


# ---------------------------------------------------------------------------
# Sources YAML update
# ---------------------------------------------------------------------------

def _load_sources_yml(path: Path) -> dict:
    if not path.exists():
        return {"sources": []}
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(raw.get("sources"), list):
        raw["sources"] = []
    return raw


def _update_sources_yml(
    sources_path: Path,
    state: BatchState,
    extraction_dir: Path,
) -> None:
    """Rewrite sources.yml in one transaction."""
    data = _load_sources_yml(sources_path)
    existing_slugs = {s.get("slug") for s in data["sources"] if isinstance(s, dict)}

    for item in state.items:
        if item.status in ("skipped_duplicate", "changed-source"):
            continue
        if item.source_key in existing_slugs:
            continue

        extraction_path = extraction_dir / f"{item.source_key}.json"
        title = item.source_key
        source_date = None
        if extraction_path.exists():
            try:
                ext = SourceExtraction.model_validate_json(
                    extraction_path.read_text(encoding="utf-8")
                )
                title = ext.title
                source_date = ext.source_date
            except Exception:
                pass

        entry: dict[str, Any] = {
            "slug": item.source_key,
            "title": title,
            "type": "transcript",
            "ingested": date.today().isoformat(),
            "raw_path": item.files[0] if item.files else "",
            "sha256": item.sha256,
            "batch_id": state.batch_id,
            "extraction": {
                "schema_version": "1",
                "model": state.extraction_model,
            },
        }
        if source_date:
            entry["source_date"] = source_date

        data["sources"].append(entry)

    tmp = sources_path.with_suffix(".yml.tmp")
    tmp.write_text(yaml.dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8")
    tmp.replace(sources_path)


# ---------------------------------------------------------------------------
# Log entry
# ---------------------------------------------------------------------------

def _append_log_entry(log_path: Path, state: BatchState, plan: UpdatePlan) -> None:
    today = date.today().isoformat()
    entry = f"\n## {today} — Batch ingest: {state.batch_id}\n\n"
    entry += f"- Sources ingested: {plan.sources.get('create', 0) + plan.sources.get('update', 0)}\n"
    entry += f"- New concepts: {plan.concepts.get('create', 0)}\n"
    entry += f"- Updated concepts: {plan.concepts.get('update', 0)}\n"
    entry += f"- New entities: {plan.entities.get('create', 0)}\n"
    entry += f"- Updated entities: {plan.entities.get('update', 0)}\n"
    entry += f"- Conflicts detected: {len(plan.conflicts)}\n"
    deferred = plan.concepts.get("defer", 0) + plan.entities.get("defer", 0)
    entry += f"- Deferred resolutions: {deferred}\n"

    if log_path.exists():
        existing = log_path.read_text(encoding="utf-8")
        log_path.write_text(existing + entry, encoding="utf-8")
    else:
        log_path.write_text(
            "---\ntype: concept\nstatus: active\nconfidence: high\n"
            f"created: {today}\nupdated: {today}\naliases: []\n"
            "abstract: \"\"\nsources: []\ntags: [meta]\n---\n\n# Ingest Log\n"
            + entry,
            encoding="utf-8",
        )


# ---------------------------------------------------------------------------
# Main apply
# ---------------------------------------------------------------------------

def apply_update_plan(
    plan: UpdatePlan,
    state: BatchState,
    cfg: BatchIngestConfig,
    vault_root: Path,
) -> None:
    """Apply all mutations in update-plan.json to the wiki."""
    from .progress import Progress

    today = date.today().isoformat()

    # Optimistic lock check
    if cfg.apply.optimistic_locking:
        stale = check_optimistic_locks(plan, vault_root)
        for stale_path in stale:
            print(f"  ! Concurrent modification detected, skipping: {stale_path}")
            for fe in plan.files:
                if fe["path"] == stale_path:
                    fe["_status"] = "needs-replan"

    extraction_dir = state.batch_dir / "extraction"
    normalized_dir = state.batch_dir / "normalized"
    resolution_dir = state.batch_dir / "resolution"

    applicable = [fe for fe in plan.files if fe.get("_status") != "needs-replan"]
    progress = Progress("Apply", total=len(applicable))
    written: list[str] = []
    skipped: list[str] = []
    apply_count = 0

    # Build source_key → [plans] lookup once (avoids O(N²) glob inside the loop)
    curation_dir = state.batch_dir / "curation"
    source_to_plans: dict[str, list[PageMutationPlan]] = {}
    if curation_dir.exists():
        for cp in curation_dir.glob("*.json"):
            try:
                mp = PageMutationPlan.model_validate_json(cp.read_text(encoding="utf-8"))
                source_to_plans.setdefault(mp.slug, []).append(mp)
            except Exception:
                pass
    all_plans = [mp for plans in source_to_plans.values() for mp in plans]

    # Apply concept/entity mutation plans
    for fe in plan.files:
        if fe.get("_status") == "needs-replan":
            skipped.append(fe["path"])
            continue

        mp_data = fe.get("mutation_plan")
        source_key = fe.get("source_key")

        if mp_data:
            # This is a concept/entity page
            mp = PageMutationPlan(**mp_data)
            target_path = vault_root / fe["path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)

            if target_path.exists():
                existing = target_path.read_text(encoding="utf-8")
                new_content = apply_mutation_to_existing_page(existing, mp, today, cfg.wiki_language)
            else:
                new_content = create_new_page(mp, today, cfg.wiki_language)

            tmp = target_path.with_suffix(".md.tmp")
            tmp.write_text(new_content, encoding="utf-8")
            tmp.replace(target_path)
            written.append(fe["path"])
            apply_count += 1
            n_claims = len(mp.claims_to_add)
            detail = f"{mp.action}, {n_claims} claims"
            if mp.conflicts:
                detail += f", {len(mp.conflicts)} conflicts"
            progress.step(apply_count, label=fe["path"].split("/")[-1], detail=detail)

        elif source_key:
            # This is a source page
            norm_path = normalized_dir / f"{source_key}.json"
            if not norm_path.exists():
                norm_path = extraction_dir / f"{source_key}.json"
            if not norm_path.exists():
                continue

            extraction = SourceExtraction.model_validate_json(
                norm_path.read_text(encoding="utf-8")
            )

            res_path = resolution_dir / f"{source_key}.json"
            resolution_map = {}
            if res_path.exists():
                resolution_map = json.loads(res_path.read_text(encoding="utf-8"))

            applied_plans = all_plans

            source_page = render_source_page(
                source_key, extraction, resolution_map, applied_plans,
                created_at=today, wiki_language=cfg.wiki_language,
            )

            target_path = vault_root / fe["path"]
            target_path.parent.mkdir(parents=True, exist_ok=True)
            tmp = target_path.with_suffix(".md.tmp")
            tmp.write_text(source_page, encoding="utf-8")
            tmp.replace(target_path)
            written.append(fe["path"])
            state.update_status(source_key, "applied")
            apply_count += 1
            progress.step(apply_count, label=fe["path"].split("/")[-1], detail="source")

    # Update sources.yml in one transaction
    sources_path = vault_root / "manifests" / "sources.yml"
    _update_sources_yml(sources_path, state, extraction_dir)

    # Append log entry
    log_path = vault_root / "wiki" / "log.md"
    _append_log_entry(log_path, state, plan)

    # Rebuild index
    rebuild_script = vault_root / "scripts" / "rebuild_index.py"
    if rebuild_script.exists():
        subprocess.run(
            [sys.executable, str(rebuild_script)],
            cwd=vault_root,
            check=False,
        )

    progress.done(f"{len(written)} files written")
    if skipped:
        print(f"  ! Skipped (concurrent modification): {len(skipped)} files")
        for s in skipped:
            print(f"    needs-replan: {s}")
