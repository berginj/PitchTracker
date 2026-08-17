"""Run mypy and prevent the unchecked type-error backlog from growing.

The repository is not yet ready for a clean whole-tree mypy run.  This small
ratchet keeps that debt explicit while allowing incremental fixes: an update
may remove existing diagnostics, but a normal check fails if it introduces a
new diagnostic.  Error locations intentionally omit line numbers so harmless
line movement does not create baseline churn.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "mypy-baseline.txt"
ERROR_RE = re.compile(
    r"^(?P<path>.+?):\d+: error: (?P<message>.+)$",
)


def _diagnostics(output: str) -> list[str]:
    diagnostics: list[str] = []
    for line in output.splitlines():
        match = ERROR_RE.match(line.strip())
        if match is None:
            continue
        path = match.group("path").replace("\\", "/")
        diagnostics.append(f"{path}: error: {match.group('message')}")
    return diagnostics


def _run_mypy() -> tuple[int, list[str]]:
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mypy",
            ".",
            "--no-incremental",
            "--show-error-codes",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    output = f"{result.stdout}\n{result.stderr}"
    return result.returncode, _diagnostics(output)


def _read_baseline() -> list[str]:
    if not BASELINE.exists():
        return []
    return [line for line in BASELINE.read_text(encoding="utf-8").splitlines() if line]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--update",
        action="store_true",
        help="replace the checked-in baseline with the current diagnostics",
    )
    args = parser.parse_args()

    mypy_exit, current = _run_mypy()
    if mypy_exit not in (0, 1):
        print(f"mypy failed to run (exit {mypy_exit})", file=sys.stderr)
        return mypy_exit

    current = sorted(current)
    if args.update:
        BASELINE.write_text("\n".join(current) + "\n", encoding="utf-8")
        print(f"Updated {BASELINE.relative_to(ROOT)} with {len(current)} diagnostics.")
        return 0

    baseline = _read_baseline()
    new = list((Counter(current) - Counter(baseline)).elements())
    resolved = list((Counter(baseline) - Counter(current)).elements())
    print(f"mypy baseline: {len(current)} diagnostics ({len(resolved)} resolved)")
    if new:
        print("New mypy diagnostics:", file=sys.stderr)
        print("\n".join(new), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
