#!/usr/bin/env python
"""Test launcher for Camera Capture Validator.

This tool validates camera setup and calibration by capturing raw video
without running detection or tracking pipelines.

Use this to:
- Verify cameras are working correctly
- Test calibration setup
- Record test footage for debugging
- Validate camera configuration before running full sessions
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from PySide6 import QtWidgets

from ui.capture_validator import CaptureValidatorWindow


def main():
    """Launch camera capture validator."""
    app = QtWidgets.QApplication(sys.argv)

    # Set application style
    app.setStyle("Fusion")

    # Create and show validator window
    # Use opencv backend for better compatibility
    validator = CaptureValidatorWindow(backend="opencv")
    validator.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
