"""Explicit GUI artifact smoke test: isolated state, simulator, no network/cameras."""

from __future__ import annotations

import json
import os
from contextlib import chdir
from pathlib import Path
import tempfile
import traceback

from PySide6 import QtCore, QtWidgets

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
                report["workflows"] = _render_workflows(app, windows)
            report["ok"] = True
    except Exception:
        report["ok"] = False
        report["error"] = traceback.format_exc()
    finally:
        for owned_window in reversed(windows):
            owned_window.close()
            owned_window.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
        app.setQuitOnLastWindowClosed(quit_on_close)
        os.chdir(original_cwd)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return 0 if report["ok"] else 1


def _render_workflows(app: QtWidgets.QApplication, windows: list[QtWidgets.QWidget]) -> list[str]:
    from launcher import LauncherWindow
    from ui.coaching import CoachWindow
    from ui.review import ReviewWindow
    from ui.setup.stereo_setup_window import StereoSetupWindow

    workflows = []
    for factory in (
        lambda: LauncherWindow(backend="sim", background_tasks=False),
        lambda: CoachWindow(backend="sim"), StereoSetupWindow, ReviewWindow,
    ):
        window = factory()
        windows.append(window)
        window.show()
        app.processEvents()
        if window.grab().isNull():
            raise RuntimeError(f"GUI render failed: {type(window).__name__}")
        if not window.close():
            raise RuntimeError(f"GUI shutdown did not reach terminal state: {type(window).__name__}")
        app.processEvents()
        workflows.append(type(window).__name__)
    return workflows
