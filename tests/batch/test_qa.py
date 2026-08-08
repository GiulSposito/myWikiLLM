"""Tests for qa.py: blocking checks and sampling."""

import json
from pathlib import Path

import pytest

from scripts.batch.config import load_config
from scripts.batch.models import (
    Claim,
    ClaimAddition,
    Conflict,
    EntityMention,
    Locator,
    PageMutationPlan,
    SourceExtraction,
)
from scripts.batch.planner import UpdatePlan
from scripts.batch.qa import (
    generate_qa_report,
    run_qa_checks,
    sample_sources,
)
from scripts.batch.state import BatchItem, BatchState

VAULT_ROOT = Path(__file__).parent.parent.parent


# ---------------------------------------------------------------------------
# Sampling
# ---------------------------------------------------------------------------

def test_sample_deterministic():
    keys = [f"meeting-{i:02d}" for i in range(50)]
    s1 = sample_sources(keys, rate=0.10, min_size=5, max_size=20)
    s2 = sample_sources(keys, rate=0.10, min_size=5, max_size=20)
    assert s1 == s2


def test_sample_respects_min_size():
    keys = [f"meeting-{i:02d}" for i in range(10)]
    sample = sample_sources(keys, rate=0.10, min_size=5, max_size=100)
    assert len(sample) >= 5


def test_sample_respects_max_size():
    keys = [f"meeting-{i:02d}" for i in range(1000)]
    sample = sample_sources(keys, rate=0.50, min_size=5, max_size=100)
    assert len(sample) <= 100


# ---------------------------------------------------------------------------
# Blocking checks: valid batch passes
# ---------------------------------------------------------------------------

def _write_extraction(extraction_dir: Path, source_key: str, extraction: SourceExtraction):
    extraction_dir.mkdir(parents=True, exist_ok=True)
    (extraction_dir / f"{source_key}.json").write_text(
        extraction.model_dump_json(), encoding="utf-8"
    )


def test_qa_passes_clean_batch(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("qa-clean")

    item = BatchItem(
        source_key="meeting-01-abc",
        custom_id="src_meeting_01_abc",
        files=["raw/meeting-01.md"],
        sha256="abc",
        status="extracted",
    )
    state.add_item(item)

    extraction = SourceExtraction(
        schema_version="1",
        title="Test",
        factual_summary="Summary.",
        claims=[Claim(
            text="The team decided to use Kong.",
            kind="decision",
            locator=Locator(timestamp_start="00:01:00"),
        )],
    )
    _write_extraction(state.batch_dir / "extraction", "meeting-01-abc", extraction)

    plan = UpdatePlan(batch_id="qa-clean")
    ok, report = run_qa_checks(plan, state, tmp_path)
    assert ok, f"QA should pass: {report}"


# ---------------------------------------------------------------------------
# Blocking checks: failures
# ---------------------------------------------------------------------------

def test_qa_fails_on_unresolved_extraction_error(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("qa-fail-err")

    item = BatchItem(
        source_key="meeting-fail",
        custom_id="src_meeting_fail",
        files=["raw/meeting-fail.md"],
        sha256="abc",
        status="failed_extraction",
        error="server_error",
    )
    state.add_item(item)

    plan = UpdatePlan(batch_id="qa-fail-err")
    ok, report = run_qa_checks(plan, state, tmp_path)
    assert not ok
    assert "Unresolved extraction failures" in report


def test_qa_warns_critical_claim_missing_locator(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("qa-warn-loc")

    item = BatchItem(
        source_key="meeting-noloc",
        custom_id="src_meeting_noloc",
        files=["raw/meeting.md"],
        sha256="abc",
        status="extracted",
    )
    state.add_item(item)

    extraction = SourceExtraction(
        schema_version="1",
        title="Test",
        factual_summary="Summary.",
        claims=[Claim(
            text="The timeout was set to 30 seconds.",
            kind="requirement",  # critical kind
            locator=Locator(),  # no locator
        )],
    )
    _write_extraction(state.batch_dir / "extraction", "meeting-noloc", extraction)

    plan = UpdatePlan(batch_id="qa-warn-loc")
    ok, report = run_qa_checks(plan, state, tmp_path)
    # Critical claim missing locator → error (not just warning)
    assert not ok
    assert "Critical claim locator rate" in report


def test_qa_fails_on_invalid_mutation_plan(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("qa-fail-plan")

    plan = UpdatePlan(
        batch_id="qa-fail-plan",
        files=[{
            "path": "wiki/concepts/test.md",
            "action": "create",
            "baseline_sha256": "",
            "mutation_plan": {
                "page_type": "invalid_type",  # invalid
                "action": "create",
                "slug": "test",
                "title": "Test",
            },
        }],
    )
    ok, report = run_qa_checks(plan, state, tmp_path)
    assert not ok
    assert "invalid_type" in report or "page_type" in report


# ---------------------------------------------------------------------------
# QA report generation
# ---------------------------------------------------------------------------

def test_generate_qa_report_creates_file(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("qa-report")

    item = BatchItem(
        source_key="meeting-01-abc",
        custom_id="src_m01",
        files=["raw/meeting-01.md"],
        sha256="abc",
        status="extracted",
    )
    state.add_item(item)

    extraction = SourceExtraction(
        schema_version="1",
        title="Test Meeting",
        factual_summary="Summary.",
        claims=[Claim(
            text="Fact A.",
            kind="fact",
            locator=Locator(timestamp_start="00:01:00"),
        )],
    )
    _write_extraction(state.batch_dir / "extraction", "meeting-01-abc", extraction)

    cfg = load_config()
    cfg.quality.min_sample_size = 1  # force at least one sample
    plan = UpdatePlan(batch_id="qa-report")

    report_path = generate_qa_report(plan, state, tmp_path, cfg)
    assert Path(report_path).exists()
    content = Path(report_path).read_text()
    assert "Batch Ingest QA Report" in content
