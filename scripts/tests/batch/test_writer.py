"""Tests for renderer.py and writer.py."""

import json
import shutil
from pathlib import Path

import pytest

from scripts.batch.config import load_config
from scripts.batch.models import (
    Claim,
    ClaimAddition,
    Conflict,
    ConceptMention,
    EntityMention,
    Locator,
    PageMutationPlan,
    SourceExtraction,
)
from scripts.batch.planner import UpdatePlan, build_update_plan
from scripts.batch.renderer import render_source_page
from scripts.batch.state import BatchItem, BatchState
from scripts.batch.writer import (
    apply_mutation_to_existing_page,
    check_optimistic_locks,
    create_new_page,
)

VAULT_ROOT = Path(__file__).parent.parent.parent
FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Renderer tests
# ---------------------------------------------------------------------------

def test_render_source_page_contains_title():
    extraction = SourceExtraction(
        schema_version="1",
        title="API Gateway Meeting",
        factual_summary="Meeting about Kong deployment.",
        claims=[Claim(
            text="Kong was selected.",
            kind="decision",
            locator=Locator(timestamp_start="00:01:00"),
        )],
    )
    page = render_source_page("meeting-01-abc", extraction, {}, [])
    assert "# API Gateway Meeting" in page


def test_render_source_page_has_frontmatter():
    extraction = SourceExtraction(
        schema_version="1",
        title="Test",
        factual_summary="Test summary.",
    )
    page = render_source_page("test-src", extraction, {}, [])
    assert page.startswith("---")
    assert "type: source" in page


def test_render_source_page_has_claims():
    extraction = SourceExtraction(
        schema_version="1",
        title="T",
        factual_summary="Summary.",
        claims=[
            Claim(text="Decision A was made.", kind="decision",
                  locator=Locator(timestamp_start="00:01:00")),
            Claim(text="Risk B was identified.", kind="risk",
                  locator=Locator(timestamp_start="00:02:00")),
        ],
    )
    page = render_source_page("test", extraction, {}, [])
    assert "Decision A was made." in page
    assert "Risk B was identified." in page


def test_render_source_page_links_entities():
    extraction = SourceExtraction(
        schema_version="1",
        title="T",
        factual_summary="Summary.",
        entities=[EntityMention(name="Kong", entity_type="product")],
    )
    resolution_map = {
        "kong": {"action": "existing", "target_slug": "kong"}
    }
    page = render_source_page("test", extraction, resolution_map, [])
    assert "[[kong]]" in page


def test_render_source_page_shows_conflicts():
    plan = PageMutationPlan(
        page_type="concept",
        action="update",
        slug="api-gateway",
        title="API Gateway",
        conflicts=[Conflict(
            conflict_type="different-data",
            existing_claim="Timeout is 30s.",
            existing_source="meeting-01",
            new_claim="Timeout is 60s.",
            new_source="meeting-05",
            explanation="Two different values stated.",
        )],
    )
    extraction = SourceExtraction(
        schema_version="1",
        title="T",
        factual_summary="Summary.",
    )
    page = render_source_page("test", extraction, {}, [plan], wiki_language="en")
    assert "Contradictions" in page
    assert "different-data" in page


# ---------------------------------------------------------------------------
# Writer: mutation application
# ---------------------------------------------------------------------------

def test_apply_mutation_appends_claims():
    existing = (
        "---\ntype: concept\nstatus: draft\nconfidence: low\n"
        "created: 2026-01-01\nupdated: 2026-01-01\naliases: []\n"
        "abstract: \"\"\nsources: []\ntags: []\n---\n\n# API Gateway\n\nExisting content.\n"
    )
    plan = PageMutationPlan(
        page_type="concept",
        action="update",
        slug="api-gateway",
        title="API Gateway",
        claims_to_add=[ClaimAddition(
            text="Kong is the API Gateway.",
            source_slug="meeting-01",
            source_claim_id="meeting-01:c0000",
        )],
    )
    result = apply_mutation_to_existing_page(existing, plan, "2026-08-07")
    assert "Kong is the API Gateway." in result
    assert "meeting-01" in result


def test_apply_mutation_sets_conflict_status():
    existing = (
        "---\ntype: concept\nstatus: draft\nconfidence: low\n"
        "created: 2026-01-01\nupdated: 2026-01-01\naliases: []\n"
        "abstract: \"\"\nsources: []\ntags: []\n---\n\n# API Gateway\n"
    )
    plan = PageMutationPlan(
        page_type="concept",
        action="update",
        slug="api-gateway",
        title="API Gateway",
        conflicts=[Conflict(
            conflict_type="different-data",
            existing_claim="30s",
            existing_source="meeting-01",
            new_claim="60s",
            new_source="meeting-05",
            explanation="Conflicting timeout values.",
        )],
    )
    result = apply_mutation_to_existing_page(existing, plan, "2026-08-07", wiki_language="en")
    assert "conflict" in result
    assert "Contradictions" in result


