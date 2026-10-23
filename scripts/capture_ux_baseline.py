"""Render real UI layouts with isolated synthetic inputs; never open cameras.

Run from the repo with a supported Python and Qt installed. Services and private
preferences are replaced only in this evidence harness, not in application code.
"""

from __future__ import annotations

import argparse
from contextlib import ExitStack
from dataclasses import asdict, replace
from html import escape
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402

from app.contracts import PitchSummary  # noqa: E402
from contracts.measurements import SpeedMeasurement  # noqa: E402
from contracts.quality import MeasurementStatus  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402

SIZES = ((1366, 768), (1024, 768), (800, 600))


class DisplayOnlyPipeline(QtCore.QObject):
    """No domain lifecycle is executed by screenshot fixtures."""

    pitch_started = QtCore.Signal(int, object)
    pitch_ended = QtCore.Signal(object)

    def __init__(self, backend="sim", parent=None):
        super().__init__(parent)

    def is_capturing(self):
        return False

    def shutdown(self):
        pass


def synthetic_pitches():
    pitches = []
    for index, speed in enumerate((71.2, 72.4, 71.8, 73.0, 72.6), 1):
        pitches.append(PitchSummary(
            pitch_id=f"pitch_{index:05d}", t_start_ns=index * 1_000_000_000,
            t_end_ns=index * 1_000_000_000 + 200_000_000,
            is_strike=index != 3, zone_row=1, zone_col=1, run_in=0, rise_in=0,
            speed_mph=speed, rotation_rpm=None, sample_count=12,
            trajectory_plate_x_ft=0.1, trajectory_plate_y_ft=2.6,
            measurement_status=MeasurementStatus.ESTIMATED,
            vision_speed=SpeedMeasurement(speed, "vision_fit", "first_observed", estimator="vision_only"),
            quality_diagnostics={"movement_validated": False},
        ))
    return pitches


def synthetic_image():
    """Draw a labeled schematic; no camera/athlete imagery is read."""
    import numpy as np
    import cv2

    image = np.full((480, 640, 3), (38, 48, 63), dtype=np.uint8)
    cv2.line(image, (40, 450), (320, 130), (73, 94, 110), 2)
    cv2.line(image, (600, 450), (320, 130), (73, 94, 110), 2)
    cv2.rectangle(image, (260, 180), (380, 350), (150, 171, 188), 2)
    cv2.putText(image, "SYNTHETIC CAMERA SCHEMATIC", (80, 65), 0, .65, (215, 226, 235), 1)
    cv2.putText(image, "No camera acquired / no private footage", (80, 100), 0, .48, (170, 191, 208), 1)
    return image


def capture(app, widget, page, state, output, records, *, theme_mode=None, reveal_widget=None):
    get_style_manager().set_mode(theme_mode or ("setup" if page.startswith("setup") else "production"))
    for width, height in SIZES:
        widget.resize(width, height)
        widget.show()
        for _ in range(3):
            QtWidgets.QApplication.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
            app.processEvents()
        if reveal_widget is not None:
            for area in widget.findChildren(QtWidgets.QScrollArea):
                if area.widget() is not None and area.widget().isAncestorOf(reveal_widget):
                    area.ensureWidgetVisible(reveal_widget)
            app.processEvents()
        filename = f"{page}-{state}-{width}x{height}.png"
        if not widget.grab().save(str(output / filename)):
            raise RuntimeError(f"Could not save {filename}")
        controls = []
        bounds = QtCore.QRect(0, 0, width, height)
        for child in widget.findChildren(QtWidgets.QAbstractButton):
            if not child.isVisibleTo(widget):
                continue
            position = child.mapTo(widget, QtCore.QPoint(0, 0))
            rect = QtCore.QRect(position, child.size())
            controls.append({
                "text": child.text(), "accessible_name": child.accessibleName(),
                "enabled": child.isEnabled(),
                "rect": [rect.x(), rect.y(), rect.width(), rect.height()],
                "inside_requested_bounds": bounds.contains(rect),
                "connected_click_receivers": child.receivers("2clicked(bool)"),
            })
        records.append({
            "file": filename, "page": page, "fixture_state": state,
            "requested_size": [width, height],
            "actual_size": [widget.width(), widget.height()],
            "minimum_size_hint": [widget.minimumSizeHint().width(), widget.minimumSizeHint().height()],
            "device_pixel_ratio": widget.devicePixelRatioF(),
            "visible_button_count": len(controls), "controls": controls,
            "vertical_scroll_ranges": [area.verticalScrollBar().maximum()
                                       for area in widget.findChildren(QtWidgets.QScrollArea)],
            "horizontal_scroll_ranges": [area.horizontalScrollBar().maximum()
                                         for area in widget.findChildren(QtWidgets.QScrollArea)],
        })
    widget.hide()


