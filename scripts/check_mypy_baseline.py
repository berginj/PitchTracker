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
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASELINE = ROOT / "mypy-baseline.txt"
ERROR_RE = re.compile(
    r"^(?P<path>.+?):\d+: error: (?P<message>.+)$",
)
CODE_RE = re.compile(r"\[(?P<code>[a-z0-9-]+)\]$")


@dataclass(frozen=True, order=True)
class Diagnostic:
    """Stable mypy diagnostic identity with line-number churn removed."""

    path: str
    message: str
    code: str

    @property
    def baseline_line(self) -> str:
        return f"{self.path}: error: {self.message}"


def _diagnostics(output: str) -> list[Diagnostic]:
    diagnostics: list[Diagnostic] = []
    for line in output.splitlines():
        match = ERROR_RE.match(line.strip())
        if match is None:
            continue
        path = match.group("path").replace("\\", "/")
        message = match.group("message")
        code_match = CODE_RE.search(message)
        diagnostics.append(
            Diagnostic(path, message, code_match.group("code") if code_match else "unknown")
        )
    return diagnostics


def _run_mypy() -> tuple[int, list[Diagnostic]]:
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


def _read_baseline() -> list[Diagnostic]:
    if not BASELINE.exists():
        return []
    diagnostics: list[Diagnostic] = []
    for line in BASELINE.read_text(encoding="utf-8").splitlines():
        if not line:
            continue
        path, marker, message = line.partition(": error: ")
        if not marker:
            raise ValueError(f"Malformed mypy baseline entry: {line}")
        code_match = CODE_RE.search(message)
        diagnostics.append(
            Diagnostic(path, message, code_match.group("code") if code_match else "unknown")
        )
    return diagnostics


def _print_summary(current: list[Diagnostic]) -> None:
    by_area = Counter(item.path.split("/", 1)[0] for item in current)
    by_code = Counter(item.code for item in current)
    print("Diagnostics by area: " + ", ".join(f"{key}={value}" for key, value in by_area.most_common()))
    print("Diagnostics by code: " + ", ".join(f"{key}={value}" for key, value in by_code.most_common()))


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
    baseline = _read_baseline()
    new = list((Counter(current) - Counter(baseline)).elements())
    resolved = list((Counter(baseline) - Counter(current)).elements())
    _print_summary(current)
    if args.update:
        if new:
            print("Refusing to update the baseline because mypy added diagnostics:", file=sys.stderr)
            print("\n".join(item.baseline_line for item in sorted(new)), file=sys.stderr)
            return 1
        BASELINE.write_text(
            "\n".join(item.baseline_line for item in current) + ("\n" if current else ""),
            encoding="utf-8",
        )
        print(f"Updated {BASELINE.relative_to(ROOT)} with {len(current)} diagnostics.")
        return 0

    print(f"mypy baseline: {len(current)} diagnostics ({len(resolved)} resolved)")
    if new:
        print("New mypy diagnostics:", file=sys.stderr)
        print("\n".join(item.baseline_line for item in sorted(new)), file=sys.stderr)
        return 1
    if resolved:
        print(
            "Resolved mypy diagnostics remain in the baseline; run "
            "'python scripts/check_mypy_baseline.py --update' and commit the reduction:",
            file=sys.stderr,
        )
        print("\n".join(item.baseline_line for item in sorted(resolved)), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
