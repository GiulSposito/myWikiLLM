"""Tests for resolver.py (no API calls)."""

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from scripts.batch.config import load_config
from scripts.batch.models import (
    ConceptMention,
    EntityMention,
    SourceExtraction,
    ResolutionDecision,
)
from scripts.batch.resolver import (
    build_wiki_lookup,
    find_fuzzy_candidates,
    resolve_mentions_for_source,
)

VAULT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Wiki lookup
# ---------------------------------------------------------------------------

def test_build_wiki_lookup_empty_wiki(tmp_path):
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)
    (tmp_path / "manifests").mkdir()
    (tmp_path / "manifests" / "aliases.yml").write_text("", encoding="utf-8")
    lookup = build_wiki_lookup(tmp_path)
    assert isinstance(lookup, dict)


def _write_concept_page(wiki_dir: Path, slug: str, title: str, aliases: list, abstract: str = ""):
    page = wiki_dir / "concepts" / f"{slug}.md"
    page.parent.mkdir(parents=True, exist_ok=True)
    fm = (
        f"---\ntype: concept\nstatus: draft\nconfidence: low\n"
        f"created: 2026-01-01\nupdated: 2026-01-01\n"
        f"aliases: {aliases}\nabstract: \"{abstract}\"\n"
        f"sources: []\ntags: []\n---\n\n# {title}\n"
    )
    page.write_text(fm, encoding="utf-8")


def test_build_wiki_lookup_finds_concept(tmp_path):
    _write_concept_page(tmp_path / "wiki", "api-gateway", "API Gateway",
                        ["API GW", "gateway"], "API Gateway routes HTTP requests.")
    (tmp_path / "manifests").mkdir(exist_ok=True)
    (tmp_path / "manifests" / "aliases.yml").write_text("", encoding="utf-8")

    lookup = build_wiki_lookup(tmp_path)
    assert "api-gateway" in lookup
    assert lookup["api-gateway"]["slug"] == "api-gateway"
    assert "api gw" in lookup
    assert "gateway" in lookup


# ---------------------------------------------------------------------------
# Fuzzy matching
# ---------------------------------------------------------------------------

def test_fuzzy_finds_close_match(tmp_path):
    _write_concept_page(tmp_path / "wiki", "retrieval-augmented-generation",
                        "Retrieval-Augmented Generation", ["RAG"])
    (tmp_path / "manifests").mkdir(exist_ok=True)
    (tmp_path / "manifests" / "aliases.yml").write_text("", encoding="utf-8")

    lookup = build_wiki_lookup(tmp_path)
    candidates = find_fuzzy_candidates(
        "Retrieval Augmented Generation", lookup, threshold=0.80, max_candidates=5
    )
    assert len(candidates) >= 1
    slugs = [c["slug"] for c in candidates]
    assert "retrieval-augmented-generation" in slugs


# ---------------------------------------------------------------------------
# resolve_mentions_for_source
# ---------------------------------------------------------------------------

def _make_extraction(entities=None, concepts=None):
    return SourceExtraction(
        schema_version="1",
        title="Test",
        factual_summary="Test summary.",
        entities=entities or [],
        concepts=concepts or [],
    )


def test_resolve_exact_match(tmp_path):
    _write_concept_page(tmp_path / "wiki", "oauth", "OAuth", [])
    (tmp_path / "manifests").mkdir(exist_ok=True)
    (tmp_path / "manifests" / "aliases.yml").write_text("", encoding="utf-8")

    lookup = build_wiki_lookup(tmp_path)
    cfg = load_config()
    extraction = _make_extraction(concepts=[ConceptMention(name="OAuth")])
    deferred = []
    resolutions = resolve_mentions_for_source(extraction, "src-001", lookup, cfg, deferred)

    norm_key = "oauth"
    assert norm_key in resolutions
    assert resolutions[norm_key]["action"] == "existing"
    assert resolutions[norm_key]["target_slug"] == "oauth"


def test_resolve_new_entity_no_candidates(tmp_path):
    (tmp_path / "wiki" / "entities").mkdir(parents=True)
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "manifests").mkdir(exist_ok=True)
    (tmp_path / "manifests" / "aliases.yml").write_text("", encoding="utf-8")

    lookup = build_wiki_lookup(tmp_path)
    cfg = load_config()
    extraction = _make_extraction(
        entities=[EntityMention(name="Acme Payments", entity_type="company")]
    )
    deferred = []
    resolutions = resolve_mentions_for_source(extraction, "src-002", lookup, cfg, deferred)

    norm_key = "acme payments"
    assert norm_key in resolutions
    assert resolutions[norm_key]["action"] == "new"
    assert resolutions[norm_key]["suggested_slug"] == "acme-payments"


def test_resolve_via_alias(tmp_path):
    manifests = tmp_path / "manifests"
    manifests.mkdir(exist_ok=True)
    (manifests / "aliases.yml").write_text(
        "retrieval-augmented-generation:\n  - RAG\n  - Retrieval Augmented Generation\n",
        encoding="utf-8",
    )
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)

    lookup = build_wiki_lookup(tmp_path)
    cfg = load_config()
    extraction = _make_extraction(concepts=[ConceptMention(name="RAG")])
    deferred = []
    resolutions = resolve_mentions_for_source(extraction, "src-003", lookup, cfg, deferred)

    norm_key = "rag"
    assert norm_key in resolutions
    assert resolutions[norm_key]["action"] == "existing"
    assert resolutions[norm_key]["target_slug"] == "retrieval-augmented-generation"
