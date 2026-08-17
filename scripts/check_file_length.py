"""Enforce the repository's 500-line-per-file convention in CI.

The repo convention (see .github/copilot-instructions.md) caps Python files at
500 lines. This guard fails when a *new* file crosses that limit so the rule is
self-enforcing instead of aspirational.

Existing oversized files are grandfathered in ``ALLOWLIST`` as known tech debt.
The guard also fails if an allowlisted file drops to <=500 lines (or is deleted)
so the debt list shrinks as files are split and never goes stale.

Usage::

    python scripts/check_file_length.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

MAX_LINES = 500

# Directories excluded from the check (vendored, generated, or build output).
EXCLUDED_PREFIXES = (
    "archive/",
    "contracts-shared/examples/",
)

# Grandfathered files that already exceed MAX_LINES. New entries require a
# tracked extraction issue; see GitHub issue #12 for the July 2026 baseline.
# Remove an entry once the file is brought under MAX.
ALLOWLIST: dict[str, int] = {
}

ROOT = Path(__file__).resolve().parents[1]


def _tracked_py_files() -> list[str]:
    out = subprocess.run(
        ["git", "ls-files", "*.py"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    ).stdout
    files = [
        line.strip()
        for line in out.splitlines()
        if line.strip() and (ROOT / line.strip()).exists()
    ]
    return [f for f in files if not f.startswith(EXCLUDED_PREFIXES)]


def _line_count(rel_path: str) -> int:
    with (ROOT / rel_path).open("r", encoding="utf-8", errors="replace") as handle:
        return sum(1 for _ in handle)


def main() -> int:
    new_violations: list[tuple[str, int]] = []
    resolved: list[str] = []

    tracked = set(_tracked_py_files())
    for rel in sorted(tracked):
        count = _line_count(rel)
        if count > MAX_LINES and rel not in ALLOWLIST:
            new_violations.append((rel, count))

    for rel in sorted(ALLOWLIST):
        if rel not in tracked or _line_count(rel) <= MAX_LINES:
            resolved.append(rel)

    if new_violations:
        print(f"ERROR: files exceeding {MAX_LINES} lines (split them or extract modules):")
        for rel, count in new_violations:
            print(f"  {count:>5}  {rel}")

    if resolved:
        print("ERROR: allowlisted files are now within the limit -- remove them from")
        print("       ALLOWLIST in scripts/check_file_length.py:")
        for rel in resolved:
            print(f"  {rel}")

    if new_violations or resolved:
        return 1

    print(f"OK: no Python file exceeds {MAX_LINES} lines (excluding {len(ALLOWLIST)} grandfathered).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
