#!/usr/bin/env python
"""Test launcher for Coaching App prototype."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6 import QtWidgets

from ui.coaching import CoachWindow


def main():
    """Launch coaching app for testing."""
    app = QtWidgets.QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show coaching window
    # Use opencv backend for better compatibility (UVC can fail with serial numbers)
    coach = CoachWindow(backend="opencv")
    coach.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
