"""Pattern analysis dialog for displaying pitch pattern detection results."""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtWidgets

from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    polish_form_controls,
    show_message_dialog,
    style_data_table,
    style_message_panel,
    style_status_label,
)

if TYPE_CHECKING:
    from analysis.pattern_detection.schemas import PatternAnalysisReport


class PatternAnalysisDialog(QtWidgets.QDialog):
    """Dialog displaying pattern detection analysis results."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        session_dir: Path,
        pitcher_id: str | None = None,
    ) -> None:
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self.setWindowTitle("Pattern Analysis")
        self.resize(960, 720)
        self.session_dir = session_dir
        self.pitcher_id = pitcher_id
        self.analysis_report: PatternAnalysisReport | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the analysis dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)

        layout.addWidget(
            build_dialog_header(
                "Pattern Analysis",
                f"Analyze session data from {self.session_dir.name}.",
                eyebrow="Insights",
            )
        )

        self.tabs = QtWidgets.QTabWidget()

        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setReadOnly(True)
        style_message_panel(self.summary_text, "info", "Run analysis to generate a summary.")
        self.tabs.addTab(self.summary_text, "Summary")

        self.anomalies_table = QtWidgets.QTableWidget()
        self.anomalies_table.setColumnCount(4)
        self.anomalies_table.setHorizontalHeaderLabels(["Pitch ID", "Type", "Severity", "Details"])
        style_data_table(self.anomalies_table)
        self.anomalies_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.anomalies_table, "Anomalies")

        self.classification_table = QtWidgets.QTableWidget()
        self.classification_table.setColumnCount(4)
        self.classification_table.setHorizontalHeaderLabels(["Pitch ID", "Type", "Confidence", "Features"])
        style_data_table(self.classification_table)
        self.classification_table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.tabs.addTab(self.classification_table, "Pitch Types")

        self.baseline_text = QtWidgets.QTextEdit()
        self.baseline_text.setReadOnly(True)
        style_message_panel(self.baseline_text, "info", "Run analysis to compare against a baseline profile.")
        self.tabs.addTab(self.baseline_text, "Baseline Comparison")

        layout.addWidget(self.tabs, 1)

        button_row = QtWidgets.QHBoxLayout()
        button_row.setSpacing(10)

        self.analyze_button = QtWidgets.QPushButton("Run Analysis")
        self._style_manager.style_button(self.analyze_button, "primary")
        self.analyze_button.clicked.connect(self._run_analysis)

        self.open_html_button = QtWidgets.QPushButton("Open HTML Report")
        self._style_manager.style_button(self.open_html_button, "ghost")
        self.open_html_button.clicked.connect(self._open_html_report)
        self.open_html_button.setEnabled(False)

        self.export_json_button = QtWidgets.QPushButton("Export JSON")
        self._style_manager.style_button(self.export_json_button, "ghost")
        self.export_json_button.clicked.connect(self._export_json)
        self.export_json_button.setEnabled(False)

        self.create_profile_button = QtWidgets.QPushButton("Create Pitcher Profile")
        self._style_manager.style_button(self.create_profile_button, "success")
        self.create_profile_button.clicked.connect(self._create_profile)
        self.create_profile_button.setEnabled(False)

        close_button = QtWidgets.QPushButton("Close")
        self._style_manager.style_button(close_button, "ghost")
        close_button.clicked.connect(self.accept)

        button_row.addWidget(self.analyze_button)
        button_row.addWidget(self.open_html_button)
        button_row.addWidget(self.export_json_button)
        button_row.addWidget(self.create_profile_button)
        button_row.addStretch()
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.status_label = QtWidgets.QLabel("Ready to analyze.")
        style_status_label(self.status_label, "info", "Ready to analyze.")
        layout.addWidget(self.status_label)

        polish_form_controls(self)

    def _set_status(self, text: str, tone: str = "info") -> None:
        """Update analysis status."""
        style_status_label(self.status_label, tone, text)

    def _run_analysis(self) -> None:
        """Run pattern analysis on the session."""
        self._set_status("Running analysis...", "warning")
        self.analyze_button.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            from analysis.pattern_detection.detector import PatternDetector

            detector = PatternDetector()
            self.analysis_report = detector.analyze_session(
                self.session_dir,
                pitcher_id=self.pitcher_id,
                output_json=True,
                output_html=True,
            )

            self._update_summary()
            self._update_anomalies()
            self._update_classifications()
            self._update_baseline()

            self.open_html_button.setEnabled(True)
            self.export_json_button.setEnabled(True)
            self.create_profile_button.setEnabled(True)
            self._set_status(
                f"Analysis complete: {self.analysis_report.summary.total_pitches} pitches analyzed",
                "success",
            )

        except Exception as exc:
            self._set_status(f"Analysis failed: {exc}", "error")
            show_message_dialog(
                self,
                "Analysis Error",
                f"Failed to analyze session:\n\n{exc}",
                tone="error",
            )
        finally:
            self.analyze_button.setEnabled(True)

    def _update_summary(self) -> None:
        """Update summary tab with analysis results."""
        if not self.analysis_report:
            return

        summary = self.analysis_report.summary
        consistency = self.analysis_report.consistency_metrics
        repertoire = self.analysis_report.pitch_repertoire

        text = f"""
