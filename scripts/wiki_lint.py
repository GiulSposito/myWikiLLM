#!/usr/bin/env python3
"""
wiki_lint.py — orquestrador paralelo do wiki-lint.

Lança validate_frontmatter, validate_links e find_orphans em paralelo,
coleta outputs em ordem e retorna exit code combinado (1 se qualquer um falhar).

Uso:
  python3 scripts/wiki_lint.py
"""

import subprocess
import sys
from pathlib import Path

VAULT_ROOT = Path(__file__).parent.parent
SCRIPTS = [
    "validate_frontmatter.py",
    "validate_links.py",
    "find_orphans.py",
]


def main() -> int:
    procs = [
        subprocess.Popen(
            [sys.executable, str(VAULT_ROOT / "scripts" / script)],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            cwd=VAULT_ROOT,
        )
        for script in SCRIPTS
    ]

    combined_rc = 0
    for script, proc in zip(SCRIPTS, procs):
        out, _ = proc.communicate()
        print(f"── {script} ──")
        print(out, end="" if out.endswith("\n") else "\n")
        if proc.returncode != 0:
            combined_rc = 1

    return combined_rc


if __name__ == "__main__":
    sys.exit(main())
