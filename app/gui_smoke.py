"""Explicit GUI artifact smoke test: isolated state, simulator, no network/cameras."""

from __future__ import annotations

import json
import os
from contextlib import chdir
from pathlib import Path
import tempfile
import time
import traceback

from PySide6 import QtCore, QtWidgets
from loguru import logger

from app.runtime_paths import resource_root, seed_default_configs


def run_gui_smoke(report_path: Path) -> int:
    """Construct/render/close the real GUI workflows and write a local QA report."""
    report_path = report_path.resolve()
    resources = resource_root()
    original_cwd = Path.cwd()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    assert isinstance(app, QtWidgets.QApplication)
    quit_on_close = app.quitOnLastWindowClosed()
    app.setQuitOnLastWindowClosed(False)
    windows: list[QtWidgets.QWidget] = []
    report: dict[str, object] = {"schema_version": "gui_smoke.v1", "ok": False, "backend": "sim", "workflows": []}
    try:
        with tempfile.TemporaryDirectory(prefix="pitchtracker-gui-smoke-") as scratch:
            state = Path(scratch)
            seed_default_configs(resources, state)
            # Restore cwd before TemporaryDirectory removes its own scratch tree
            # (Windows refuses deletion of the process's current directory).
            with chdir(state):
                try:
                    report["workflows"] = _render_workflows(app, windows, report)
                finally:
                    _close_windows(app, windows)
                    # This terminal diagnostic owns its process. Flush and close
                    # log sinks before Windows removes the isolated scratch tree.
                    logger.complete()
                    logger.remove()
            report["ok"] = True
    except Exception:
        report["ok"] = False
        report["error"] = traceback.format_exc()
    finally:
        _close_windows(app, windows)
        app.setQuitOnLastWindowClosed(quit_on_close)
        os.chdir(original_cwd)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def _close_windows(app, windows):
    for owned_window in reversed(windows):
        owned_window.close()
        owned_window.deleteLater()
    windows.clear()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def _render_workflows(app: QtWidgets.QApplication, windows: list[QtWidgets.QWidget], report: dict[str, object]) -> list[str]:
    from launcher import LauncherWindow
    from ui.coaching import CoachWindow
    from ui.review import ReviewWindow
    from ui.setup.stereo_setup_window import StereoSetupWindow
    from ui.workspace.window import WorkspaceWindow

    workflows = []
    for factory in (
        lambda: LauncherWindow(backend="sim", background_tasks=False),
        lambda: CoachWindow(backend="sim"), lambda: StereoSetupWindow(backend="sim"), ReviewWindow,
        lambda: WorkspaceWindow(backend="sim", background_tasks=False),
    ):
        window = factory()
        windows.append(window)
        if isinstance(window, StereoSetupWindow):
            stages = [stage.value for stage in window._machine.steps]
            if stages != ["cameras", "images", "calibration", "field", "ready"]:
                raise RuntimeError("GUI smoke did not construct the guided setup workflow")
            report["setup_stages"] = stages
        window.show()
        app.processEvents()
        if window.grab().isNull():
            raise RuntimeError(f"GUI render failed: {type(window).__name__}")
        if not window.close():
            deadline = time.monotonic() + 5
            while window.isVisible() and time.monotonic() < deadline:
                app.processEvents()
                time.sleep(.01)
            if window.isVisible():
                raise RuntimeError(f"GUI shutdown did not reach terminal state: {type(window).__name__}")
        app.processEvents()
        workflows.append(type(window).__name__)
    return workflows