<h2>Session Summary</h2>
<p><b>Session ID:</b> {self.analysis_report.session_id}</p>
<p><b>Pitcher ID:</b> {self.analysis_report.pitcher_id or 'N/A'}</p>

<h3>Overview</h3>
<ul>
<li><b>Total Pitches:</b> {summary.total_pitches}</li>
<li><b>Average Velocity:</b> {summary.average_velocity_mph:.1f} mph</li>
<li><b>Strike Percentage:</b> {summary.strike_percentage * 100:.1f}%</li>
<li><b>Anomalies Detected:</b> {summary.anomalies_detected}</li>
<li><b>Pitch Types Detected:</b> {summary.pitch_types_detected}</li>
</ul>

<h3>Consistency Metrics</h3>
<ul>
<li><b>Velocity Std Dev:</b> {consistency.velocity_std_mph:.2f} mph</li>
<li><b>Velocity CV:</b> {consistency.velocity_cv:.3f}</li>
<li><b>Movement Consistency:</b> {consistency.movement_consistency_score:.3f}</li>
</ul>

<h3>Pitch Repertoire</h3>
"""
        if repertoire:
            for entry in repertoire:
                text += (
                    f"<p><b>{entry.pitch_type}:</b> {entry.count} pitches "
                    f"({entry.percentage * 100:.1f}%), avg {entry.avg_speed_mph:.1f} mph</p>"
                )
        else:
            text += "<p>No pitch types classified</p>"

        self.summary_text.setHtml(text)

    def _update_anomalies(self) -> None:
        """Update anomalies tab with detected anomalies."""
        if not self.analysis_report:
            return

        anomalies = self.analysis_report.anomalies
        self.anomalies_table.setRowCount(len(anomalies))
        for row, anomaly in enumerate(anomalies):
            self.anomalies_table.setItem(row, 0, QtWidgets.QTableWidgetItem(anomaly.pitch_id))
            self.anomalies_table.setItem(row, 1, QtWidgets.QTableWidgetItem(anomaly.anomaly_type))
            self.anomalies_table.setItem(row, 2, QtWidgets.QTableWidgetItem(anomaly.severity))
            self.anomalies_table.setItem(row, 3, QtWidgets.QTableWidgetItem(json.dumps(anomaly.details)))
        self.anomalies_table.resizeRowsToContents()

    def _update_classifications(self) -> None:
        """Update pitch classification tab."""
        if not self.analysis_report:
            return

        classifications = self.analysis_report.pitch_classification
        self.classification_table.setRowCount(len(classifications))
        for row, classification in enumerate(classifications):
            self.classification_table.setItem(row, 0, QtWidgets.QTableWidgetItem(classification.pitch_id))
            self.classification_table.setItem(row, 1, QtWidgets.QTableWidgetItem(classification.heuristic_type))
            self.classification_table.setItem(
                row,
                2,
                QtWidgets.QTableWidgetItem(f"{classification.confidence:.2f}"),
            )
            self.classification_table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(json.dumps(classification.features)),
            )
        self.classification_table.resizeRowsToContents()

    def _update_baseline(self) -> None:
        """Update baseline comparison tab."""
        if not self.analysis_report or not self.analysis_report.baseline_comparison:
            self.baseline_text.setHtml("<p>No baseline profile available.</p>")
            return

        baseline = self.analysis_report.baseline_comparison
        if not baseline.profile_exists:
            self.baseline_text.setHtml("<p>No baseline profile exists for this pitcher.</p>")
            return

        velocity = baseline.velocity_vs_baseline
        strike = baseline.strike_percentage_vs_baseline
        if velocity is None or strike is None:
            self.baseline_text.setHtml("<p>Baseline comparison is incomplete.</p>")
            return
        text = f"""
