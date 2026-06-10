"""Test script for Review Mode UI.

Launch this script to test the Review Mode window directly.
"""

import sys
from pathlib import Path

from PySide6 import QtWidgets

from ui.review import ReviewWindow


def main():
    """Launch review mode window for testing."""
    app = QtWidgets.QApplication(sys.argv)

    # Create and show review window
    window = ReviewWindow()
    window.show()

    # Show info message
    QtWidgets.QMessageBox.information(
        window,
        "Review Mode Test",
        "Review Mode window opened!\n\n"
        "To test:\n"
        "1. File → Open Session\n"
        "2. Browse to a recorded session in recordings/\n"
        "3. Use playback controls and timeline\n\n"
        "Note: You need at least one recorded session to test with.",
    )

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
