#!/usr/bin/env python3
"""PitchTracker Application Launcher

This script properly sets up the Python path and launches the PitchTracker application.

Usage:
    python launch_app.py              # Launch with simulated backend
    python launch_app.py --backend opencv  # Launch with real cameras
"""

import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

# Import and run main window
if __name__ == "__main__":
    from ui.main_window import main
    sys.exit(main())
