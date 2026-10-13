#!/usr/bin/env python
"""Compatibility command for the canonical guided setup launcher."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from launcher import main as launch  # noqa: E402


def main():
    launch(["--setup", *sys.argv[1:]])


if __name__ == "__main__":
    main()
