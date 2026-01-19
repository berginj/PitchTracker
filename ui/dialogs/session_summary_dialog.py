"""Session summary dialog with pitch statistics and heatmap."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6 import QtCore, QtWidgets


class SessionSummaryDialog(QtWidgets.QDialog):
    """Dialog displaying session statistics with strike zone heatmap and pitch table."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        summary,
        on_upload: Callable,
        on_save: Callable,
        session_dir: Optional[Path] = None,
    ) -> None:
        """Initialize session summary dialog.

        Args:
            parent: Parent widget
            summary: SessionSummary object with pitch statistics
            on_upload: Callback for upload button (receives summary)
            on_save: Callback for save button (receives export format string)
            session_dir: Optional session directory path (derived from session_id if not provided)
        """
        super().__init__(parent)
        self.setWindowTitle("Session Summary")
        self.resize(680, 520)
        self._on_upload = on_upload
        self._on_save = on_save
        self._summary = summary

        # Derive session directory if not provided
        if session_dir is None:
            session_dir = Path("recordings") / summary.session_id
        self._session_dir = session_dir

        # Header with session stats
        header = QtWidgets.QLabel(
            f"Session: {summary.session_id} | "
            f"Pitches: {summary.pitch_count} | "
            f"Strikes: {summary.strikes} | "
            f"Balls: {summary.balls}"
        )

        # Strike zone heatmap (3x3 grid)
        heatmap = QtWidgets.QTableWidget(3, 3)
        heatmap.setHorizontalHeaderLabels(["Inside", "Middle", "Outside"])
        heatmap.setVerticalHeaderLabels(["Top", "Middle", "Bottom"])
        heatmap.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)
        heatmap.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        for row in range(3):
            for col in range(3):
                value = summary.heatmap[row][col]
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setTextAlignment(QtCore.Qt.AlignCenter)
                heatmap.setItem(row, col, item)

        # Pitch summary table
        table = QtWidgets.QTableWidget(len(summary.pitches), 7)
        table.setHorizontalHeaderLabels(
            ["Pitch", "Strike", "Zone", "Run (in)", "Rise (in)", "Speed", "Rotation"]
        )
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.Stretch)

        for row, pitch in enumerate(summary.pitches):
            zone = "-"
            if pitch.zone_row is not None and pitch.zone_col is not None:
                zone = f"{pitch.zone_row},{pitch.zone_col}"

            values = [
                pitch.pitch_id,
                "Y" if pitch.is_strike else "N",
                zone,
                f"{pitch.run_in:.2f}",
                f"{pitch.rise_in:.2f}",
                f"{pitch.speed_mph:.1f}" if pitch.speed_mph is not None else "-",
                f"{pitch.rotation_rpm:.1f}" if pitch.rotation_rpm is not None else "-",
            ]

            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col > 0:
                    item.setTextAlignment(QtCore.Qt.AlignCenter)
                table.setItem(row, col, item)

        # Export controls
        export_combo = QtWidgets.QComboBox()
        export_combo.addItem("Session Summary (JSON)", "summary_json")
        export_combo.addItem("Session Summary (CSV)", "summary_csv")
        export_combo.addItem("Training Report (JSON)", "training_report")
        export_combo.addItem("Manifests (ZIP)", "manifests_zip")

        save_button = QtWidgets.QPushButton("Save Session")
        save_button.clicked.connect(lambda: self._on_save(export_combo.currentData()))

        close_button = QtWidgets.QPushButton("Close")
        close_button.clicked.connect(self.accept)

        upload_button = QtWidgets.QPushButton("Upload Session")
        upload_button.clicked.connect(lambda: self._on_upload(summary))

        analyze_button = QtWidgets.QPushButton("Analyze Patterns")
        analyze_button.clicked.connect(self._on_analyze_patterns)

        # Layout
        layout = QtWidgets.QVBoxLayout()

        top_row = QtWidgets.QHBoxLayout()
        top_row.addWidget(header)
        top_row.addStretch(1)

        export_layout = QtWidgets.QVBoxLayout()
        export_layout.addWidget(save_button)
        export_layout.addWidget(export_combo)
        top_row.addLayout(export_layout)

        layout.addLayout(top_row)
        layout.addWidget(QtWidgets.QLabel("Strike Zone Heatmap"))
        layout.addWidget(heatmap)
        layout.addWidget(QtWidgets.QLabel("Pitch Summary"))
        layout.addWidget(table)

        button_row = QtWidgets.QHBoxLayout()
        button_row.addWidget(analyze_button)
        button_row.addWidget(upload_button)
        button_row.addStretch(1)
        button_row.addWidget(close_button)
        layout.addLayout(button_row)

        self.setLayout(layout)

    def _on_analyze_patterns(self) -> None:
        """Open pattern analysis dialog."""
        from ui.dialogs.pattern_analysis_dialog import PatternAnalysisDialog

        dialog = PatternAnalysisDialog(self, self._session_dir)
        dialog.exec()


__all__ = ["SessionSummaryDialog"]
