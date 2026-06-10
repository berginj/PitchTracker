"""Test script to verify coaching UI with 3 visualization modes."""

import sys
from pathlib import Path

from PySide6 import QtWidgets

from ui.coaching.coach_window import CoachWindow


def main():
    """Launch coaching window for UI testing."""
    app = QtWidgets.QApplication(sys.argv)

    # Create coaching window
    window = CoachWindow(backend="uvc")
    window.show()

    print("Coaching window launched successfully!")
    print("Test the following:")
    print("  1. Mode selector dropdown has 3 modes")
    print("  2. Switch between modes")
    print("  3. Each mode displays correctly")
    print("  4. Camera toggle works in each mode")

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
