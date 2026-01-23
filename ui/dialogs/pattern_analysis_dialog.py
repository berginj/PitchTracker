"""Pattern analysis dialog for displaying pitch pattern detection results."""

from __future__ import annotations

import json
import subprocess
import sys
import webbrowser
from pathlib import Path
from typing import TYPE_CHECKING

from PySide6 import QtCore, QtWidgets

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
        """Initialize pattern analysis dialog.

        Args:
            parent: Parent widget
            session_dir: Path to session directory
            pitcher_id: Optional pitcher ID for baseline comparison
        """
        super().__init__(parent)
        self.setWindowTitle("Pattern Analysis")
        self.resize(800, 600)
        self.session_dir = session_dir
        self.pitcher_id = pitcher_id
        self.analysis_report: PatternAnalysisReport | None = None

        # Create tab widget
        self.tabs = QtWidgets.QTabWidget()

        # Summary tab
        self.summary_text = QtWidgets.QTextEdit()
        self.summary_text.setReadOnly(True)
        self.tabs.addTab(self.summary_text, "Summary")

        # Anomalies tab
        self.anomalies_table = QtWidgets.QTableWidget()
        self.anomalies_table.setColumnCount(4)
        self.anomalies_table.setHorizontalHeaderLabels(
            ["Pitch ID", "Type", "Severity", "Details"]
        )
        self.anomalies_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.tabs.addTab(self.anomalies_table, "Anomalies")

        # Pitch Classification tab
        self.classification_table = QtWidgets.QTableWidget()
        self.classification_table.setColumnCount(4)
        self.classification_table.setHorizontalHeaderLabels(
            ["Pitch ID", "Type", "Confidence", "Features"]
        )
        self.classification_table.horizontalHeader().setSectionResizeMode(
            QtWidgets.QHeaderView.Stretch
        )
        self.tabs.addTab(self.classification_table, "Pitch Types")

        # Baseline Comparison tab
        self.baseline_text = QtWidgets.QTextEdit()
        self.baseline_text.setReadOnly(True)
        self.tabs.addTab(self.baseline_text, "Baseline Comparison")

        # Buttons
        self.analyze_button = QtWidgets.QPushButton("Run Analysis")
        self.analyze_button.clicked.connect(self._run_analysis)

        self.open_html_button = QtWidgets.QPushButton("Open HTML Report")
        self.open_html_button.clicked.connect(self._open_html_report)
        self.open_html_button.setEnabled(False)

        self.export_json_button = QtWidgets.QPushButton("Export JSON")
        self.export_json_button.clicked.connect(self._export_json)
        self.export_json_button.setEnabled(False)

        self.create_profile_button = QtWidgets.QPushButton("Create Pitcher Profile")
        self.create_profile_button.clicked.connect(self._create_profile)
        self.create_profile_button.setEnabled(False)

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)

        # Layout
        button_row1 = QtWidgets.QHBoxLayout()
        button_row1.addWidget(self.analyze_button)
        button_row1.addWidget(self.open_html_button)
        button_row1.addWidget(self.export_json_button)
        button_row1.addStretch(1)

        button_row2 = QtWidgets.QHBoxLayout()
        button_row2.addWidget(self.create_profile_button)
        button_row2.addStretch(1)
        button_row2.addWidget(close_button)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self.tabs)
        layout.addLayout(button_row1)
        layout.addLayout(button_row2)

        self.setLayout(layout)

        # Status bar
        self.status_label = QtWidgets.QLabel("Ready to analyze")
        layout.addWidget(self.status_label)

    def _run_analysis(self) -> None:
        """Run pattern analysis on the session."""
        self.status_label.setText("Running analysis...")
        self.analyze_button.setEnabled(False)
        QtWidgets.QApplication.processEvents()

        try:
            from analysis.pattern_detection.detector import PatternDetector

            detector = PatternDetector()

            # Run analysis
            self.analysis_report = detector.analyze_session(
                self.session_dir,
                pitcher_id=self.pitcher_id,
                output_json=True,
                output_html=True,
            )

            # Update UI with results
            self._update_summary()
            self._update_anomalies()
            self._update_classifications()
            self._update_baseline()

            # Enable export buttons
            self.open_html_button.setEnabled(True)
            self.export_json_button.setEnabled(True)
            self.create_profile_button.setEnabled(True)

            self.status_label.setText(
                f"Analysis complete: {self.analysis_report.summary.total_pitches} pitches analyzed"
            )

        except Exception as e:
            self.status_label.setText(f"Analysis failed: {e}")
            QtWidgets.QMessageBox.critical(
                self, "Analysis Error", f"Failed to analyze session:\n\n{e}"
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
                text += f"<p><b>{entry.pitch_type}:</b> {entry.count} pitches ({entry.percentage * 100:.1f}%), avg {entry.avg_speed_mph:.1f} mph</p>"
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
            self.anomalies_table.setItem(
                row, 0, QtWidgets.QTableWidgetItem(anomaly.pitch_id)
            )
            self.anomalies_table.setItem(
                row, 1, QtWidgets.QTableWidgetItem(anomaly.anomaly_type)
            )
            self.anomalies_table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(anomaly.severity)
            )
            self.anomalies_table.setItem(
                row, 3, QtWidgets.QTableWidgetItem(json.dumps(anomaly.details))
            )

    def _update_classifications(self) -> None:
        """Update pitch classification tab."""
        if not self.analysis_report:
            return

        classifications = self.analysis_report.pitch_classification
        self.classification_table.setRowCount(len(classifications))

        for row, classification in enumerate(classifications):
            self.classification_table.setItem(
                row, 0, QtWidgets.QTableWidgetItem(classification.pitch_id)
            )
            self.classification_table.setItem(
                row, 1, QtWidgets.QTableWidgetItem(classification.heuristic_type)
            )
            self.classification_table.setItem(
                row, 2, QtWidgets.QTableWidgetItem(f"{classification.confidence:.2f}")
            )
            self.classification_table.setItem(
                row,
                3,
                QtWidgets.QTableWidgetItem(json.dumps(classification.features)),
            )

    def _update_baseline(self) -> None:
        """Update baseline comparison tab."""
        if not self.analysis_report or not self.analysis_report.baseline_comparison:
            self.baseline_text.setHtml("<p>No baseline profile available</p>")
            return

        baseline = self.analysis_report.baseline_comparison

        if not baseline.profile_exists:
            self.baseline_text.setHtml("<p>No baseline profile exists for this pitcher</p>")
            return

        text = "<h2>Baseline Comparison</h2>"

        # Velocity comparison
        velocity = baseline.velocity_vs_baseline
        text += f"""
<h3>Velocity</h3>
<ul>
<li><b>Current:</b> {velocity['current']:.1f} mph</li>
<li><b>Baseline:</b> {velocity['baseline']:.1f} mph</li>
<li><b>Delta:</b> {velocity['delta_mph']:.1f} mph</li>
<li><b>Status:</b> {velocity['status']}</li>
</ul>
"""

        # Strike percentage
        strike = baseline.strike_percentage_vs_baseline
        text += f"""
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
            QtWidgets.QMessageBox.warning(
                self, "Report Not Found", "HTML report not found. Run analysis first."
            )

    def _export_json(self) -> None:
        """Export analysis report to JSON file."""
        json_path = self.session_dir / "analysis_report.json"
        if not json_path.exists():
            QtWidgets.QMessageBox.warning(
                self, "Report Not Found", "JSON report not found. Run analysis first."
            )
            return

        # Ask user where to save
        save_path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Analysis Report",
            str(json_path.name),
            "JSON Files (*.json)",
        )

        if save_path:
            import shutil

            shutil.copy(json_path, save_path)
            QtWidgets.QMessageBox.information(
                self, "Export Complete", f"Report exported to:\n{save_path}"
            )

    def _create_profile(self) -> None:
        """Create or update pitcher profile."""
        # Ask for pitcher ID if not provided
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

            # Create profile from this session
            detector.create_pitcher_profile(pitcher_id, [self.session_dir])

            QtWidgets.QMessageBox.information(
                self,
                "Profile Created",
                f"Pitcher profile created/updated for: {pitcher_id}",
            )

            # Re-run analysis with profile
            self.pitcher_id = pitcher_id
            self._run_analysis()

        except Exception as e:
            QtWidgets.QMessageBox.critical(
                self, "Profile Error", f"Failed to create profile:\n\n{e}"
            )


__all__ = ["PatternAnalysisDialog"]
