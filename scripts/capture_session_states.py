"""UX-03 actual-widget state gallery; synthetic snapshots only, no command dispatch."""

from contextlib import ExitStack, chdir
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
from app.services.orchestrator.runtime_status import FinalizedSession, RuntimeFailure  # noqa: E402
from scripts.capture_ux_baseline import capture, live_fixture, synthetic_image, synthetic_pitches, write_gallery  # noqa: E402
from scripts.capture_workspace import SyntheticPipeline  # noqa: E402
from ui.coaching.coach_window import CoachWindow  # noqa: E402
from ui.coaching.dialogs import SessionStartDialog  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from ui.workspace.contracts import SessionPreparation  # noqa: E402
from ui.workspace.window import WorkspaceWindow  # noqa: E402


def main():
    output = ROOT / "docs/review/ux/ux03"
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    for font in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ux03-", dir=scratch) as temporary, chdir(temporary), ExitStack() as stack:
        for target, value in (
            ("configs.app_state.load_state", {}), ("ui.coaching.mode_composition.load_state", {}),
            ("app.services.rig_profile.RigProfileService.load_active", None),
            ("ui.team.team_manager.load_pitchers", ["Example Pitcher"]),
        ):
            stack.enter_context(patch(target, return_value=value))
        stack.enter_context(patch.object(SessionStartDialog, "_load_saved_pitchers", lambda self: ["Example Pitcher"]))
        config = Path("configs/default.yaml")
        config.parent.mkdir()
        config.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        pipeline = SyntheticPipeline()
        window = WorkspaceWindow(backend="sim", config_path=config.resolve(), pipeline=pipeline, background_tasks=False)
        window._on_validation_complete([], [])
        live = window.page("live")
        assert isinstance(live, CoachWindow)
        live.stop_updates()
        pitches, frame = synthetic_pitches(), synthetic_image()
        states = [
            ("idle", "idle", "idle", False, None, None),
            ("preview", "live", "idle", False, None, None),
            ("ready", "live", "idle", True, None, None),
            ("starting", "live", "starting", True, "start_recording", None),
            ("recording", "live", "recording", True, None, None),
            ("paused", "live", "paused", True, None, None),
            ("finalizing", "live", "finalizing", True, "stop_recording", None),
            ("completed", "live", "completed", False, None, None),
            ("prepare-error", "idle", "idle", False, None, "start_capture"),
            ("start-error", "live", "idle", True, None, "start_recording"),
            ("pause-error", "live", "recording", True, None, "pause_recording"),
            ("resume-error", "live", "paused", True, None, "resume_recording"),
            ("end-error", "live", "finalizing", True, None, "stop_recording"),
        ]
        for state, capture_phase, recording_phase, prepared, pending, failure in states:
            fixture = state if state in {"idle", "ready", "recording", "paused", "finalizing"} else "idle"
            live_fixture(live, fixture, pitches, frame)
            window._on_preparation_changed(SessionPreparation("Synthetic bullpen", "Example Pitcher", prepared))
            pipeline.update(capture_phase=capture_phase, recording_phase=recording_phase,
                            session_id="synthetic-bullpen" if recording_phase in {"starting", "recording", "paused", "finalizing"} else None,
                            pending_operation=pending,
                            failure=RuntimeFailure(failure, "Synthetic failure. Resolve the reported issue and retry.") if failure else None,
                            finalized_session=FinalizedSession("synthetic-bullpen", Path("recordings/synthetic")) if state == "completed" else None)
            pages = ["live"]
            if state in {"recording", "paused", "finalizing", "end-error"}:
                pages.append("sessions")
            if state == "paused":
                pages.append("players")
            if state == "recording":
                pages.append("setup")
            for page in pages:
                window.navigate(page)
                capture(app, window, "session-" + page, state, output, records,
                        theme_mode="setup" if page == "setup" else "production")
        pipeline.update(capture_phase="idle", recording_phase="idle", session_id=None,
                        pending_operation=None, failure=None, finalized_session=None)
        dialog = SessionStartDialog(live._config, backend="sim", config_path=config, prepare_only=True)
        capture(app, dialog, "session-preparation-dialog", "unconfirmed", output, records)
        dialog.close()
        dialog.deleteLater()
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
    manifest = {"schema_version": "ux03_captures.v1", "source_commit": commit, "source_worktree_dirty": True,
                "synthetic_only": True, "renderer": "Actual WorkspaceWindow / Qt offscreen / Windows fonts",
                "limitations": ["Display snapshots only; no camera, recording or command worker started",
                                "Not a hardware, physical accuracy, Windows DPI or screen-reader qualification"],
                "captures": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, commit, package="UX-03", heading="Session states and recovery · synthetic captures",
                  specification="../UX_03_IMPLEMENTATION.md")
    print(f"Saved {len(records)} actual-widget captures to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