def write_gallery(output, records, commit, *, package="UX-01",
                  heading="Current UI · synthetic baseline", specification="../UX_01_SPEC.md"):
    cards = []
    for item in records:
        requested = "x".join(map(str, item["requested_size"]))
        actual = "x".join(map(str, item["actual_size"]))
        label = f'{item["page"]} / {item["fixture_state"]}'
        cards.append(f'''<article data-page="{escape(item['page'])}">
          <a href="{escape(item['file'])}"><img loading="lazy" src="{escape(item['file'])}"
          alt="Current UI: {escape(label)}, requested {requested}, actual {actual}"></a>
          <h2>{escape(label)}</h2><p>Requested {requested} · actual {actual}</p>
          <p>{item['visible_button_count']} visible buttons · synthetic inputs</p></article>''')
    options = "".join(f'<option>{escape(page)}</option>' for page in sorted({r["page"] for r in records}))
    page = f'''<!doctype html><html lang="en"><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1">
      <title>PitchTracker {escape(package)} · {escape(heading)}</title><style>
      body{{margin:24px;background:#f4f7fb;color:#0f172a;font:15px "Segoe UI",sans-serif}}
      h1{{font-size:26px}}h2{{font-size:16px}}p{{color:#475569;font-size:13px}}
      select{{padding:8px;margin-bottom:20px}}a{{color:#1d4ed8}}
      .grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:16px}}
      article{{background:white;padding:14px;border:1px solid #d7e0ea;border-radius:12px}}
      article img{{width:100%;height:210px;object-fit:contain;background:#f8fafc}}
      article[hidden]{{display:none}}</style><h1>{escape(heading)}</h1>
      <p>Source {escape(commit)} + evidence worktree · offscreen Qt · installed Windows fonts.</p>
      <p>Actual widget layouts with display-only state fixtures. No lifecycle, camera, private
      session or accuracy validation. Click an image for its full actual size.</p>
      <p><a href="../workspace.html">Target workspace</a> · <a href="{escape(specification)}">Specification</a>
      · <a href="manifest.json">Geometry manifest</a></p>
      <label>Filter by surface <select id="surface"><option>All</option>{options}</select></label>
      <div class="grid">{''.join(cards)}</div><script>
      document.getElementById('surface').addEventListener('change',e=>{{
      document.querySelectorAll('article').forEach(a=>a.hidden=e.target.value!=='All'&&a.dataset.page!==e.target.value);
      }});</script></html>'''
    (output / "index.html").write_text(page, encoding="utf-8")


def live_fixture(window, state, pitches, image):
    messages = {
        "idle": "Ready. Click 'Start Session' to begin.",
        "ready": "Session ready. Click 'Start Recording' when ready to pitch.",
        "recording": "Recording in progress. Ready to track pitches.",
        "paused": "Session paused. Cameras remain live until you resume.",
        "finalizing": "Stopping recording...",
        "error": "Session stop failed. Session remains active; retry End Session.",
        "unavailable": "Recording in progress. Latest pitch measurement unavailable.",
    }
    tone = "error" if state == "error" else "warning" if state in {"paused", "ready"} else "info"
    window._set_status_message(messages[state], tone)
    window._setup_button.setEnabled(state == "idle")
    window._start_recording_button.setEnabled(state == "ready")
    window._pause_button.setEnabled(state in {"recording", "paused", "unavailable"})
    window._pause_button.setText("Resume" if state == "paused" else "Pause")
    window._end_button.setEnabled(state not in {"idle", "finalizing"})
    window._recording_indicator.setVisible(state in {"recording", "error", "unavailable"})
    window._session_label.setText("Session: <not started>" if state == "idle" else "Session: Synthetic bullpen")
    window._pitcher_label.setText("Pitcher: <not selected>" if state == "idle" else "Pitcher: Example Pitcher")
    data = [] if state in {"idle", "ready"} else pitches
    if state == "unavailable":
        data = [replace(pitches[-1], speed_mph=None, vision_speed=None,
                        measurement_status=MeasurementStatus.UNAVAILABLE,
                        trajectory_plate_x_ft=None, trajectory_plate_y_ft=None)]
    window._broadcast_mode.clear()
    window._broadcast_mode.update_pitch_data(data)
    window._pitch_count_label.setText(f"Pitches: {len(data)}")
    if state != "idle":
        frame = SimpleNamespace(image=image)
        window._broadcast_mode.update_camera_frames(frame, frame)


