#!/usr/bin/env python3
"""Validate all dependencies are installed before running PitchTracker.

This script checks for required Python packages and provides helpful
error messages with installation instructions if anything is missing.
"""

import sys
from typing import List, Tuple


def check_dependencies(verbose: bool = False) -> Tuple[bool, List[str]]:
    """Check if all required dependencies are installed.

    Args:
        verbose: If True, print success messages for each package

    Returns:
        Tuple of (all_installed: bool, missing_packages: List[str])
    """
    missing = []
    installed = []

    # Core dependencies
    dependencies = [
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

    for import_name, package_name, description in dependencies:
        try:
            __import__(import_name)
            installed.append((package_name, description))
            if verbose:
                print(f"  ✓ {package_name}")
        except ImportError:
            missing.append((package_name, description))

    return len(missing) == 0, missing, installed


def print_dependency_error(missing: List[Tuple[str, str]]) -> None:
    """Print helpful error message about missing dependencies.

    Args:
        missing: List of (package_name, description) tuples
    """
    print("\n" + "="*70)
    print("ERROR: MISSING DEPENDENCIES")
    print("="*70)
    print("\nPitchTracker requires the following packages to be installed:")
    print()

    for package_name, description in missing:
        print(f"  ✗ {package_name:<30} - {description}")

    print("\n" + "-"*70)
    print("SOLUTION:")
    print("-"*70)
    print("\nInstall all dependencies with this command:")
    print("\n  pip install -r requirements.txt")
    print("\nOr install individually:")
    for package_name, _ in missing:
        print(f"  pip install {package_name}")

    print("\n" + "="*70)
    print("\nFor detailed setup instructions, see: docs/INSTALLATION.md")
    print("="*70)


def main():
    """Run dependency check as standalone script."""
    print("\nChecking PitchTracker dependencies...")
    print("-" * 70)

    all_installed, missing, installed = check_dependencies(verbose=True)

    if all_installed:
        print("-" * 70)
        print(f"\n✓ All {len(installed)} required dependencies are installed!")
        print("\nYou can now run PitchTracker:")
        print("  python launcher.py       # Setup Wizard (first-time setup)")
        print("  python main_window.py    # Main application")
        return 0
    else:
        print_dependency_error(missing)
        return 1


if __name__ == "__main__":
    sys.exit(main())
