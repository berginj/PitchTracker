"""UX-07 actual-widget evidence using disposable, synthetic inputs only."""

from contextlib import chdir
from dataclasses import replace
import json
import os
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6 import QtCore, QtGui, QtWidgets  # noqa: E402
from app.contracts import SessionSummary  # noqa: E402
from launcher import LauncherWindow  # noqa: E402
from scripts.capture_ux_baseline import capture, synthetic_pitches, write_gallery  # noqa: E402
from ui.analytics.session_dashboard import SessionDashboard  # noqa: E402
from ui.analytics.comparison_dashboard import ComparisonDashboardDialog  # noqa: E402
from ui.analytics.comparison_data import load_pitcher_stats  # noqa: E402
from ui.dialogs.recording_settings_dialog import RecordingSettingsDialog  # noqa: E402
from ui.dialogs.session_summary_dialog import SessionSummaryDialog  # noqa: E402
from ui.review.pipeline_comparison_dialog import PipelineComparisonDialog  # noqa: E402
from ui.review.fit_batch_dialog import FitBatchDialog  # noqa: E402
from ui.themes import get_style_manager  # noqa: E402
from ui.workspace.secondary import WorkspaceHelpDialog, WorkspaceSettingsDialog  # noqa: E402


class EmptyHistory:
    def _load_summaries_for_pitcher(self, pitcher_id: str, days: int):
        return []


def main():
    output = ROOT / "docs/review/ux/ux07"
    output.mkdir(parents=True, exist_ok=True)
    scratch = ROOT / "screenshots"
    scratch.mkdir(exist_ok=True)
    app = QtWidgets.QApplication([])
    for font in ("SegUIVar.ttf", "segoeui.ttf", "segoeuib.ttf", "seguisb.ttf"):
        QtGui.QFontDatabase.addApplicationFont(f"C:/Windows/Fonts/{font}")
    get_style_manager().apply_to_app(app)
    records: list[dict[str, object]] = []
    widgets = []

    def save(widget, page, state, *, reveal=None):
        widgets.append(widget)
        capture(app, widget, page, state, output, records, reveal_widget=reveal)

    with TemporaryDirectory(prefix="ux07-", dir=scratch) as temporary, chdir(temporary):
        pitches = synthetic_pitches()
        pitches[1] = replace(pitches[1], measurement_status="REJECTED", observation_rejection_reasons=["Synthetic tracking gap"])
        pitches[2] = replace(pitches[2], measurement_status="UNAVAILABLE", speed_mph=None, strike_call_available=False)
        pitches[3] = replace(pitches[3], zone_row=0, zone_col=2, strike_call_available=False,
                             strike_call_reason="Synthetic incomplete plate coverage")
        analytics = SessionDashboard()
        save(analytics, "analytics", "empty")
        analytics.load_session("Synthetic completed session", "Example recorded player", pitches)
        save(analytics, "analytics", "partial-speeds")
        analytics._tabs.setCurrentWidget(analytics._table)
        save(analytics, "analytics", "partial-table")
        analytics._tabs.setCurrentWidget(analytics._heat_map_grid)
        save(analytics, "analytics", "zone-counts")

        comparison = ComparisonDashboardDialog()
        comparison.dashboard.add_pitcher(load_pitcher_stats(EmptyHistory(), "example", "Missing recorded history"))
        save(comparison, "comparison", "history-unavailable")

        launcher = LauncherWindow(backend="sim", background_tasks=False)
        widgets.append(launcher)
        settings = WorkspaceSettingsDialog(launcher, launcher._build_footer(), lambda: None)
        save(settings, "settings", "idle")
        save(WorkspaceHelpDialog(page="setup"), "help", "setup-guide")
        save(WorkspaceHelpDialog(docs_root=Path(temporary) / "missing-docs"), "help", "guide-unavailable")

        save(RecordingSettingsDialog(None, "Synthetic bullpen", "./selected-output", 60), "recording-dialog", "defaults")
        summary = SessionSummary("Synthetic completed session", len(pitches), 0, 0, [[0] * 3 for _ in range(3)], pitches)
        save(SessionSummaryDialog(None, summary, lambda value: None, lambda kind: None,
                                  session_dir=Path(temporary)), "summary-dialog", "partial-results")

        advanced = PipelineComparisonDialog()
        save(advanced, "advanced-comparison", "no-report")
        advanced._show({"status": "failed", "results": [{
            "session_id": "synthetic-session", "variant": "optional detector", "status": "unavailable",
            "reason": "Synthetic model bundle unavailable", "metrics": {
                "recall": None, "center_error_px": {"p95": None}, "target_error_ft": {"p95": None},
                "completed_opportunities": 0, "opportunities": 12}, "detector_roundtrip_ms": {"p95": None}}]})
        save(advanced, "advanced-comparison", "failed-opportunities", reveal=advanced.details)
        save(FitBatchDialog(None, "synthetic-completed-session"), "advanced-refits", "no-jobs")

        for widget in reversed(widgets):
            widget.close()
            widget.deleteLater()
        app.sendPostedEvents(None, QtCore.QEvent.Type.DeferredDelete)
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    manifest = {"schema_version": "ux07_captures.v1", "source_commit": commit, "source_worktree_dirty": True,
                "synthetic_only": True, "renderer": "Actual PySide6 widgets / offscreen Qt / Windows fonts",
                "before_evidence": "../baseline/index.html",
                "limitations": ["No cameras, private artifacts, worker jobs or uploads",
                                "Synthetic captures do not qualify Windows DPI or screen readers"], "captures": records}
    (output / "manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    write_gallery(output, records, commit, package="UX-07", heading="Secondary surfaces · synthetic captures",
                  specification="../UX_07_IMPLEMENTATION.md")
    print(f"Saved {len(records)} secondary captures to {output.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
