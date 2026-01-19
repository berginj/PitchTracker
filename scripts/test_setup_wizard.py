#!/usr/bin/env python
"""Test launcher for Setup Wizard prototype."""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6 import QtWidgets

from ui.setup import SetupWindow


def main():
    """Launch setup wizard for testing."""
    app = QtWidgets.QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show wizard
    wizard = SetupWindow(backend="uvc")
    wizard.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
