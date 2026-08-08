"""
Scanner: discover transcripts, compute SHA256, apply dedup rules.

Dedup rules (spec §7):
  Rule 1 — same path + same hash   → skip
  Rule 2 — different path + same hash → skip, record duplicate_of
  Rule 3 — same path + different hash → changed-source (requires --reingest-changed)
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

try:
    import yaml
except ImportError as exc:
    raise ImportError("pyyaml is required") from exc

VAULT_ROOT = Path(__file__).parent.parent.parent
SOURCES_MANIFEST = VAULT_ROOT / "manifests" / "sources.yml"
TRANSCRIPT_EXTENSIONS = {".md", ".txt", ".vtt", ".srt"}


# ---------------------------------------------------------------------------
# Source identity
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def slugify(text: str) -> str:
    text = text.lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")[:60]


def make_source_key(path: Path, sha256: str) -> str:
    """slug-shorthash, e.g. architecture-weekly-a821e682"""
    short = sha256[:8]
    return f"{slugify(path.stem)}-{short}"


def make_custom_id(source_key: str) -> str:
    """Anthropic custom_id: alphanumeric + _ - , max 64 chars."""
    safe = re.sub(r"[^a-zA-Z0-9_-]", "_", source_key)
    return f"src_{safe}"[:64]


# ---------------------------------------------------------------------------
# Existing sources index
# ---------------------------------------------------------------------------

@dataclass
class KnownSource:
    slug: str
    raw_path: str | None
    sha256: str | None


def load_known_sources() -> list[KnownSource]:
    if not SOURCES_MANIFEST.exists():
        return []
    raw = yaml.safe_load(SOURCES_MANIFEST.read_text(encoding="utf-8")) or {}
    sources = raw.get("sources") or []
    result = []
    for s in sources:
        if not isinstance(s, dict):
            continue
        result.append(KnownSource(
            slug=s.get("slug", ""),
            raw_path=s.get("raw_path") or s.get("path"),
            sha256=s.get("sha256"),
        ))
    return result


# ---------------------------------------------------------------------------
# Scan result
# ---------------------------------------------------------------------------

@dataclass
class ScanResult:
    path: Path
    source_key: str
    custom_id: str
    sha256: str
    status: str   # scanned | skipped_duplicate | changed-source
    duplicate_of: str | None = None


def scan_directory(
    directory: Path,
    reingest_changed: bool = False,
) -> list[ScanResult]:
    """Discover transcript files and classify each against existing sources."""
    known = load_known_sources()

    by_hash: dict[str, KnownSource] = {}
    by_path: dict[str, KnownSource] = {}
    for ks in known:
        if ks.sha256:
            by_hash[ks.sha256] = ks
        if ks.raw_path:
            by_path[str(Path(ks.raw_path).resolve())] = ks

    results: list[ScanResult] = []
    seen_hashes: dict[str, str] = {}  # hash → source_key in this scan

    files = sorted(
        p for p in directory.rglob("*")
        if p.is_file() and p.suffix.lower() in TRANSCRIPT_EXTENSIONS
    )

    for path in files:
        h = sha256_file(path)
        source_key = make_source_key(path, h)
        custom_id = make_custom_id(source_key)
        abs_path_str = str(path.resolve())

        # Check if already in sources.yml
        known_by_hash = by_hash.get(h)
        known_by_path = by_path.get(abs_path_str)

        if known_by_hash and known_by_path and known_by_hash.slug == known_by_path.slug:
            # Rule 1: same path + same hash → skip
            status = "skipped_duplicate"
            duplicate_of = known_by_hash.slug
        elif known_by_hash and not known_by_path:
            # Rule 2: different path, same hash → skip as duplicate
            status = "skipped_duplicate"
            duplicate_of = known_by_hash.slug
        elif known_by_path and not known_by_hash:
            # Rule 3: same path, different hash → changed source
            if reingest_changed:
                status = "scanned"
                duplicate_of = None
            else:
                status = "changed-source"
                duplicate_of = None
        elif h in seen_hashes:
            # Duplicate within this batch
            status = "skipped_duplicate"
            duplicate_of = seen_hashes[h]
        else:
            status = "scanned"
            duplicate_of = None

        if status == "scanned":
            seen_hashes[h] = source_key

        results.append(ScanResult(
            path=path,
            source_key=source_key,
            custom_id=custom_id,
            sha256=h,
            status=status,
            duplicate_of=duplicate_of,
        ))

    return results


# ---------------------------------------------------------------------------
# Line-number injector (for .md/.txt without timestamps)
# ---------------------------------------------------------------------------

def inject_line_numbers(text: str) -> str:
    """Prefix each line with L<6-digit-number> without modifying raw/."""
    lines = text.splitlines(keepends=True)
    numbered = []
    for i, line in enumerate(lines, start=1):
        numbered.append(f"L{i:06d} {line}")
    return "".join(numbered)


def has_timestamps(text: str) -> bool:
    """Heuristic: does the transcript contain HH:MM:SS style timestamps?"""
    ts_pattern = re.compile(r"\b\d{1,2}:\d{2}:\d{2}\b")
    sample = text[:5000]
    return bool(ts_pattern.search(sample))


def prepare_transcript(path: Path) -> str:
    """Return transcript content ready for LLM extraction."""
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() in (".vtt", ".srt"):
        return text  # already has timestamps
    if has_timestamps(text):
        return text
    return inject_line_numbers(text)
