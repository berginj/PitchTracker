"""Capture the implemented UX-02 shell with synthetic data and no hardware/network."""

from contextlib import ExitStack, chdir
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from app.services.orchestrator.runtime_status import RuntimeStatus  # noqa: E402
from app.qt_pipeline_service import QtPipelineService  # noqa: E402
from scripts.capture_ux_baseline import capture, live_fixture, synthetic_image, synthetic_pitches, write_gallery  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from ui.workspace.contracts import SessionPreparation  # noqa: E402
from ui.workspace.window import WorkspaceWindow  # noqa: E402
from ui.workspace.pages import SetupPage  # noqa: E402
from ui.coaching.coach_window import CoachWindow  # noqa: E402


class SyntheticPipeline(QtPipelineService):
    pitch_started = QtCore.Signal(int, object)
    pitch_ended = QtCore.Signal(object)
    runtime_status_changed = QtCore.Signal(object)

    def __init__(self):
        QtCore.QObject.__init__(self)
        self.status = RuntimeStatus()

    def runtime_status(self):
        return self.status

    def update(self, **changes):
        self.status = replace(self.status, sequence=self.status.sequence + 1, **changes)
        self.runtime_status_changed.emit(self.status)

    def get_preview_frames(self):
        return None, None

    def is_capturing(self):
        return self.status.owns_capture

    def get_recent_pitches(self):
        return []

    def get_stats(self):
        return {}

    def get_quality_diagnostics(self):
        return {}

    def shutdown(self):
        pass


def main():
    output = ROOT / "docs/review/ux/ux02"
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    for font in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ux02-", dir=scratch) as temporary, chdir(temporary), ExitStack() as stack:
        for target, value in (
            ("configs.app_state.load_state", {}), ("ui.coaching.mode_composition.load_state", {}),
            ("app.services.rig_profile.RigProfileService.load_active", None),
            ("ui.team.team_manager.load_pitchers", ["Example Pitcher", "Sample Pitcher"]),
        ):
            stack.enter_context(patch(target, return_value=value))
        config = Path("configs/default.yaml")
        config.parent.mkdir()
        config.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        pipeline = SyntheticPipeline()
        window = WorkspaceWindow(backend="sim", config_path=config.resolve(), pipeline=pipeline, background_tasks=False)
        window._on_validation_complete([], [])
        live = window.page("live")
        assert isinstance(live, CoachWindow)
        live.stop_updates()
        pitches, image = synthetic_pitches(), synthetic_image()
        for state in ("idle", "recording"):
            live_fixture(live, state, pitches, image)
            window._on_preparation_changed(SessionPreparation(
                "Synthetic bullpen" if state == "recording" else "",
                "Example Pitcher" if state == "recording" else "", state == "recording"))
            pipeline.update(capture_phase="live" if state == "recording" else "idle",
                            recording_phase="recording" if state == "recording" else "idle",
                            session_id="synthetic-bullpen" if state == "recording" else None)
            for name in ("live", "sessions", "players", "setup"):
                window.navigate(name)
                capture(app, window, "workspace-" + name, state, output, records,
                        theme_mode="setup" if name == "setup" else "production")
        window._on_preparation_changed(SessionPreparation())
        pipeline.update(capture_phase="idle", recording_phase="idle", session_id=None)
        window.navigate("setup")
        setup = window.page("setup")
        assert isinstance(setup, SetupPage)
        setup.open_guided_setup()
        capture(app, window, "workspace-guided-setup", "idle", output, records, theme_mode="setup")
        window.close()
        deadline = time.monotonic() + 5
        while window.isVisible() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        if window.isVisible():
            raise RuntimeError("Evidence workspace did not drain shutdown")
        window.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {"schema_version": "ux02_captures.v1", "source_commit": commit,
                "source_worktree_dirty": True, "synthetic_only": True,
                "renderer": "Actual WorkspaceWindow / Qt offscreen / installed Windows fonts",
                "limitations": ["Display fixtures only; no capture or recording performed",
                                "Guided setup initialized only by explicit fixture action in disposable state",
                                "Not hardware, Windows DPI or physical accuracy qualification"],
                "captures": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, commit, package="UX-02", heading="Implemented workspace · synthetic captures",
                  specification="../UX_02_IMPLEMENTATION.md")
    print(f"Saved {len(records)} actual workspace captures to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
