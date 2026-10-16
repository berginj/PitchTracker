"""Capture UX-04 Live views with synthetic data in a disposable workspace."""

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
from app.services.orchestrator.runtime_status import RuntimeFailure  # noqa: E402
from contracts import Frame  # noqa: E402
from scripts.capture_ux_baseline import capture, synthetic_image, synthetic_pitches, write_gallery  # noqa: E402
from scripts.capture_workspace import SyntheticPipeline  # noqa: E402
from ui.coaching.coach_window import CoachWindow  # noqa: E402
from ui.coaching.widgets.mode_widgets import BaseModeWidget  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from ui.workspace.contracts import SessionPreparation  # noqa: E402
from ui.workspace.window import WorkspaceWindow  # noqa: E402


def main():
    output = ROOT / "docs/review/ux/ux04"
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    for font in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ux04-", dir=scratch) as temporary, chdir(temporary), ExitStack() as stack:
        for target, value in (("configs.app_state.load_state", {}), ("ui.coaching.mode_composition.load_state", {}),
                              ("app.services.rig_profile.RigProfileService.load_active", None)):
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
        original = synthetic_pitches()
        frame = Frame(camera_id="synthetic", frame_index=0, t_capture_monotonic_ns=0,
                      image=synthetic_image(), width=640, height=480, pixfmt="bgr8")
        for state in ("empty", "measured", "unavailable", "rejected", "degraded", "error"):
            pitches = [] if state == "empty" else list(original)
            if state in {"unavailable", "rejected", "degraded"}:
                status = state.upper()
                pitches[-1] = replace(
                    pitches[-1], measurement_status=status,
                    observation_rejection_reasons=["Insufficient tracking evidence"] if state != "degraded" else None,
                    observation_warning_reasons=["Partial tracking coverage"] if state == "degraded" else None)
            live._broadcast_mode.clear()
            live._progression_mode.clear()
            live._game_mode.clear()
            live._pitch_snapshot = pitches
            for pitch in pitches:
                live._session_tracker.add_pitch(pitch)
            live._session_prepared = bool(pitches)
            live._session_name, live._pitcher_name = "Synthetic bullpen", "Example Pitcher"
            live._pitch_count_label.setText(f"Pitches: {len(pitches)}")
            live._quality_indicator.setText("Tracking: waiting" if not pitches else "Tracking: estimated")
            window._on_preparation_changed(SessionPreparation(live._session_name, live._pitcher_name, bool(pitches)))
            pipeline.update(capture_phase="live" if pitches else "idle",
                            recording_phase="finalizing" if state == "error" else "recording" if pitches else "idle",
                            session_id="synthetic-bullpen" if pitches else None,
                            failure=RuntimeFailure("stop_recording", "Synthetic writer cleanup pending. Retry End Session.") if state == "error" else None)
            for index, name in enumerate(("latest-pitch", "session-trends", "games")):
                live._mode_selector.setCurrentIndex(index)
                mode = live._mode_stack.currentWidget()
                assert isinstance(mode, BaseModeWidget)
                mode.update_pitch_data(pitches, new_pitches=[])
                if pitches:
                    mode.update_camera_frames(frame, frame)
                capture(app, window, name, state, output, records)
        pipeline.update(capture_phase="idle", recording_phase="idle", session_id=None, failure=None)
        window.close()
        deadline = time.monotonic() + 5
        while window.isVisible() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        if window.isVisible():
            raise RuntimeError("Evidence workspace did not finish shutdown")
        window.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {"schema_version": "ux04_captures.v1", "source_commit": commit, "source_worktree_dirty": True,
                "synthetic_only": True, "renderer": "Actual PySide6 widgets / offscreen Qt / Windows fonts",
                "limitations": ["No hardware, recording, private athlete data or processing admitted",
                                "Display fixtures, not physical accuracy, DPI or screen-reader qualification"],
                "captures": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, commit, package="UX-04", heading="Live feedback · synthetic captures",
                  specification="../UX_04_IMPLEMENTATION.md")
    print(f"Saved {len(records)} Live captures to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