def build_evidence(app, temp, output, records):
    from launcher import LauncherWindow
    from ui.analytics.session_dashboard import SessionDashboard
    from ui.coaching.coach_window import CoachWindow
    from ui.dialogs.recording_settings_dialog import RecordingSettingsDialog
    from ui.review.review_window import ReviewWindow
    from ui.setup.stereo_setup_window import StereoSetupWindow
    from ui.team.team_manager import TeamManager
    from app.services.setup_workflow import SetupWorkflowService

    config = temp / "default.yaml"
    config.write_text((ROOT / "configs/default.yaml").read_text(encoding="utf-8"), encoding="utf-8")
    pitches, image = synthetic_pitches(), synthetic_image()
    launcher = LauncherWindow(backend="sim", config_path=config, background_tasks=False)
    capture(app, launcher, "launcher", "validation-pending", output, records)
    launcher.close()

    window = CoachWindow(backend="sim", config_path=config)
    window._preview_timer.stop()
    window._metrics_timer.stop()
    for state in ("idle", "ready", "recording", "paused", "finalizing", "error", "unavailable"):
        live_fixture(window, state, pitches, image)
        capture(app, window, "live", state, output, records)
    window.close()  # Synthetic display flags do not set the lifecycle owner active.

    review = ReviewWindow()
    capture(app, review, "review", "empty", output, records)
    review._left_display.set_frame(image)
    review._right_display.set_frame(image)
    entries = [SimpleNamespace(pitch_id=p.pitch_id, manifest={
        "pitch_id": p.pitch_id, "measured_speed_mph": p.speed_mph}) for p in pitches]
    review._pitch_list.load_pitches(entries, {})
    review._timeline.set_total_frames(120)
    review._status_bar.showMessage("Synthetic completed session / schematic frames / no video reader opened")
    capture(app, review, "review", "synthetic-pitches", output, records)
    review.close()

    team = TeamManager()
    capture(app, team, "players", "empty", output, records)
    team._update_roster_display(["Example Pitcher", "Sample Pitcher"])
    capture(app, team, "players", "synthetic-roster", output, records)
    team.close()

    workflow = SetupWorkflowService(config, temp / "calibration/rigs", backend="sim", use_active=False)
    setup = StereoSetupWindow(workflow=workflow)
    for index, spec in enumerate(setup._machine.specs):
        # Render each real stage without fabricating completion of its prerequisites.
        setup._machine._index = index
        setup._show_current()
        capture(app, setup, f"setup-{spec.step.value}", "unchecked", output, records)
    setup.close()

    dashboard = SessionDashboard()
    dashboard.load_session("Synthetic bullpen", "Example Pitcher", [])
    capture(app, dashboard, "analytics", "empty", output, records)
    dashboard.load_session("Synthetic bullpen", "Example Pitcher", pitches)
    capture(app, dashboard, "analytics", "synthetic-pitches", output, records)
    dashboard.close()

    dialog = RecordingSettingsDialog(None, "Synthetic bullpen", str(temp), 60.0)
    capture(app, dialog, "recording-dialog", "defaults", output, records)
    dialog.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=ROOT / "docs/review/ux/baseline")
    args = parser.parse_args()
    output = args.output.resolve()
    if not output.is_relative_to(ROOT):
        parser.error("Evidence output must stay inside this repository")
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    # Qt offscreen may not discover Windows fonts. Load installed fonts explicitly
    # rather than accepting tofu glyphs and invalid minimum-size measurements.
    if sys.platform == "win32":
        fonts = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts"
        for filename in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
            path = fonts / filename
            if path.is_file():
                QtGui.QFontDatabase.addApplicationFont(str(path))
    if not QtGui.QFontDatabase.families():
        raise RuntimeError("No fonts available; refuse to record invalid visual evidence")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    with TemporaryDirectory(prefix="ux-fixtures-", dir=scratch) as temporary, ExitStack() as stack:
        for target, value in (
            ("configs.app_state.load_state", {}),
            ("ui.coaching.mode_composition.load_state", {}),
            ("configs.pitchers.load_pitchers", []),
            ("ui.team.team_manager.load_pitchers", []),
            ("app.services.rig_profile.RigProfileService.load_active", None),
        ):
            stack.enter_context(patch(target, return_value=value))
        stack.enter_context(patch("ui.coaching.coach_window.QtPipelineService", DisplayOnlyPipeline))
        build_evidence(app, Path(temporary), output, records)
    manifest = {
        "schema_version": "ux_baseline.v1", "synthetic_only": True,
        "source_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "source_worktree_dirty": bool(subprocess.check_output(["git", "status", "--porcelain"], cwd=ROOT)),
        "python": platform.python_version(), "qt": QtCore.qVersion(),
        "platform": app.platformName(), "theme_tokens": asdict(get_style_manager().theme),
        "available_font_families": QtGui.QFontDatabase.families(),
        "limitations": ["Display-only service/state fixtures; no lifecycle executed",
                        "Review pitch list and schematic frames injected; no recordings loaded",
                        "Setup stages rendered directly; prerequisites not marked passed",
                        "Offscreen pixels are not Windows DPI, screen-reader or hardware validation"],
        "captures": records,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, manifest["source_commit"])
    print(f"Captured {len(records)} synthetic baseline images in {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
