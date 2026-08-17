"""Run strict mypy over modules that have permanently left the debt baseline."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "mypy-clean-zones.json"


def main() -> int:
    targets = json.loads(MANIFEST.read_text(encoding="utf-8"))["targets"]
    if not targets:
        print("mypy clean-zone manifest must contain at least one target", file=sys.stderr)
        return 2
    command = [
        sys.executable,
        "-m",
        "mypy",
        *targets,
        "--no-incremental",
        "--follow-imports=silent",
        "--disallow-untyped-defs",
        "--disallow-incomplete-defs",
        "--disallow-any-generics",
        "--no-implicit-reexport",
        "--warn-unreachable",
        "--show-error-codes",
    ]
    result = subprocess.run(command, cwd=ROOT, check=False)
    if result.returncode == 0:
        print(f"OK: {len(targets)} strict mypy clean zones")
    return result.returncode


if __name__ == "__main__":
    raise SystemExit(main())
