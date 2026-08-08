"""Tests for dedup rules and scan idempotency."""

import shutil
from pathlib import Path

import pytest
import yaml

from scripts.batch.scanner import scan_directory, sha256_file
from scripts.batch.state import BatchState, make_batch_id, STAGING_ROOT, VAULT_ROOT

FIXTURES = Path(__file__).parent / "fixtures"
SOURCES_MANIFEST = VAULT_ROOT / "manifests" / "sources.yml"


def _make_sources_yml(tmp_path, entries):
    sources_path = tmp_path / "sources.yml"
    sources_path.write_text(
        yaml.dump({"sources": entries}, allow_unicode=True),
        encoding="utf-8",
    )
    return sources_path


# ---------------------------------------------------------------------------
# Rule 1: same path + same hash → skip
# ---------------------------------------------------------------------------

def test_rule1_same_path_same_hash(tmp_path, monkeypatch):
    f = tmp_path / "meeting.md"
    f.write_text("Hello world")
    h = sha256_file(f)

    manifest = _make_sources_yml(tmp_path, [{
        "slug": "meeting-abc12345",
        "raw_path": str(f),
        "sha256": h,
    }])
    monkeypatch.setattr("scripts.batch.scanner.SOURCES_MANIFEST", manifest)

    results = scan_directory(tmp_path)
    assert len(results) == 1
    assert results[0].status == "skipped_duplicate"
    assert results[0].duplicate_of == "meeting-abc12345"


# ---------------------------------------------------------------------------
# Rule 2: different path + same hash → skip
# ---------------------------------------------------------------------------

def test_rule2_different_path_same_hash(tmp_path, monkeypatch):
    f1 = tmp_path / "original.md"
    f2 = tmp_path / "copy.md"
    f1.write_text("Identical content")
    f2.write_text("Identical content")
    h = sha256_file(f1)

    manifest = _make_sources_yml(tmp_path, [{
        "slug": "original-slug",
        "raw_path": str(f1),
        "sha256": h,
    }])
    monkeypatch.setattr("scripts.batch.scanner.SOURCES_MANIFEST", manifest)

    # Only scan f2's parent but f1 is known
    scan_dir = tmp_path
    results = scan_directory(scan_dir)
    by_name = {r.path.name: r for r in results}

    assert by_name["copy.md"].status == "skipped_duplicate"
    assert by_name["copy.md"].duplicate_of == "original-slug"


# ---------------------------------------------------------------------------
# Rule 3: same path + different hash → changed-source
# ---------------------------------------------------------------------------

def test_rule3_changed_source_blocked(tmp_path, monkeypatch):
    f = tmp_path / "meeting.md"
    f.write_text("New content")

    manifest = _make_sources_yml(tmp_path, [{
        "slug": "meeting-old",
        "raw_path": str(f),
        "sha256": "00000000deadbeef" * 4,  # old hash
    }])
    monkeypatch.setattr("scripts.batch.scanner.SOURCES_MANIFEST", manifest)

    results = scan_directory(tmp_path, reingest_changed=False)
    assert results[0].status == "changed-source"


def test_rule3_changed_source_allowed_with_flag(tmp_path, monkeypatch):
    f = tmp_path / "meeting.md"
    f.write_text("New content")

    manifest = _make_sources_yml(tmp_path, [{
        "slug": "meeting-old",
        "raw_path": str(f),
        "sha256": "00000000deadbeef" * 4,
    }])
    monkeypatch.setattr("scripts.batch.scanner.SOURCES_MANIFEST", manifest)

    results = scan_directory(tmp_path, reingest_changed=True)
    assert results[0].status == "scanned"


# ---------------------------------------------------------------------------
# Idempotency: scanning twice yields same result
# ---------------------------------------------------------------------------

def test_scan_idempotent(tmp_path):
    shutil.copytree(FIXTURES, tmp_path / "fixtures")
    r1 = scan_directory(tmp_path / "fixtures")
    r2 = scan_directory(tmp_path / "fixtures")
    keys1 = sorted(r.source_key for r in r1)
    keys2 = sorted(r.source_key for r in r2)
    assert keys1 == keys2


# ---------------------------------------------------------------------------
# BatchState: create / load round-trip
# ---------------------------------------------------------------------------

def test_state_create_load_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("test-batch-20260807")
    assert (tmp_path / "test-batch-20260807" / "manifest.yml").exists()

    loaded = BatchState.load(tmp_path / "test-batch-20260807")
    assert loaded.batch_id == "test-batch-20260807"


def test_state_item_status_transitions(tmp_path, monkeypatch):
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("status-test")

    from scripts.batch.state import BatchItem
    item = BatchItem(
        source_key="meeting-abc",
        custom_id="src_meeting_abc",
        files=["raw/meeting.md"],
        sha256="abc123",
    )
    state.add_item(item)
    state.update_status("meeting-abc", "extracted")
    state.save()

    loaded = BatchState.load(tmp_path / "status-test")
    assert loaded.get_item("meeting-abc").status == "extracted"
