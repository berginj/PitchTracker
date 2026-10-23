"""UX-08 journey/recovery presentation evidence, using only disposable display fixtures."""

from contextlib import ExitStack, chdir
import json
import os
from pathlib import Path
import subprocess
import sys
from types import ModuleType
from tempfile import TemporaryDirectory
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from app.services.orchestrator.runtime_status import FinalizedSession, RuntimeFailure  # noqa: E402
from configs.pitchers import save_pitchers  # noqa: E402
from contracts.pitcher import PitcherSelection  # noqa: E402
from scripts.capture_ux_baseline import capture, live_fixture, synthetic_image, synthetic_pitches, write_gallery  # noqa: E402
from scripts.capture_workspace import SyntheticPipeline  # noqa: E402
from scripts.ux_review_fixtures import SyntheticReviewReader, write_session  # noqa: E402
from ui.coaching.coach_window import CoachWindow  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from ui.workspace.contracts import ReviewSelection, SessionPreparation  # noqa: E402
from ui.workspace.window import WorkspaceWindow  # noqa: E402
from ui.workspace.pages import SetupPage, SessionsPage  # noqa: E402


def close_workspace(app, window):
    window._exit_confirmed = True
    window.close()
    deadline = time.monotonic() + 10
    while window.isVisible() and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(.01)
    if window.isVisible():
        raise RuntimeError("Synthetic workspace did not finish shutdown")
    window.deleteLater()
    app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)


def main():
    output = ROOT / "docs/review/ux/ux08"
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    for font in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ux08-", dir=scratch) as temporary, chdir(temporary), ExitStack() as stack:
        stack.enter_context(patch("app.review.review_service.VideoReader", SyntheticReviewReader))
        config = Path("configs/default.yaml")
        config.parent.mkdir()
        config.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        save_pitchers(["Example Pitcher", "Next Pitcher"])
        pipeline = SyntheticPipeline()
        window = WorkspaceWindow(backend="sim", config_path=config.resolve(), pipeline=pipeline, background_tasks=False)
        window._on_validation_complete([], [])
        live = window.page("live")
        assert isinstance(live, CoachWindow)
        live.stop_updates()
        pitches, frame = synthetic_pitches(), synthetic_image()
        completed = write_session(Path("recordings"), "synthetic-completed")

        # Render the prior header implementation with the same synthetic input
        # and current shared theme, so the overflow has a reviewable before image.
        before_module = ModuleType("ui.workspace._ux08_before")
        sys.modules[before_module.__name__] = before_module
        source = subprocess.check_output(["git", "show", "HEAD:ui/workspace/window.py"], cwd=ROOT, text=True, encoding="utf-8")
        exec(compile(source, "ui/workspace/window.py@HEAD", "exec"), before_module.__dict__)
        prior_pipeline = SyntheticPipeline()
        prior = before_module.WorkspaceWindow(backend="sim", config_path=config.resolve(),
                                              pipeline=prior_pipeline, background_tasks=False)
        prior.page("live").stop_updates()
        prior._on_validation_complete([], [])
        prior_pipeline.update(capture_phase="live", recording_phase="completed",
                              finalized_session=FinalizedSession("synthetic-completed", completed),
                              failure=RuntimeFailure("stop_recording", "Synthetic writer failure with a long diagnostic. " * 40))
        prior.navigate("sessions")
        capture(app, prior, "before-sessions", "completed-long-error", output, records)
        close_workspace(app, prior)

        def show(page, state, *, capture_phase="live", recording_phase="idle", prepared=True,
                 pending=None, failure=None):
            window._on_preparation_changed(SessionPreparation("Synthetic bullpen", "Example Pitcher", prepared))
            pipeline.update(capture_phase=capture_phase, recording_phase=recording_phase,
                            session_id="Synthetic bullpen" if recording_phase in {"recording", "paused", "finalizing"} else None,
                            pending_operation=pending, failure=failure,
                            finalized_session=FinalizedSession("synthetic-completed", completed) if recording_phase == "completed" else None,
                            pitcher=PitcherSelection("Example Pitcher"))
            window.navigate(page)
            fixture = recording_phase if recording_phase in {"recording", "paused", "finalizing"} else "ready"
            live_fixture(live, fixture, pitches, frame)
            capture(app, window, "journey-" + page, state, output, records,
                    theme_mode="setup" if page == "setup" else "production")

        show("setup", "unchecked-setup", capture_phase="idle", prepared=False)
        setup = window.page("setup")
        assert isinstance(setup, SetupPage)
        setup.open_guided_setup()
        capture(app, window, "journey-setup", "saved-checks-required", output, records)
        show("players", "active-player", capture_phase="idle", prepared=False)
        show("live", "ready")
        show("live", "recording", recording_phase="recording")
        show("sessions", "recording-away-from-live", recording_phase="recording")
        show("setup", "runtime-capture-blocks-edits", recording_phase="recording")
        show("setup", "paused", recording_phase="paused")
        show("sessions", "finalizing", recording_phase="finalizing", pending="stop_recording")
        show("sessions", "finalization-failed", recording_phase="finalizing",
             failure=RuntimeFailure("stop_recording", "Synthetic writer failure. Accepted work remains owned. " * 30))
        show("sessions", "completed-controls", recording_phase="completed", prepared=False)
        sessions = window.page("sessions")
        assert isinstance(sessions, SessionsPage)
        review = sessions.review
        review.open_session(ReviewSelection(completed, pitch_id="pitch_00002"))
        capture(app, window, "journey-sessions", "selected-completed-pitch", output, records)
        missing = write_session(Path("recordings"), "synthetic-missing-video", state="missing-video")
        review.open_session(ReviewSelection(missing, pitch_id="pitch_00001"))
        capture(app, window, "journey-sessions", "missing-video", output, records)
        show("live", "capture-error", capture_phase="idle", recording_phase="recording",
             failure=RuntimeFailure("capture", "Synthetic camera disconnect. End Session and inspect the camera connection."))
        show("live", "analysis-unavailable", recording_phase="recording")
        live_fixture(live, "unavailable", pitches, frame)
        capture(app, window, "journey-live", "measurement-unavailable", output, records)
        pipeline.update(capture_phase="idle", recording_phase="idle", session_id=None,
                        pending_operation=None, failure=None, finalized_session=None)
        close_workspace(app, window)

        invalid = WorkspaceWindow(backend="sim", config_path=Path(temporary) / "missing-config.yaml",
                                  pipeline=SyntheticPipeline(), background_tasks=False)
        invalid._on_validation_complete([], [])
        capture(app, invalid, "journey-live", "invalid-configuration", output, records)
        invalid.navigate("sessions")
        capture(app, invalid, "journey-sessions", "invalid-config-history-available", output, records)
        close_workspace(app, invalid)

    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {"schema_version": "ux08_captures.v1", "source_commit": commit, "source_worktree_dirty": True,
                "synthetic_only": True, "renderer": "Actual WorkspaceWindow / offscreen Qt / Windows fonts",
                "limitations": ["Presentation fixtures; real simulator lifecycle is tested separately",
                                "No physical camera, athlete data, DPI or screen-reader qualification"], "captures": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, commit, package="UX-08", heading="Operator journeys · synthetic recovery states",
                  specification="../UX_08_QUALIFICATION.md")
    print(f"Saved {len(records)} operator captures to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
