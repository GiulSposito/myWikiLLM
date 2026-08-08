"""Tests for scanner.py: discovery, SHA256, dedup rules."""

import shutil
import tempfile
from pathlib import Path

import pytest

from scripts.batch.scanner import (
    has_timestamps,
    inject_line_numbers,
    make_custom_id,
    make_source_key,
    prepare_transcript,
    scan_directory,
    sha256_file,
    slugify,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# Unit: slugify / make_source_key / make_custom_id
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert slugify("Architecture Weekly") == "architecture-weekly"


def test_slugify_special_chars():
    assert slugify("Meeting #5: Q3/2026") == "meeting-5-q3-2026"


def test_make_source_key_format():
    key = make_source_key(Path("raw/transcripts/meeting-001.md"), "a821e682abcdef")
    assert key.startswith("meeting-001-")
    assert len(key.split("-")[-1]) == 8


def test_make_custom_id_valid():
    key = "architecture-weekly-a821e682"
    cid = make_custom_id(key)
    assert cid.startswith("src_")
    assert len(cid) <= 64
    import re
    assert re.match(r"^[a-zA-Z0-9_-]+$", cid)


# ---------------------------------------------------------------------------
# Unit: SHA256
# ---------------------------------------------------------------------------

def test_sha256_deterministic(tmp_path):
    f = tmp_path / "test.md"
    f.write_text("hello world")
    h1 = sha256_file(f)
    h2 = sha256_file(f)
    assert h1 == h2
    assert len(h1) == 64


def test_sha256_differs_for_different_content(tmp_path):
    f1 = tmp_path / "a.md"
    f2 = tmp_path / "b.md"
    f1.write_text("hello")
    f2.write_text("world")
    assert sha256_file(f1) != sha256_file(f2)


# ---------------------------------------------------------------------------
# Unit: line number injection
# ---------------------------------------------------------------------------

def test_inject_line_numbers():
    text = "first line\nsecond line\nthird line"
    result = inject_line_numbers(text)
    lines = result.splitlines()
    assert lines[0].startswith("L000001 first line")
    assert lines[1].startswith("L000002 second line")
    assert lines[2].startswith("L000003 third line")


def test_has_timestamps_true():
    text = "00:01:23 Alice: Hello\n00:01:45 Bob: World"
    assert has_timestamps(text)


def test_has_timestamps_false():
    text = "Alice: Hello\nBob: World"
    assert not has_timestamps(text)


def test_prepare_transcript_with_timestamps():
    path = FIXTURES / "meeting-01-api-gateway.md"
    result = prepare_transcript(path)
    assert "00:01:23" in result
    assert not result.startswith("L")


def test_prepare_transcript_without_timestamps():
    path = FIXTURES / "meeting-07-rag-alias.md"
    result = prepare_transcript(path)
    # Already line-numbered in the fixture
    assert "L000001" in result


# ---------------------------------------------------------------------------
# Integration: scan_directory
# ---------------------------------------------------------------------------

def test_scan_discovers_all_fixtures():
    results = scan_directory(FIXTURES)
    names = {r.path.name for r in results}
    assert "meeting-01-api-gateway.md" in names
    assert len(results) == 10  # 9 unique + 1 duplicate


def test_scan_detects_duplicate_file():
    results = scan_directory(FIXTURES)
    by_name = {r.path.name: r for r in results}
    dup = by_name.get("meeting-10-rag-duplicate.md")
    assert dup is not None
    assert dup.status == "skipped_duplicate"
    assert dup.duplicate_of is not None


def test_scan_unique_custom_ids():
    results = scan_directory(FIXTURES)
    cids = [r.custom_id for r in results]
    assert len(cids) == len(set(cids))


def test_scan_scanned_count():
    results = scan_directory(FIXTURES)
    scanned = [r for r in results if r.status == "scanned"]
    assert len(scanned) == 9
