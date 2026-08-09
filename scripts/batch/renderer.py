"""
Renderer: deterministic source page generation.

Takes SourceExtraction + resolutions + mutation results → Markdown source page.
No LLM involved — pure template rendering.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from .models import SourceExtraction, PageMutationPlan

_LABELS: dict[str, dict[str, str]] = {
    "en": {
        "bibliographic_metadata": "Bibliographic Metadata",
        "summary": "Summary",
        "key_claims": "Key Claims",
        "important_quotes": "Important Quotes",
        "relevant_entities": "Relevant Entities",
        "relevant_concepts": "Relevant Concepts",
        "contradictions": "Contradictions",
        "pages_updated": "Pages Updated",
        "open_questions": "Open Questions",
        "no_claims": "_No claims extracted._",
        "none_identified": "_None identified._",
        "type_label": "Type",
        "authors_label": "Authors",
        "date_label": "Date",
        "source_key_label": "Source key",
        "participants_label": "Participants",
    },
    "pt": {
        "bibliographic_metadata": "Metadados Bibliográficos",
        "summary": "Resumo",
        "key_claims": "Claims Principais",
        "important_quotes": "Citações Importantes",
        "relevant_entities": "Entidades Relevantes",
        "relevant_concepts": "Conceitos Relevantes",
        "contradictions": "Contradições",
        "pages_updated": "Páginas Atualizadas",
        "open_questions": "Questões Abertas",
        "no_claims": "_Nenhum claim extraído._",
        "none_identified": "_Nenhum identificado._",
        "type_label": "Tipo",
        "authors_label": "Autores",
        "date_label": "Data",
        "source_key_label": "Chave da fonte",
        "participants_label": "Participantes",
    },
}


def _get_labels(wiki_language: str) -> dict[str, str]:
    """Return label dict; falls back to pt when wiki_language is 'source'."""
    if wiki_language in _LABELS:
        return _LABELS[wiki_language]
    return _LABELS["pt"]


def render_source_page(
    source_key: str,
    extraction: SourceExtraction,
    resolution_map: dict[str, dict],
    applied_plans: list[PageMutationPlan],
    created_at: str = "",
    wiki_language: str = "source",
) -> str:
    """Generate a wiki/sources/<source_key>.md page."""
    today = date.today().isoformat()
    created = created_at or today
    L = _get_labels(wiki_language)

    # Determine pages updated
    pages_updated = sorted({
        plan.slug for plan in applied_plans
        if plan.action in ("create", "update")
    })

    # Collect conflict slugs
    conflict_slugs = sorted({
        plan.slug for plan in applied_plans
        if plan.conflicts
    })

    # Collect entity and concept mentions resolved to existing/new pages
    entity_pages = []
    concept_pages = []
    for mention in extraction.entities:
        from .normalizer import fold_case
        norm = fold_case(mention.name)
        dec = resolution_map.get(norm, {})
        if dec.get("action") in ("existing", "new"):
            slug = dec.get("target_slug") or dec.get("suggested_slug")
            if slug and slug not in entity_pages:
                entity_pages.append(slug)

    for mention in extraction.concepts:
        from .normalizer import fold_case
        norm = fold_case(mention.name)
        dec = resolution_map.get(norm, {})
        if dec.get("action") in ("existing", "new"):
            slug = dec.get("target_slug") or dec.get("suggested_slug")
            if slug and slug not in concept_pages:
                concept_pages.append(slug)

    # Build tags
    tags = ["wiki/source"]
    source_type = "transcript"
    tags_yaml = "\n".join(f"  - {t}" for t in tags)

    # All source slugs from applied plans (for the sources: field)
    sources_yaml = f"  - {source_key}"

    # Build key claims section
    claims_section = ""
    for idx, claim in enumerate(extraction.claims[:20], start=1):
        locator_str = ""
        if claim.locator.timestamp_start:
            locator_str = f" [{claim.locator.timestamp_start}]"
        elif claim.locator.line_start:
            locator_str = f" [L{claim.locator.line_start:06d}]"
        if claim.locator.speaker:
            locator_str += f" {claim.locator.speaker}"
        claims_section += f"\n{idx}. {claim.text}{locator_str}"

    # Build entities section
    entities_section = ""
    for slug in entity_pages:
        entities_section += f"\n- [[{slug}]]"

    # Build concepts section
    concepts_section = ""
    for slug in concept_pages:
        concepts_section += f"\n- [[{slug}]]"

    # Build contradictions section
    conflicts_section = ""
    for plan in applied_plans:
        for conflict in plan.conflicts:
            conflicts_section += (
                f"\n- Conflict with [[{plan.slug}]] "
                f"({conflict.conflict_type}): "
                f"{conflict.explanation}"
            )

    # Build pages updated section
    pages_updated_section = ""
    for slug in pages_updated:
        pages_updated_section += f"\n- [[{slug}]]"

    # Build open questions section
    oq_section = ""
    for oq in extraction.open_questions:
        oq_section += f"\n- {oq.text}"

    # Build verbatim quotes section
    quotes_section = ""
    for claim in extraction.claims[:5]:
        if claim.verbatim_excerpt:
            quotes_section += f'\n> "{claim.verbatim_excerpt}"\n'

    # Authors line
    authors = ", ".join(extraction.authors) if extraction.authors else "Unknown"
    participants = ", ".join(extraction.participants) if extraction.participants else ""
    date_str = extraction.source_date or today

    page = f"""\
---
type: source
status: draft
confidence: medium
created: {created}
updated: {today}
aliases: []
abstract: "{extraction.factual_summary[:150].replace('"', "'")}"
sources:
{sources_yaml}
tags:
{tags_yaml}
batch_ingested: true
source_key: {source_key}
---

# {extraction.title}

## {L["bibliographic_metadata"]}

- **{L["type_label"]}:** {source_type}
- **{L["authors_label"]}:** {authors}
- **{L["date_label"]}:** {date_str}
- **{L["source_key_label"]}:** {source_key}
"""

    if participants:
        page += f"- **{L['participants_label']}:** {participants}\n"

    page += f"""
## {L["summary"]}

{extraction.factual_summary}

## {L["key_claims"]}
{claims_section if claims_section else f"\n{L['no_claims']}"}
"""

    if quotes_section:
        page += f"\n## {L['important_quotes']}\n{quotes_section}\n"

    page += f"""
## {L["relevant_entities"]}
{entities_section if entities_section else f"\n{L['none_identified']}"}

## {L["relevant_concepts"]}
{concepts_section if concepts_section else f"\n{L['none_identified']}"}
"""

    if conflicts_section:
        page += f"\n## {L['contradictions']}\n{conflicts_section}\n"

    if pages_updated_section:
        page += f"\n## {L['pages_updated']}\n{pages_updated_section}\n"

    if oq_section:
        page += f"\n## {L['open_questions']}\n{oq_section}\n"

    return page
