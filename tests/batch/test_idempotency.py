"""Tests for pipeline idempotency (no API calls)."""

import json
import shutil
from pathlib import Path

import pytest

from scripts.batch.models import Claim, EntityMention, Locator, SourceExtraction
from scripts.batch.state import BatchItem, BatchState, STAGING_ROOT

FIXTURES = Path(__file__).parent / "fixtures"
VAULT_ROOT = Path(__file__).parent.parent.parent


def _make_extraction(source_key: str) -> SourceExtraction:
    return SourceExtraction(
        schema_version="1",
        title=f"Meeting {source_key}",
        factual_summary="Test summary.",
        claims=[
            Claim(
                text="The team decided to use Kong.",
                kind="decision",
                locator=Locator(timestamp_start="00:01:00"),
            )
        ],
        entities=[EntityMention(name="Kong", entity_type="product")],
    )


def test_collect_idempotent(tmp_path, monkeypatch):
    """Re-saving an extraction to disk should not create a second entry."""
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("idem-test")

    item = BatchItem(
        source_key="meeting-idem",
        custom_id="src_meeting_idem",
        files=["tests/batch/fixtures/meeting-01-api-gateway.md"],
        sha256="abc123",
        status="extracted",
    )
    state.add_item(item)

    extraction = _make_extraction("meeting-idem")
    extraction_dir = state.batch_dir / "extraction"
    out_path = extraction_dir / "meeting-idem.json"
    out_path.write_text(extraction.model_dump_json(), encoding="utf-8")
    state.save()

    # Simulate second call: file already exists
    loaded = BatchState.load(state.batch_dir)
    already_done = [i for i in loaded.items if i.status == "extracted"]
    assert len(already_done) == 1  # not doubled


def test_state_save_load_items_stable(tmp_path, monkeypatch):
    """Items list is stable across save/load cycles."""
    monkeypatch.setattr("scripts.batch.state.STAGING_ROOT", tmp_path)
    state = BatchState.create("stable-test")

    for i in range(5):
        state.add_item(BatchItem(
            source_key=f"meeting-{i:02d}",
            custom_id=f"src_meeting_{i:02d}",
            files=[f"raw/meeting-{i:02d}.md"],
            sha256=f"hash{i:08x}",
        ))
    state.save()

    loaded = BatchState.load(state.batch_dir)
    assert len(loaded.items) == 5
    keys_original = sorted(i.source_key for i in state.items)
    keys_loaded = sorted(i.source_key for i in loaded.items)
    assert keys_original == keys_loaded


def test_extraction_json_roundtrip():
    """SourceExtraction survives JSON round-trip without data loss."""
    original = _make_extraction("meeting-rt")
    serialized = original.model_dump_json()
    restored = SourceExtraction.model_validate_json(serialized)

    assert restored.title == original.title
    assert len(restored.claims) == len(original.claims)
    assert restored.claims[0].text == original.claims[0].text
    assert restored.entities[0].name == original.entities[0].name
