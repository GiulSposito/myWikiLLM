"""Tests for grouper.py and planner.py."""

import json
from pathlib import Path

import pytest

from scripts.batch.models import (
    ClaimAddition,
    Conflict,
    EntityMention,
    ConceptMention,
    Locator,
    Claim,
    PageMutationPlan,
    SourceExtraction,
)
from scripts.batch.grouper import group_evidence, TargetGroup
from scripts.batch.planner import UpdatePlan, build_update_plan, print_plan_summary
from scripts.batch.state import BatchItem, BatchState

VAULT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_extraction(title="Test", entities=None, concepts=None, claims=None):
    return SourceExtraction(
        schema_version="1",
        title=title,
        factual_summary="Test summary.",
        entities=entities or [],
        concepts=concepts or [],
        claims=claims or [],
    )


def _write_extraction(batch_dir: Path, source_key: str, extraction: SourceExtraction):
    (batch_dir / "normalized").mkdir(exist_ok=True)
    out = batch_dir / "normalized" / f"{source_key}.json"
    out.write_text(extraction.model_dump_json(indent=2), encoding="utf-8")


def _write_resolution(batch_dir: Path, source_key: str, resolutions: dict):
    (batch_dir / "resolution").mkdir(exist_ok=True)
    out = batch_dir / "resolution" / f"{source_key}.json"
    out.write_text(json.dumps(resolutions, ensure_ascii=False), encoding="utf-8")


# ---------------------------------------------------------------------------
# Grouper tests
# ---------------------------------------------------------------------------

def test_group_evidence_single_source(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("group-test")

    # Create wiki dirs
    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)

    item = BatchItem(
        source_key="meeting-01-abc",
        custom_id="src_meeting_01_abc",
        files=["tests/batch/fixtures/meeting-01-api-gateway.md"],
        sha256="abc",
        status="resolved",
    )
    state.add_item(item)

    extraction = _make_extraction(
        entities=[EntityMention(name="Kong", entity_type="product")],
        concepts=[ConceptMention(name="API Gateway")],
        claims=[Claim(
            text="Kong was selected as the API Gateway.",
            kind="decision",
            locator=Locator(timestamp_start="00:01:00"),
        )],
    )
    _write_extraction(state.batch_dir, "meeting-01-abc", extraction)
    _write_resolution(state.batch_dir, "meeting-01-abc", {
        "kong": {"action": "new", "suggested_slug": "kong", "confidence": "high"},
        "api gateway": {"action": "new", "suggested_slug": "api-gateway", "confidence": "high"},
    })

    groups = group_evidence(state, tmp_path)
    slugs = {g.slug for g in groups}
    assert "api-gateway" in slugs or "kong" in slugs


def test_group_evidence_multiple_sources(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("group-multi")

    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)

    for i in range(3):
        sk = f"meeting-{i:02d}-abc"
        item = BatchItem(
            source_key=sk,
            custom_id=f"src_{sk}",
            files=[f"raw/meeting-{i}.md"],
            sha256=f"hash{i}",
            status="resolved",
        )
        state.add_item(item)
        extraction = _make_extraction(
            concepts=[ConceptMention(name="OAuth")],
            claims=[Claim(
                text=f"OAuth was discussed in meeting {i}.",
                kind="fact",
                locator=Locator(timestamp_start=f"00:0{i}:00"),
            )],
        )
        _write_extraction(state.batch_dir, sk, extraction)
        _write_resolution(state.batch_dir, sk, {
            "oauth": {"action": "new", "suggested_slug": "oauth", "confidence": "high"},
        })

    groups = group_evidence(state, tmp_path)
    oauth_groups = [g for g in groups if g.slug == "oauth"]
    assert len(oauth_groups) == 1  # one group, not three
    assert len(oauth_groups[0].source_keys) == 3


# ---------------------------------------------------------------------------
# Planner tests
# ---------------------------------------------------------------------------

def test_build_update_plan_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("plan-empty")
    plan = build_update_plan(state, tmp_path)
    assert isinstance(plan, UpdatePlan)
    assert plan.batch_id == "plan-empty"


def test_build_update_plan_with_mutation_plans(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("plan-mutations")

    (tmp_path / "wiki" / "concepts").mkdir(parents=True)
    (tmp_path / "wiki" / "entities").mkdir(parents=True)

    # Pre-create curation outputs
    curation_dir = state.batch_dir / "curation"
    curation_dir.mkdir(exist_ok=True)

    create_plan = PageMutationPlan(
        page_type="concept",
        action="create",
        slug="api-gateway",
        title="API Gateway",
        claims_to_add=[ClaimAddition(
            text="Kong is the API Gateway.",
            source_slug="meeting-01",
            source_claim_id="meeting-01:c0000",
        )],
    )
    (curation_dir / "concept_api-gateway.json").write_text(
        create_plan.model_dump_json(), encoding="utf-8"
    )

    conflict_plan = PageMutationPlan(
        page_type="concept",
        action="update",
        slug="api-timeout",
        title="API Timeout",
        conflicts=[Conflict(
            conflict_type="different-data",
            existing_claim="Timeout is 30 seconds.",
            existing_source="meeting-01",
            new_claim="Timeout is 60 seconds.",
            new_source="meeting-05",
            explanation="Different timeout values stated in different meetings.",
        )],
    )
    (curation_dir / "concept_api-timeout.json").write_text(
        conflict_plan.model_dump_json(), encoding="utf-8"
    )

    plan = build_update_plan(state, tmp_path)
    assert plan.concepts["create"] == 1
    assert plan.concepts["update"] == 1
    assert len(plan.conflicts) == 1


def test_print_plan_summary_runs(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("plan-print")
    plan = build_update_plan(state, tmp_path)
    print_plan_summary(plan)
    captured = capsys.readouterr()
    assert "Batch:" in captured.out


# ---------------------------------------------------------------------------
# PageMutationPlan model constraints
# ---------------------------------------------------------------------------

def test_plan_append_only():
    """PageMutationPlan has no delete/replace fields."""
    plan = PageMutationPlan(
        page_type="concept",
        action="update",
        slug="test",
        title="Test",
    )
    plan_dict = plan.model_dump()
    # These destructive operations must not exist in the schema
    assert "delete_claims" not in plan_dict
    assert "replace_page" not in plan_dict
    assert "delete_section" not in plan_dict
    assert "rename_file" not in plan_dict
