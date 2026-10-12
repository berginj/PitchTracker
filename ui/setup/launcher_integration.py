"""Launcher helpers for opening the canonical stereo setup wizard."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from PySide6 import QtCore, QtWidgets


def launch_stereo_setup_window(
    parent: QtWidgets.QWidget,
    on_closed: Callable[[], None],
    *, config_path: Path | None = None, backend: str = "uvc",
) -> QtWidgets.QMainWindow:
    """Hide the launcher and show the genuine live stereo setup wizard."""
    from app.services.catalog.service import CameraCatalogService
    from app.services.setup_workflow import SetupWorkflowService
    from ui.setup.guided_steps import GUIDED_SETUP_SPEC, build_guided_setup_widgets
    from ui.setup.stereo_setup_window import StereoSetupWindow

    catalog = CameraCatalogService()
    workflow = SetupWorkflowService(config_path=config_path or Path("configs/default.yaml"), backend=backend)
    window = StereoSetupWindow(
        widget_factory=lambda: build_guided_setup_widgets(workflow, catalog), specs=GUIDED_SETUP_SPEC,
    )
    window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose)
    parent.hide()
    window.show()
    window.destroyed.connect(on_closed)
    return window


__all__ = ["launch_stereo_setup_window"]
