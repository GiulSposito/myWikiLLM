"""
Resolver: map extracted entity/concept mentions to canonical wiki pages.

Three resolution paths (spec §19):
A. Exact match → auto-resolve (deterministic)
B. High-confidence fuzzy match (≥ threshold) → auto-resolve
C. Ambiguous → Resolution Batch (Sonnet structured output)
   'defer' action → never creates a page automatically
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise ImportError("pyyaml is required") from exc

from .config import BatchIngestConfig
from .models import ResolutionDecision, SourceExtraction
from .normalizer import fold_case, slugify, load_alias_index
from .state import BatchState

VAULT_ROOT_DEFAULT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Wiki page index
# ---------------------------------------------------------------------------

def _parse_frontmatter(path: Path) -> dict | None:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None
    if not text.startswith("---"):
        return None
    parts = text.split("---", 2)
    if len(parts) < 3:
        return None
    try:
        data = yaml.safe_load(parts[1])
    except Exception:
        return None
    return data if isinstance(data, dict) else None


def build_wiki_lookup(vault_root: Path) -> dict[str, dict]:
    """
    Returns {normalized_name: {slug, title, aliases, abstract, page_type}}.
    Includes: direct slugs, aliases from frontmatter, and aliases.yml.
    """
    lookup: dict[str, dict] = {}
    alias_index = load_alias_index(vault_root)

    # Pre-load alias_index as slug-level entries
    for norm_name, canonical_slug in alias_index.items():
        if canonical_slug not in lookup.values():
            lookup[norm_name] = {"slug": canonical_slug, "title": canonical_slug,
                                  "aliases": [], "abstract": "", "page_type": "unknown"}

    for subdir in ("concepts", "entities"):
        wiki_dir = vault_root / "wiki" / subdir
        if not wiki_dir.exists():
            continue
        for md_path in wiki_dir.glob("*.md"):
            fm = _parse_frontmatter(md_path)
            if not fm:
                continue
            slug = md_path.stem
            title = fm.get("title") or slug
            aliases = fm.get("aliases") or []
            abstract = fm.get("abstract") or ""
            page_type = "concept" if subdir == "concepts" else "entity"

            entry = {
                "slug": slug,
                "title": title,
                "aliases": aliases,
                "abstract": abstract,
                "page_type": page_type,
            }

            lookup[fold_case(slug)] = entry
            lookup[slugify(slug)] = entry
            lookup[fold_case(title)] = entry
            for alias in aliases:
                lookup[fold_case(str(alias))] = entry
                lookup[slugify(str(alias))] = entry

    return lookup


def find_fuzzy_candidates(
    name: str,
    lookup: dict[str, dict],
    threshold: float,
    max_candidates: int,
) -> list[dict]:
    """Find candidate pages by fuzzy name match."""
    try:
        from rapidfuzz import process, fuzz
    except ImportError:
        return []

    name_norm = fold_case(name)
    name_slug = slugify(name)

    all_keys = list(lookup.keys())
    matches = process.extract(
        name_norm,
        all_keys,
        scorer=fuzz.WRatio,
        limit=max_candidates * 3,
        score_cutoff=threshold * 100,
    )

    seen_slugs: set[str] = set()
    candidates = []
    for match_key, score, _ in matches:
        entry = lookup[match_key]
        slug = entry["slug"]
        if slug not in seen_slugs:
            seen_slugs.add(slug)
            candidates.append({**entry, "_score": score / 100.0})
        if len(candidates) >= max_candidates:
            break

    return candidates


# ---------------------------------------------------------------------------
# Resolution decision
# ---------------------------------------------------------------------------

RESOLUTION_SYSTEM_PROMPT = """You are a knowledge entity resolver for a wiki.
Given an entity or concept mention and a list of candidate wiki pages,
decide which action to take:

- "existing": the mention clearly refers to one of the candidates. Provide target_slug.
- "new": the mention is clearly distinct from all candidates and warrants a new page.
  Provide canonical_name and suggested_slug.
- "defer": insufficient context to decide confidently. Use this for ambiguous cases.