def test_apply_mutation_does_not_delete_existing_content():
    existing = (
        "---\ntype: concept\nstatus: draft\nconfidence: low\n"
        "created: 2026-01-01\nupdated: 2026-01-01\naliases: []\n"
        "abstract: \"\"\nsources: []\ntags: []\n---\n\n# API Gateway\n\n"
        "This is important existing knowledge.\n"
    )
    plan = PageMutationPlan(
        page_type="concept",
        action="update",
        slug="api-gateway",
        title="API Gateway",
        claims_to_add=[ClaimAddition(
            text="New fact.",
            source_slug="meeting-02",
            source_claim_id="meeting-02:c0000",
        )],
    )
    result = apply_mutation_to_existing_page(existing, plan, "2026-08-07")
    assert "This is important existing knowledge." in result
    assert "New fact." in result


def test_create_new_page_includes_required_fields():
    plan = PageMutationPlan(
        page_type="concept",
        action="create",
        slug="oauth",
        title="OAuth 2.0",
        abstract="OAuth 2.0 is an authorization framework.",
        aliases_to_add=["OAuth", "OAuth2"],
        claims_to_add=[ClaimAddition(
            text="OAuth 2.0 uses authorization codes.",
            source_slug="meeting-02",
            source_claim_id="meeting-02:c0000",
        )],
    )
    page = create_new_page(plan, "2026-08-07")
    assert "type: concept" in page
    assert "status: draft" in page
    assert "OAuth 2.0" in page
    assert "OAuth 2.0 is an authorization framework." in page
    assert "meeting-02" in page


# ---------------------------------------------------------------------------
# Writer: optimistic locking
# ---------------------------------------------------------------------------

def test_optimistic_lock_detects_change(tmp_path):
    f = tmp_path / "wiki" / "concepts" / "api-gateway.md"
    f.parent.mkdir(parents=True)
    f.write_text("original content")

    import hashlib
    h = hashlib.sha256(b"original content").hexdigest()

    plan = UpdatePlan(
        batch_id="test",
        files=[{
            "path": "wiki/concepts/api-gateway.md",
            "action": "update",
            "baseline_sha256": h,
        }],
    )
    # No change → no stale
    stale = check_optimistic_locks(plan, tmp_path)
    assert stale == []

    # Modify file
    f.write_text("modified content")
    stale = check_optimistic_locks(plan, tmp_path)
    assert "wiki/concepts/api-gateway.md" in stale


def test_optimistic_lock_passes_for_new_files(tmp_path):
    plan = UpdatePlan(
        batch_id="test",
        files=[{
            "path": "wiki/concepts/new-page.md",
            "action": "create",
            "baseline_sha256": "",  # empty = new file
        }],
    )
    stale = check_optimistic_locks(plan, tmp_path)
    assert stale == []


# ---------------------------------------------------------------------------
# Language localization
# ---------------------------------------------------------------------------

def test_render_source_page_pt_labels():
    extraction = SourceExtraction(schema_version="1", title="T", factual_summary="Resumo.")
    page = render_source_page("src", extraction, {}, [], wiki_language="pt")
    assert "Metadados Bibliográficos" in page
    assert "Resumo" in page
    assert "Claims Principais" in page


def test_render_source_page_en_labels():
    extraction = SourceExtraction(schema_version="1", title="T", factual_summary="Summary.")
    page = render_source_page("src", extraction, {}, [], wiki_language="en")
    assert "Bibliographic Metadata" in page
    assert "Summary" in page
    assert "Key Claims" in page


def test_create_new_page_pt_labels():
    plan = PageMutationPlan(
        page_type="concept", action="create", slug="inferencia-causal",
        title="Inferência Causal", definition="Método para determinar relações causais.",
    )
    page = create_new_page(plan, "2026-08-07", wiki_language="pt")
    assert "Definição" in page
    assert "Inferência Causal" in page


def test_create_new_page_en_labels():
    plan = PageMutationPlan(
        page_type="concept", action="create", slug="causal-inference",
        title="Causal Inference", definition="Method to determine causal relationships.",
    )
    page = create_new_page(plan, "2026-08-07", wiki_language="en")
    assert "Definition" in page
    assert "Causal Inference" in page


def test_apply_mutation_pt_labels():
    existing = (
        "---\ntype: concept\nstatus: draft\nconfidence: low\n"
        "created: 2026-01-01\nupdated: 2026-01-01\naliases: []\n"
        "abstract: \"\"\nsources: []\ntags: []\n---\n\n# Inferência Causal\n"
    )
    plan = PageMutationPlan(
        page_type="concept", action="update", slug="inferencia-causal",
        title="Inferência Causal",
        proposed_open_questions=["Como aplicar em dados esparsos?"],
    )
    result = apply_mutation_to_existing_page(existing, plan, "2026-08-07", wiki_language="pt")
    assert "Questões Abertas" in result
