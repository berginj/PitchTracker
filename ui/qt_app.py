"""PySide6 UI entry point for PitchTracker application."""

from __future__ import annotations

import argparse
import platform
from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets

from ui.main_window import MainWindow


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments.

    Returns:
        Parsed arguments with config path and backend selection
    """
    parser = argparse.ArgumentParser(description="Pitch Tracker Qt UI.")
    parser.add_argument("--config", type=Path, default=None)
    parser.add_argument("--backend", default="uvc", choices=("uvc", "opencv", "sim"))
    return parser.parse_args()


def _select_config_path(config_arg: Optional[Path]) -> Path:
    """Select configuration file path based on platform.

    Args:
        config_arg: Optional config path from command line

    Returns:
        Path to configuration file (snapdragon.yaml on ARM, default.yaml otherwise)
    """
    if config_arg is not None:
        return config_arg
    machine = platform.machine().lower()
    processor = platform.processor().lower()
    is_arm = any(token in machine for token in ("arm", "aarch64")) or "arm" in processor
    snapdragon_path = Path("configs/snapdragon.yaml")
    if is_arm and snapdragon_path.exists():
        return snapdragon_path
    return Path("configs/default.yaml")


def main() -> None:
    """Main entry point for PitchTracker Qt application."""
    args = parse_args()
    app = QtWidgets.QApplication([])
    config_path = _select_config_path(args.config)
    window = MainWindow(backend=args.backend, config_path=config_path)
    window.resize(1280, 720)
    window.show()
    app.exec()


if __name__ == "__main__":
    main()