Be conservative: prefer "defer" over a low-confidence "existing" or "new".
"""


def _resolve_with_llm(
    mention_name: str,
    mention_kind: str,
    candidates: list[dict],
    evidence_texts: list[str],
    cfg: BatchIngestConfig,
) -> ResolutionDecision:
    """Call the configured model to resolve an ambiguous mention."""
    if cfg.provider == "litellm":
        from .litellm_sync import run_resolution_sync
        result = run_resolution_sync(mention_name, mention_kind, candidates, evidence_texts, cfg)
        return ResolutionDecision(**result)

    # Default: Anthropic SDK direct call
    import anthropic

    has_auth = (
        os.environ.get("ANTHROPIC_API_KEY")
        or os.environ.get("ANTHROPIC_AUTH_TOKEN")
        or os.environ.get("ANTHROPIC_MODEL")
    )
    if not has_auth:
        return ResolutionDecision(action="defer", confidence="low")

    client = anthropic.Anthropic()
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

    response = client.messages.create(
        model=cfg.models.resolution,
        max_tokens=cfg.tokens.resolution_max_output,
        system=RESOLUTION_SYSTEM_PROMPT,
        messages=[{
            "role": "user",
            "content": json.dumps(payload, ensure_ascii=False),
        }],
    )

    try:
        data = json.loads(response.content[0].text)
        return ResolutionDecision(**data)
    except Exception:
        return ResolutionDecision(action="defer", confidence="low")


# ---------------------------------------------------------------------------
# Per-source resolution
# ---------------------------------------------------------------------------

def resolve_mentions_for_source(
    extraction: SourceExtraction,
    source_key: str,
    wiki_lookup: dict[str, dict],
    cfg: BatchIngestConfig,
    deferred: list[dict],
) -> dict[str, Any]:
    """
    Resolve all entity and concept mentions.
    Returns resolution map: {normalized_name: ResolutionDecision}.
    """
    resolutions: dict[str, ResolutionDecision] = {}
    threshold = cfg.resolution.fuzzy_auto_threshold

    all_mentions = (
        [(m.name, "entity") for m in extraction.entities]
        + [(m.name, "concept") for m in extraction.concepts]
    )

    for mention_name, mention_kind in all_mentions:
        norm = fold_case(mention_name)
        if norm in resolutions:
            continue

        # Path A: exact match
        if norm in wiki_lookup:
            entry = wiki_lookup[norm]
            resolutions[norm] = ResolutionDecision(
                action="existing",
                target_slug=entry["slug"],
                canonical_name=mention_name,
                confidence="high",
            )
            continue

        slug_form = slugify(mention_name)
        if slug_form in wiki_lookup:
            entry = wiki_lookup[slug_form]
            resolutions[norm] = ResolutionDecision(
                action="existing",
                target_slug=entry["slug"],
                canonical_name=mention_name,
                confidence="high",
            )
            continue

        # Path B: fuzzy
        candidates = find_fuzzy_candidates(
            mention_name, wiki_lookup, threshold, cfg.resolution.max_candidates
        )
        if len(candidates) == 1 and candidates[0]["_score"] >= threshold:
            resolutions[norm] = ResolutionDecision(
                action="existing",
                target_slug=candidates[0]["slug"],
                canonical_name=mention_name,
                confidence="high",
            )
            continue

        if len(candidates) == 0:
            # New entity/concept — no existing match
            resolutions[norm] = ResolutionDecision(
                action="new",
                canonical_name=mention_name,
                suggested_slug=slugify(mention_name),
                confidence="high",
            )
            continue

        # Path C: ambiguous → LLM
        evidence = [c.text for c in extraction.claims
                    if mention_name.lower() in c.text.lower()][:3]

        can_call_llm = (
            cfg.provider == "litellm"
            or bool(os.environ.get("ANTHROPIC_API_KEY"))
            or bool(os.environ.get("ANTHROPIC_AUTH_TOKEN"))
            or bool(os.environ.get("ANTHROPIC_MODEL"))
        )
        if not can_call_llm:
            decision = ResolutionDecision(action="defer", confidence="low")
        else:
            decision = _resolve_with_llm(
                mention_name, mention_kind, candidates, evidence, cfg
            )

        if decision.action == "defer":
            deferred.append({
                "source_key": source_key,
                "mention": mention_name,
                "kind": mention_kind,
                "candidates": [c["slug"] for c in candidates],
            })

        resolutions[norm] = decision

    return {k: v.model_dump() for k, v in resolutions.items()}


# ---------------------------------------------------------------------------
# Batch resolution
# ---------------------------------------------------------------------------

def resolve_batch(
    state: BatchState,
    cfg: BatchIngestConfig,
    vault_root: Path,
) -> tuple[int, int]:
    """Resolve all normalized items. Returns (resolved_count, deferred_count)."""
    from .progress import Progress

    wiki_lookup = build_wiki_lookup(vault_root)
    normalized_dir = state.batch_dir / "normalized"
    resolution_dir = state.batch_dir / "resolution"
    resolution_dir.mkdir(exist_ok=True)

    items = state.items_by_status("normalized")
    progress = Progress("Resolve", total=len(items))
    resolved = 0
    deferred_items: list[dict] = []

    for item in items:
        src_path = normalized_dir / f"{item.source_key}.json"
        if not src_path.exists():
            continue

        extraction = SourceExtraction.model_validate_json(
            src_path.read_text(encoding="utf-8")
        )

        resolution_map = resolve_mentions_for_source(
            extraction, item.source_key, wiki_lookup, cfg, deferred_items
        )

        out_path = resolution_dir / f"{item.source_key}.json"
        out_path.write_text(
            json.dumps(resolution_map, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        state.update_status(item.source_key, "resolved")
        resolved += 1

        n_resolved = sum(1 for v in resolution_map.values()
                         if isinstance(v, dict) and v.get("action") != "defer")
        n_deferred = sum(1 for v in resolution_map.values()
                         if isinstance(v, dict) and v.get("action") == "defer")
        detail = f"{n_resolved} resolved"
        if n_deferred:
            detail += f", {n_deferred} deferred"
        progress.step(resolved, label=item.source_key, detail=detail)

    progress.done(f"{resolved} sources, {len(deferred_items)} total deferred")
    return resolved, len(deferred_items)
