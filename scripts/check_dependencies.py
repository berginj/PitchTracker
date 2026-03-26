#!/usr/bin/env python3
"""Validate all dependencies are installed before running PitchTracker."""

from __future__ import annotations

import importlib
import sys
from typing import List, Tuple


DependencyRow = Tuple[str, str, str]
DependencyResult = Tuple[bool, List[Tuple[str, str]], List[Tuple[str, str]]]


DEPENDENCIES: list[DependencyRow] = [
    ("cv2", "opencv-contrib-python", "Computer vision library"),
    ("numpy", "numpy", "Numerical computing"),
    ("scipy", "scipy", "Scientific computing"),
    ("yaml", "PyYAML", "Configuration file handling"),
    ("PySide6.QtWidgets", "PySide6", "GUI framework"),
    ("sklearn", "scikit-learn", "Machine learning (pattern detection)"),
    ("matplotlib", "matplotlib", "Plotting (reports)"),
    ("loguru", "loguru", "Logging"),
    ("jsonschema", "jsonschema", "Configuration validation"),
    ("psutil", "psutil", "System resource monitoring"),
]


def check_dependencies(verbose: bool = False) -> DependencyResult:
    """Check if all required dependencies are installed."""
    missing: List[Tuple[str, str]] = []
    installed: List[Tuple[str, str]] = []

    for import_name, package_name, description in DEPENDENCIES:
        try:
            importlib.import_module(import_name)
            installed.append((package_name, description))
            if verbose:
                print(f"  [OK] {package_name}")
        except ImportError:
            missing.append((package_name, description))

    return len(missing) == 0, missing, installed


def print_dependency_error(missing: List[Tuple[str, str]]) -> None:
    """Print a helpful error message about missing dependencies."""
    print("\n" + "=" * 70)
    print("ERROR: MISSING DEPENDENCIES")
    print("=" * 70)
    print("\nPitchTracker requires the following packages to be installed:\n")

    for package_name, description in missing:
        print(f"  [MISSING] {package_name:<30} - {description}")

    print("\n" + "-" * 70)
    print("SOLUTION:")
    print("-" * 70)
    print("\nInstall all dependencies with this command:")
    print("\n  pip install -r requirements.txt")
    print("\nOr install individually:")
    for package_name, _ in missing:
        print(f"  pip install {package_name}")

    print("\n" + "=" * 70)
    print("\nFor detailed setup instructions, see: docs/INSTALLATION.md")
    print("=" * 70)


def main() -> int:
    """Run the dependency check as a standalone script."""
    print("\nChecking PitchTracker dependencies...")
    print("-" * 70)

    all_installed, missing, installed = check_dependencies(verbose=True)

    if all_installed:
        print("-" * 70)
        print(f"\n[OK] All {len(installed)} required dependencies are installed!")
        print("\nYou can now run PitchTracker:")
        print("  python launcher.py       # Setup Wizard (first-time setup)")
        print("  python main_window.py    # Main application")
        return 0

    print_dependency_error(missing)
    return 1


if __name__ == "__main__":
    sys.exit(main())