<h2>Baseline Comparison</h2>
<h3>Velocity</h3>
<ul>
<li><b>Current:</b> {velocity['current']:.1f} mph</li>
<li><b>Baseline:</b> {velocity['baseline']:.1f} mph</li>
<li><b>Delta:</b> {velocity['delta_mph']:.1f} mph</li>
<li><b>Status:</b> {velocity['status']}</li>
</ul>

<h3>Strike Percentage</h3>
<ul>
<li><b>Current:</b> {strike['current'] * 100:.1f}%</li>
<li><b>Baseline:</b> {strike['baseline'] * 100:.1f}%</li>
<li><b>Delta:</b> {strike['delta'] * 100:.1f}%</li>
<li><b>Status:</b> {strike['status']}</li>
</ul>
"""
        self.baseline_text.setHtml(text)

    def _open_html_report(self) -> None:
        """Open HTML report in default browser."""
        html_path = self.session_dir / "analysis_report.html"
        if html_path.exists():
            webbrowser.open(html_path.as_uri())
        else:
            show_message_dialog(
                self,
                "Report Not Found",
                "HTML report not found. Run analysis first.",
                tone="warning",
            )

    def _export_json(self) -> None:
        """Export analysis report to a JSON file."""
        json_path = self.session_dir / "analysis_report.json"
        if not json_path.exists():
            show_message_dialog(
                self,
                "Report Not Found",
                "JSON report not found. Run analysis first.",
                tone="warning",
            )
            return

        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Analysis Report",
            str(json_path.name),
            "JSON Files (*.json)",
        )

        if save_path:
            import shutil

            shutil.copy(json_path, save_path)
            show_message_dialog(
                self,
                "Export Complete",
                f"Report exported to:\n{save_path}",
                tone="success",
            )

    def _create_profile(self) -> None:
        """Create or update a pitcher profile."""
        pitcher_id = self.pitcher_id
        if not pitcher_id:
            pitcher_id, ok = QtWidgets.QInputDialog.getText(
                self,
                "Pitcher ID",
                "Enter pitcher ID for profile:",
            )
            if not ok or not pitcher_id:
                return

        try:
            from analysis.pattern_detection.detector import PatternDetector

            detector = PatternDetector()
            detector.create_pitcher_profile(pitcher_id, [self.session_dir])

            show_message_dialog(
                self,
                "Profile Created",
                f"Pitcher profile created or updated for: {pitcher_id}",
                tone="success",
            )

            self.pitcher_id = pitcher_id
            self._run_analysis()

        except Exception as exc:
            show_message_dialog(
                self,
                "Profile Error",
                f"Failed to create profile:\n\n{exc}",
                tone="error",
            )


__all__ = ["PatternAnalysisDialog"]
