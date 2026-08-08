"""
BatchState: manages staging/<batch>/manifest.yml lifecycle.

Responsibilities:
- Create a new batch directory under staging/
- Load an existing batch from disk
- Track per-item status transitions
- Save state atomically (write-then-rename)
"""

from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import yaml
except ImportError as exc:
    raise ImportError("pyyaml is required") from exc

VAULT_ROOT = Path(__file__).parent.parent.parent
STAGING_ROOT = VAULT_ROOT / "staging"


@dataclass
class BatchItem:
    source_key: str
    custom_id: str
    files: list[str]
    sha256: str
    status: str = "scanned"
    duplicate_of: str | None = None
    provider_batch_id: str | None = None
    retry_count: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        d: dict[str, Any] = {
            "source_key": self.source_key,
            "custom_id": self.custom_id,
            "files": self.files,
            "sha256": self.sha256,
            "status": self.status,
        }
        if self.duplicate_of:
            d["duplicate_of"] = self.duplicate_of
        if self.provider_batch_id:
            d["provider_batch_id"] = self.provider_batch_id
        if self.retry_count:
            d["retry_count"] = self.retry_count
        if self.error:
            d["error"] = self.error
        return d

    @classmethod
    def from_dict(cls, d: dict) -> "BatchItem":
        return cls(
            source_key=d["source_key"],
            custom_id=d["custom_id"],
            files=d.get("files", []),
            sha256=d["sha256"],
            status=d.get("status", "scanned"),
            duplicate_of=d.get("duplicate_of"),
            provider_batch_id=d.get("provider_batch_id"),
            retry_count=d.get("retry_count", 0),
            error=d.get("error"),
        )


@dataclass
class BatchState:
    batch_id: str
    batch_dir: Path
    created_at: str = ""
    baseline_git_head: str = ""
    extraction_model: str = "claude-haiku-4-5-20251001"
    resolution_model: str = "claude-sonnet-5"
    curation_model: str = "claude-sonnet-5"
    provider_batches: dict[str, list[str]] = field(default_factory=lambda: {
        "extraction": [], "resolution": [], "curation": []
    })
    items: list[BatchItem] = field(default_factory=list)

    # ------------------------------------------------------------------ #
    # Factory methods
    # ------------------------------------------------------------------ #

    @classmethod
    def create(
        cls,
        batch_id: str,
        extraction_model: str = "claude-haiku-4-5-20251001",
        resolution_model: str = "claude-sonnet-5",
        curation_model: str = "claude-sonnet-5",
    ) -> "BatchState":
        batch_dir = STAGING_ROOT / batch_id
        batch_dir.mkdir(parents=True, exist_ok=True)
        for sub in ("requests", "extraction", "normalized", "resolution",
                    "grouped", "curation", "errors"):
            (batch_dir / sub).mkdir(exist_ok=True)

        state = cls(
            batch_id=batch_id,
            batch_dir=batch_dir,
            created_at=datetime.now(timezone.utc).isoformat(),
            baseline_git_head=_git_head(),
            extraction_model=extraction_model,
            resolution_model=resolution_model,
            curation_model=curation_model,
        )
        state.save()
        return state

    @classmethod
    def load(cls, batch_dir: Path) -> "BatchState":
        manifest_path = batch_dir / "manifest.yml"
        if not manifest_path.exists():
            raise FileNotFoundError(f"No manifest.yml in {batch_dir}")

        raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
        models = raw.get("models", {})
        provider_batches = raw.get("provider_batches", {
            "extraction": [], "resolution": [], "curation": []
        })

        state = cls(
            batch_id=raw["batch_id"],
            batch_dir=batch_dir,
            created_at=raw.get("created_at", ""),
            baseline_git_head=raw.get("baseline", {}).get("git_head", ""),
            extraction_model=models.get("extraction", "claude-haiku-4-5-20251001"),
            resolution_model=models.get("resolution", "claude-sonnet-5"),
            curation_model=models.get("curation", "claude-sonnet-5"),
            provider_batches=provider_batches,
        )
        state.items = [BatchItem.from_dict(i) for i in raw.get("items", [])]
        return state

    # ------------------------------------------------------------------ #
    # Persistence
    # ------------------------------------------------------------------ #

    def save(self) -> None:
        stats = self._compute_stats()
        data: dict[str, Any] = {
            "schema_version": "1",
            "batch_id": self.batch_id,
            "created_at": self.created_at,
            "baseline": {"git_head": self.baseline_git_head},
            "models": {
                "extraction": self.extraction_model,
                "resolution": self.resolution_model,
                "curation": self.curation_model,
            },
            "provider_batches": self.provider_batches,
            "items": [i.to_dict() for i in self.items],
            "statistics": stats,
        }
        manifest_path = self.batch_dir / "manifest.yml"
        tmp_path = manifest_path.with_suffix(".yml.tmp")
        tmp_path.write_text(
            yaml.dump(data, allow_unicode=True, sort_keys=False),
            encoding="utf-8",
        )
        tmp_path.replace(manifest_path)

    # ------------------------------------------------------------------ #
    # Item management
    # ------------------------------------------------------------------ #

    def add_item(self, item: BatchItem) -> None:
        self.items.append(item)

    def get_item(self, source_key: str) -> BatchItem | None:
        for item in self.items:
            if item.source_key == source_key:
                return item
        return None

    def update_status(self, source_key: str, status: str, **kwargs) -> None:
        item = self.get_item(source_key)
        if item is None:
            raise KeyError(f"Item not found: {source_key}")
        item.status = status
        for k, v in kwargs.items():
            setattr(item, k, v)

    def items_by_status(self, *statuses: str) -> list[BatchItem]:
        return [i for i in self.items if i.status in statuses]

    # ------------------------------------------------------------------ #
    # Statistics
    # ------------------------------------------------------------------ #

    def _compute_stats(self) -> dict:
        counts: dict[str, int] = {}
        for item in self.items:
            counts[item.status] = counts.get(item.status, 0) + 1
        return {
            "discovered": len(self.items),
            "skipped_duplicate": counts.get("skipped_duplicate", 0),
            "extracted": counts.get("extracted", 0),
            "failed": counts.get("failed_extraction", 0),
            "applied": counts.get("applied", 0),
        }

    def summary(self) -> dict:
        return self._compute_stats()


# ------------------------------------------------------------------ #
# Helpers
# ------------------------------------------------------------------ #

def _git_head() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=VAULT_ROOT,
        )
        return result.stdout.strip() if result.returncode == 0 else ""
    except Exception:
        return ""


def make_batch_id(directory: Path) -> str:
    """Generate a deterministic batch_id from date + directory name."""
    today = datetime.now(timezone.utc).strftime("%Y%m%d")
    slug = re.sub(r"[^a-z0-9]+", "-", directory.name.lower()).strip("-")
    return f"{today}-{slug}"
