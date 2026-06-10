"""Sync published contract schemas into the runtime ``schema/`` mirror.

``contracts-shared/`` is the single source of truth for published contract
schemas (it is the package shared with downstream consumers). The repository
also keeps a small ``schema/`` directory at the root so the running app can load
schemas without depending on the layout of the shared contracts package.

Those two copies MUST stay byte-for-byte identical -- ``tests/test_contracts.py``
asserts that they match. This script regenerates the root mirror from the
canonical source so the copy never has to be made by hand.

Usage::

    python scripts/sync_schema.py            # write the mirror
    python scripts/sync_schema.py --check     # verify the mirror is in sync (CI)

``--check`` exits non-zero if the mirror is stale, without modifying anything.
"""

from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CANONICAL_DIR = ROOT / "contracts-shared" / "schema"
MIRROR_DIR = ROOT / "schema"

# Files mirrored from the canonical package into the runtime schema directory.
MIRRORED_FILES = (
    "version.json",
    "session_summary.schema.json",
)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def check() -> bool:
    """Return True when the mirror matches the canonical source."""
    in_sync = True
    for name in MIRRORED_FILES:
        canonical = CANONICAL_DIR / name
        mirror = MIRROR_DIR / name
        if not mirror.exists() or _read(mirror) != _read(canonical):
            print(f"OUT OF SYNC: schema/{name} differs from contracts-shared/schema/{name}")
            in_sync = False
    return in_sync


def sync() -> None:
    """Copy canonical schemas into the runtime mirror."""
    MIRROR_DIR.mkdir(parents=True, exist_ok=True)
    for name in MIRRORED_FILES:
        shutil.copyfile(CANONICAL_DIR / name, MIRROR_DIR / name)
        print(f"synced schema/{name}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--check",
        action="store_true",
        help="verify the mirror is in sync without writing (exit 1 if stale)",
    )
    args = parser.parse_args()

    if not CANONICAL_DIR.exists():
        print(f"canonical schema directory not found: {CANONICAL_DIR}")
        return 1

    if args.check:
        if check():
            print("schema mirror is in sync")
            return 0
        print("Run 'python scripts/sync_schema.py' to update the mirror.")
        return 1

    sync()
    return 0


if __name__ == "__main__":
    sys.exit(main())
