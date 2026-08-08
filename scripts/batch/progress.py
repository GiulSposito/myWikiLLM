"""
Simple incremental progress output for batch ingest scripts.

Works in both TTY terminals and captured output (Claude Code tool calls),
since it uses only plain Unicode — no ANSI escape codes, no carriage returns.

Each call to .step() emits one new line, producing a readable incremental log.
"""

from __future__ import annotations

import sys


_BAR_WIDTH = 10
_FILL = "█"
_EMPTY = "░"

# Ordered pipeline stages — name must match the label passed to pipeline_header()
PIPELINE_STAGES = ["Scan", "Extract", "Normalize", "Resolve", "Curate", "Plan", "Apply"]


def pipeline_header(current: str, file=None) -> None:
    """
    Print a one-line pipeline status banner showing which stage is active.

    Example output:
        ──────────────────────────────────────────────────────────────────
          ✓ Scan  │  ▶ Extract  │  ○ Normalize  │  ○ Resolve  │  ○ Curate  │  ○ Plan  │  ○ Apply
        ──────────────────────────────────────────────────────────────────
    """
    f = file or sys.stdout
    current_idx = next(
        (i for i, s in enumerate(PIPELINE_STAGES) if s.lower() == current.lower()),
        -1,
    )
    parts = []
    for i, stage in enumerate(PIPELINE_STAGES):
        if i < current_idx:
            parts.append(f"✓ {stage}")
        elif i == current_idx:
            parts.append(f"▶ {stage}")
        else:
            parts.append(f"○ {stage}")
    line = "  " + "  │  ".join(parts)
    sep = "─" * max(len(line), 60)
    print(sep, file=f, flush=True)
    print(line, file=f, flush=True)
    print(sep, file=f, flush=True)


def _bar(current: int, total: int) -> str:
    if total <= 0:
        return _FILL * _BAR_WIDTH
    filled = round(_BAR_WIDTH * current / total)
    return _FILL * filled + _EMPTY * (_BAR_WIDTH - filled)


class Progress:
    """
    Emits one line per item processed.

    Usage:
        p = Progress("Extracting", total=10)
        for i, item in enumerate(items, 1):
            # ... do work ...
            p.step(i, label=item.name)
        p.done("10 extracted, 0 failed")
    """

    def __init__(self, phase: str, total: int, file=None) -> None:
        self.phase = phase
        self.total = total
        self._file = file or sys.stdout

    def step(self, current: int, label: str = "", detail: str = "") -> None:
        bar = _bar(current, self.total)
        width = len(str(self.total))
        counter = f"{current:{width}}/{self.total}"
        parts = [f"  {counter} {bar}"]
        if label:
            parts.append(f"  {label}")
        if detail:
            parts.append(f"  ({detail})")
        print("".join(parts), file=self._file, flush=True)

    def info(self, msg: str) -> None:
        print(f"  → {msg}", file=self._file, flush=True)

    def warn(self, msg: str) -> None:
        print(f"  ! {msg}", file=self._file, flush=True)

    def fail(self, label: str, reason: str = "") -> None:
        line = f"  ✗ {label}"
        if reason:
            line += f"  — {reason}"
        print(line, file=self._file, flush=True)

    def done(self, summary: str = "") -> None:
        line = f"✓ {self.phase}"
        if summary:
            line += f": {summary}"
        print(line, file=self._file, flush=True)

    def error(self, summary: str = "") -> None:
        line = f"✗ {self.phase}"
        if summary:
            line += f": {summary}"
        print(line, file=self._file, flush=True)
