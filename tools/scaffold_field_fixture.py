"""Create a lightweight field fixture package from a recording session."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from calib.field_fixture_scaffold import scaffold_field_fixture  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a field fixture package from a session directory.")
    parser.add_argument("session_dir", type=Path, help="Existing recording session directory")
    parser.add_argument("output_dir", type=Path, help="Output fixture package directory")
    parser.add_argument("--fixture-id", help="Fixture ID written into field_fixture.json")
    parser.add_argument("--calibration-report", type=Path, help="Optional calibration report JSON to copy")
    parser.add_argument("--sync-report", type=Path, help="Optional sync report JSON to copy")
    parser.add_argument("--overwrite", action="store_true", help="Allow writing into a non-empty output directory")
    args = parser.parse_args()

    manifest = scaffold_field_fixture(
        session_dir=args.session_dir,
        output_dir=args.output_dir,
        fixture_id=args.fixture_id,
        calibration_report=args.calibration_report,
        sync_report=args.sync_report,
        overwrite=args.overwrite,
    )
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
