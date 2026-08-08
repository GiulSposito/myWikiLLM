"""Tests for extractor.py: prompt construction, chunking, merge."""

from pathlib import Path

import pytest

from scripts.batch.config import load_config
from scripts.batch.extractor import (
    BATCH_EXTRACTION_RULES,
    _LANGUAGE_INSTRUCTIONS,
    chunk_transcript,
    get_system_prompt,
    merge_source_extraction,
    build_extraction_requests,
)
from scripts.batch.models import (
    Claim,
    ConceptMention,
    EntityMention,
    InternalTension,
    Locator,
    SourceExtraction,
)
from scripts.batch.state import BatchItem

VAULT_ROOT = Path(__file__).parent.parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# System prompt construction
# ---------------------------------------------------------------------------

def test_get_system_prompt_contains_batch_rules():
    prompt = get_system_prompt(VAULT_ROOT)
    assert "BATCH EXTRACTION MODE" in prompt


def test_get_system_prompt_contains_source_reader_rules():
    prompt = get_system_prompt(VAULT_ROOT)
    # source-reader content should be present
    assert "factual" in prompt.lower() or "extraction" in prompt.lower()


def test_batch_rules_include_concept_criteria():
    assert "Concepts to INCLUDE" in BATCH_EXTRACTION_RULES
    assert "Concepts to EXCLUDE" in BATCH_EXTRACTION_RULES


def test_system_prompt_contains_language_instruction_source():
    prompt = get_system_prompt(VAULT_ROOT, wiki_language="source")
    assert "same language as the source document" in prompt


def test_system_prompt_explicit_language_pt():
    prompt = get_system_prompt(VAULT_ROOT, wiki_language="pt")
    assert "Portuguese" in prompt


def test_system_prompt_explicit_language_en():
    prompt = get_system_prompt(VAULT_ROOT, wiki_language="en")
    assert "English" in prompt


def test_language_instructions_dict_has_all_keys():
    for key in ("source", "pt", "en"):
        assert key in _LANGUAGE_INSTRUCTIONS


def test_batch_rules_concept_exclude_generic_terms():
    # Rules must explicitly guard against the most common false positives
    for term in ("granularity", "accuracy", "optimization", "sanity check"):
        assert term in BATCH_EXTRACTION_RULES, f"Expected '{term}' in exclusion rules"


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

def test_chunk_short_transcript_no_split():
    text = "Short transcript content."
    chunks = chunk_transcript(text, target_tokens=100_000)
    assert len(chunks) == 1
    assert chunks[0] == text


def test_chunk_long_transcript_splits():
    # ~500k chars → ~125k tokens, split at 100k tokens (~400k chars)
    text = "word " * 100_000  # ~500k chars
    chunks = chunk_transcript(text, target_tokens=100_000, overlap_tokens=1_000)
    assert len(chunks) > 1


def test_chunk_overlap_exists():
    text = "abcde " * 100_000
    chunks = chunk_transcript(text, target_tokens=50_000, overlap_tokens=2_000)
    if len(chunks) > 1:
        # Overlap means end of chunk[0] should appear in start of chunk[1]
        end_of_first = chunks[0][-8000:]
        start_of_second = chunks[1][:8000]
        assert any(w in start_of_second for w in end_of_first.split()[:10])


# ---------------------------------------------------------------------------
# Merge extractions
# ---------------------------------------------------------------------------

def _make_extraction(title="T", claims=None, entities=None, concepts=None):
    return SourceExtraction(
        schema_version="1",
        title=title,
        factual_summary="Summary.",
        claims=claims or [],
        entities=entities or [],
        concepts=concepts or [],
    )


def _make_claim(text, kind="fact"):
    return Claim(text=text, kind=kind, locator=Locator())


def test_merge_single_part():
    e = _make_extraction(claims=[_make_claim("A fact.")])
    result = merge_source_extraction([e])
    assert len(result.claims) == 1


def test_merge_deduplicates_claims():
    e1 = _make_extraction(claims=[_make_claim("Same claim.")])
    e2 = _make_extraction(claims=[_make_claim("Same claim."), _make_claim("New claim.")])
    result = merge_source_extraction([e1, e2])
    assert len(result.claims) == 2


def test_merge_deduplicates_entities():
    e1 = _make_extraction(entities=[EntityMention(name="Acme", entity_type="company")])
    e2 = _make_extraction(entities=[EntityMention(name="Acme", entity_type="company"),
                                      EntityMention(name="Beta Corp", entity_type="company")])
    result = merge_source_extraction([e1, e2])
    names = [e.name for e in result.entities]
    assert names.count("Acme") == 1
    assert "Beta Corp" in names


def test_merge_combines_entity_aliases():
    e1 = _make_extraction(entities=[EntityMention(name="Acme", entity_type="company", aliases=["ACME"])])
    e2 = _make_extraction(entities=[EntityMention(name="Acme", entity_type="company", aliases=["Acme Inc."])])
    result = merge_source_extraction([e1, e2])
    acme = next(e for e in result.entities if e.name == "Acme")
    alias_lower = [a.lower() for a in acme.aliases]
    assert "acme" in alias_lower
    assert "acme inc." in alias_lower


# ---------------------------------------------------------------------------
# Build requests
# ---------------------------------------------------------------------------

def test_build_requests_produces_one_per_item():
    cfg = load_config()
    items = [
        BatchItem(
            source_key="meeting-01-abc12345",
            custom_id="src_meeting_01_abc12345",
            files=["tests/batch/fixtures/meeting-01-api-gateway.md"],
            sha256="abc",
        )
    ]
    requests = build_extraction_requests(items, cfg, VAULT_ROOT)
    assert len(requests) >= 1
    assert requests[0]["custom_id"] == "src_meeting_01_abc12345"


def test_build_requests_includes_schema():
    cfg = load_config()
    items = [
        BatchItem(
            source_key="meeting-01-abc",
            custom_id="src_meeting_01_abc",
            files=["tests/batch/fixtures/meeting-01-api-gateway.md"],
            sha256="abc",
        )
    ]
    requests = build_extraction_requests(items, cfg, VAULT_ROOT)
    params = requests[0]["params"]
    assert "output_config" in params


# ---------------------------------------------------------------------------
# Regression: InternalTension.claim_indexes null coercion
# ---------------------------------------------------------------------------

def test_internal_tension_null_claim_indexes_coerced():
    """LLM may return claim_indexes: null; must parse as empty list, not fail."""
    tension = InternalTension(description="Some tension", claim_indexes=None)
    assert tension.claim_indexes == []


def test_source_extraction_with_null_claim_indexes():
    """SourceExtraction validation must not raise when tensions have null claim_indexes."""
    data = {
        "schema_version": "1",
        "title": "Test",
        "factual_summary": "Summary.",
        "internal_tensions": [
            {"description": "Tension A", "claim_indexes": None},
            {"description": "Tension B", "claim_indexes": None},
        ],
    }
    extraction = SourceExtraction(**data)
    assert extraction.internal_tensions[0].claim_indexes == []
    assert extraction.internal_tensions[1].claim_indexes == []


def test_build_requests_cache_control_present():
    cfg = load_config()
    cfg.cache.enabled = True
    items = [
        BatchItem(
            source_key="meeting-02-abc",
            custom_id="src_meeting_02_abc",
            files=["tests/batch/fixtures/meeting-02-oauth.md"],
            sha256="abc",
        )
    ]
    requests = build_extraction_requests(items, cfg, VAULT_ROOT)
    system = requests[0]["params"]["system"]
    assert any("cache_control" in block for block in system)
