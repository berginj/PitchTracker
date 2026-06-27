"""Launcher helpers for opening the canonical stereo setup wizard."""

from __future__ import annotations

from collections.abc import Callable

from PySide6 import QtWidgets


def launch_stereo_setup_window(
    parent: QtWidgets.QWidget,
    on_closed: Callable[[], None],
) -> QtWidgets.QMainWindow:
    """Hide the launcher and show the genuine live stereo setup wizard."""
    from app.services.catalog.service import CameraCatalogService
    from ui.setup.providers import build_live_stereo_step_widgets
    from ui.setup.stereo_setup_window import StereoSetupWindow

    catalog = CameraCatalogService()
    parent.hide()
    window = StereoSetupWindow(widget_factory=lambda: build_live_stereo_step_widgets(catalog=catalog))
    window.show()
    window.destroyed.connect(on_closed)
    return window


__all__ = ["launch_stereo_setup_window"]
