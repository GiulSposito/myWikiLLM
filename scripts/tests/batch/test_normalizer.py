"""Tests for normalizer.py."""

import pytest

from scripts.batch.models import ConceptMention, EntityMention, SourceExtraction, Locator, Claim
from scripts.batch.normalizer import (
    fold_case,
    load_alias_index,
    normalize_extraction,
    slugify,
    normalize_unicode,
)
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Text utilities
# ---------------------------------------------------------------------------

def test_fold_case_lowercases():
    assert fold_case("API Gateway") == "api gateway"


def test_fold_case_strips_whitespace():
    assert fold_case("  Kong  ") == "kong"


def test_normalize_unicode_nfc():
    # Composed vs decomposed 'é'
    composed = "é"
    decomposed = "é"
    assert normalize_unicode(decomposed) == composed


def test_slugify_basic():
    assert slugify("Retrieval-Augmented Generation") == "retrieval-augmented-generation"


def test_slugify_special_chars():
    assert slugify("CI&T") == "ci-t"


def test_slugify_accented_names():
    assert slugify("Fábio") == "fabio"
    assert slugify("João") == "joao"
    assert slugify("Nestlé") == "nestle"
    assert slugify("Pivô") == "pivo"
    assert slugify("Ícaro") == "icaro"
    assert slugify("Natália") == "natalia"


def test_slugify_preserves_ascii_hyphens():
    assert slugify("read-and-write (RW) modules") == "read-and-write-rw-modules"


# ---------------------------------------------------------------------------
# Alias index
# ---------------------------------------------------------------------------

def test_load_alias_index_empty_file(tmp_path):
    aliases_path = tmp_path / "aliases.yml"
    aliases_path.write_text("# No aliases\n", encoding="utf-8")
    # Monkeypatch not needed — passing vault_root param
    from scripts.batch.normalizer import load_alias_index as lia

    class FakeVault:
        def __truediv__(self, other):
            return tmp_path / other

    # Test direct call
    idx = lia(tmp_path)
    assert idx == {}


def test_load_alias_index_with_entries(tmp_path):
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "aliases.yml").write_text(
        "retrieval-augmented-generation:\n  - RAG\n  - Retrieval Augmented Generation\n",
        encoding="utf-8",
    )
    idx = load_alias_index(tmp_path)
    assert idx.get("rag") == "retrieval-augmented-generation"
    assert idx.get("retrieval augmented generation") == "retrieval-augmented-generation"


# ---------------------------------------------------------------------------
# normalize_extraction
# ---------------------------------------------------------------------------

def _make_extraction_with(entities=None, concepts=None):
    return SourceExtraction(
        schema_version="1",
        title="Test",
        factual_summary="Summary.",
        entities=entities or [],
        concepts=concepts or [],
    )


def test_dedup_exact_entity():
    entities = [
        EntityMention(name="Kong", entity_type="product"),
        EntityMention(name="Kong", entity_type="product"),
    ]
    extraction = _make_extraction_with(entities=entities)
    result = normalize_extraction(extraction, {})
    assert len(result.entities) == 1


def test_dedup_case_insensitive_entity():
    entities = [
        EntityMention(name="Kong", entity_type="product"),
        EntityMention(name="KONG", entity_type="product"),
    ]
    extraction = _make_extraction_with(entities=entities)
    result = normalize_extraction(extraction, {})
    assert len(result.entities) == 1


def test_invalid_entity_type_removed():
    entities = [EntityMention(name="Foobar", entity_type="invalid_type")]
    extraction = _make_extraction_with(entities=entities)
    result = normalize_extraction(extraction, {})
    assert len(result.entities) == 0


def test_alias_resolves_in_entity(tmp_path):
    manifests = tmp_path / "manifests"
    manifests.mkdir()
    (manifests / "aliases.yml").write_text(
        "retrieval-augmented-generation:\n  - RAG\n",
        encoding="utf-8",
    )
    alias_idx = load_alias_index(tmp_path)

    concepts = [ConceptMention(name="RAG")]
    extraction = _make_extraction_with(concepts=concepts)
    result = normalize_extraction(extraction, alias_idx)
    rag = result.concepts[0]
    assert "retrieval-augmented-generation" in rag.aliases


def test_dedup_concept_merges_aliases():
    concepts = [
        ConceptMention(name="OAuth", aliases=["OAuth 2.0"]),
        ConceptMention(name="OAuth", aliases=["OAuth2"]),
    ]
    extraction = _make_extraction_with(concepts=concepts)
    result = normalize_extraction(extraction, {})
    assert len(result.concepts) == 1
    alias_norms = [a.lower() for a in result.concepts[0].aliases]
    assert "oauth 2.0" in alias_norms
    assert "oauth2" in alias_norms
