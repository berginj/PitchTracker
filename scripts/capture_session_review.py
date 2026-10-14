"""Actual-widget UX-05 evidence using disposable synthetic session artifacts."""

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
from scripts.capture_ux_baseline import capture, write_gallery  # noqa: E402
from scripts.capture_workspace import SyntheticPipeline  # noqa: E402
from scripts.ux_review_fixtures import SyntheticReviewReader, write_session  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from ui.workspace.contracts import ReviewSelection  # noqa: E402
from ui.workspace.window import WorkspaceWindow  # noqa: E402
from ui.workspace.pages import SessionsPage  # noqa: E402
from ui.coaching.coach_window import CoachWindow  # noqa: E402


def main():
    output = ROOT / "docs/review/ux/ux05"
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ux05-", dir=scratch) as temporary, chdir(temporary), ExitStack() as stack:
        for target, value in (("configs.app_state.load_state", {}), ("ui.coaching.mode_composition.load_state", {}),
                              ("app.services.rig_profile.RigProfileService.load_active", None)):
            stack.enter_context(patch(target, return_value=value))
        stack.enter_context(patch("app.review.review_service.VideoReader", SyntheticReviewReader))
        config = Path("configs/default.yaml")
        config.parent.mkdir()
        config.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
        pipeline = SyntheticPipeline()
        window = WorkspaceWindow(backend="sim", config_path=config.resolve(), pipeline=pipeline, background_tasks=False)
        window._on_validation_complete([], [])
        live = window.page("live")
        assert isinstance(live, CoachWindow)
        live.stop_updates()
        window.navigate("sessions")
        page = window.page("sessions")
        assert isinstance(page, SessionsPage)
        capture(app, window, "sessions", "no-history", output, records)
        for state in ("measured", "empty", "missing-video", "invalid-mapping", "legacy", "rejected", "active-capture"):
            session = write_session(Path("recordings"), f"synthetic-{state}", state=state)
            pipeline.update(capture_phase="live" if state == "active-capture" else "idle",
                            recording_phase="recording" if state == "active-capture" else "idle",
                            session_id="active-synthetic-session" if state == "active-capture" else None,
                            active_session_dir=Path("recordings/active") if state == "active-capture" else None)
            page.refresh()
            page.open_selection(ReviewSelection(session, pitch_id=None if state == "empty" else "pitch_00002"))
            capture(app, window, "sessions", state, output, records)
        pipeline.update(capture_phase="idle", recording_phase="idle", session_id=None, active_session_dir=None)
        window.close()
        deadline = time.monotonic() + 5
        while window.isVisible() and time.monotonic() < deadline:
            app.processEvents()
            time.sleep(.01)
        if window.isVisible():
            raise RuntimeError("Synthetic workspace did not finish shutdown")
        window.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {"schema_version": "ux05_captures.v1", "source_commit": commit, "source_worktree_dirty": True,
                "synthetic_only": True, "renderer": "Actual PySide6 widgets / synthetic decoder / offscreen Windows fonts",
                "limitations": ["No cameras, codecs, private artifacts, uploads or offline processing admitted",
                                "Not hardware, physical accuracy, screen-reader or Windows DPI qualification"],
                "captures": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, commit, package="UX-05", heading="Sessions and pitch review · synthetic captures",
                  specification="../UX_05_IMPLEMENTATION.md")
    print(f"Saved {len(records)} synthetic session-review captures")


if __name__ == "__main__":
    main()
