"""Validate a PitchTracker field fixture manifest."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from calib.field_fixture import FAIL, WARN, validate_field_fixture_manifest  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate a field validation fixture manifest.")
    parser.add_argument("manifest", type=Path, help="Path to field_fixture.json")
    parser.add_argument("--output", type=Path, help="Optional JSON report output path")
    args = parser.parse_args()

    report = validate_field_fixture_manifest(args.manifest)
    text = json.dumps(report, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)
    if report["status"] == FAIL:
        return 2
    if report["status"] == WARN:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
