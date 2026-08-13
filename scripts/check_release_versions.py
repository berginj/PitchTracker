"""Verify that all release-facing application versions agree."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from contracts.versioning import APP_VERSION  # noqa: E402
from updater import CURRENT_VERSION  # noqa: E402


def _installer_version() -> str | None:
    text = (ROOT / "installer.iss").read_text(encoding="utf-8")
    match = re.search(r'#define AppVersion "([^"]+)"', text)
    return match.group(1) if match else None


def main() -> int:
    versions = {
        "contracts/versioning.py": APP_VERSION,
        "updater.py": CURRENT_VERSION,
        "installer.iss": _installer_version(),
    }
    expected = APP_VERSION
    mismatches = {source: value for source, value in versions.items() if value != expected}
    if mismatches:
        print(f"ERROR: release versions must all equal {expected}:")
        for source, value in mismatches.items():
            print(f"  {source}: {value!r}")
        return 1

    print(f"OK: release version {expected} is aligned across {len(versions)} sources.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
