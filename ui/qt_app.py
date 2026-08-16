"""Compatibility entry point forwarding to the canonical role launcher."""

from __future__ import annotations

from launcher import main as launcher_main
from launcher import parse_args

__all__ = ["main", "parse_args"]


def main() -> None:
    """Backward-compatible wrapper for ``python launcher.py``."""
    launcher_main()


if __name__ == "__main__":
    main()
