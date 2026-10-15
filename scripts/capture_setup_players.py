"""Synthetic UX-06 workspace evidence without acquisition or publication."""

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
from app.services.setup_workflow import SetupWorkflowService  # noqa: E402
from configs.pitchers import save_pitchers  # noqa: E402
from contracts.pitcher import PitcherSelection  # noqa: E402
from scripts.capture_ux_baseline import capture, write_gallery  # noqa: E402
from scripts.capture_workspace import SyntheticPipeline  # noqa: E402
from scripts.ux_review_fixtures import SyntheticReviewReader, write_session  # noqa: E402
from ui.coaching.coach_window import CoachWindow  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from ui.workspace.window import WorkspaceWindow  # noqa: E402
from ui.workspace.pages import SetupPage, PlayersPage, SessionsPage  # noqa: E402


def main():
    output = ROOT / "docs/review/ux/ux06"
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    for font in ("segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ux06-", dir=scratch) as temporary, chdir(temporary), ExitStack() as stack:
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
        window.navigate("players")
        players = window.page("players")
        assert isinstance(players, PlayersPage)
        roster = players._roster
        capture(app, window, "players", "empty", output, records)
        save_pitchers(["Example Pitcher", "Next Pitcher"])
        roster._load_roster()
        roster._on_pitcher_clicked("Example Pitcher")
        pipeline.update(pitcher=PitcherSelection("Example Pitcher"))
        capture(app, window, "players", "populated", output, records)
        roster._new_pitcher_edit.setText("example pitcher")
        roster._add_pitcher()
        capture(app, window, "players", "duplicate-name", output, records)
        roster._new_pitcher_edit.clear()
        roster._feedback.setText("Browsing and active-pitcher changes remain separate actions.")
        pipeline.update(capture_phase="live", recording_phase="recording", session_id="Synthetic bullpen",
                        pitcher=PitcherSelection("Example Pitcher", "Next Pitcher", "pitch_00001"))
        capture(app, window, "players", "pending-pitch-boundary", output, records)
        session = write_session(Path("recordings"))
        path = session / "pitch_00001/manifest.json"
        payload = json.loads(path.read_text())
        payload["pitcher"] = {"schema_version": "pitcher_attribution.v1", "name": "Example Pitcher"}
        path.write_text(json.dumps(payload), encoding="utf-8")
        window._on_player_browsed("Example Pitcher")
        sessions = window.page("sessions")
        assert isinstance(sessions, SessionsPage)
        sessions._open_selected()
        capture(app, window, "sessions", "recorded-player-filter", output, records)
        sessions.browse_player("Unknown historical player")
        capture(app, window, "sessions", "unknown-attribution", output, records)
        window.navigate("setup")
        setup = window.page("setup")
        assert isinstance(setup, SetupPage)
        capture(app, window, "setup", "capture-owned", output, records)
        pipeline.update(capture_phase="idle", recording_phase="idle", session_id=None,
                        pitcher=PitcherSelection("Next Pitcher"))
        capture(app, window, "setup", "overview", output, records)
        setup.open_guided_setup()
        wizard = setup.wizard
        assert wizard is not None and isinstance(wizard.workflow, SetupWorkflowService)
        camera = wizard._steps[0]
        camera.widgets["exposure_us"].setValue(3600)
        camera.widgets["exposure_us"].editingFinished.emit()
        capture(app, window, "setup", "saved-needs-checks", output, records)
        window.navigate("players")
        window.navigate("setup")
        capture(app, window, "setup", "saved-reentry", output, records)
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
    manifest = {"schema_version": "ux06_captures.v1", "source_commit": commit, "source_worktree_dirty": True,
                "synthetic_only": True, "renderer": "Actual Qt widgets / synthetic decoder / offscreen Windows fonts",
                "limitations": ["No acquisition, private artifacts, rig publication, offline processing or uploads",
                                "Not physical accuracy, hardware, Windows DPI or screen-reader qualification"],
                "captures": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, commit, package="UX-06", heading="Setup and players · synthetic captures",
                  specification="../UX_06_IMPLEMENTATION.md")
    print(f"Saved {len(records)} synthetic setup/player captures")


if __name__ == "__main__":
    main()
