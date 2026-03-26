"""Session summary dialog with pitch statistics and heatmap."""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from ui.themes import (
    apply_standard_layout,
    build_dialog_header,
    get_style_manager,
    polish_form_controls,
    style_data_table,
)


class SessionSummaryDialog(QtWidgets.QDialog):
    """Dialog displaying session statistics with heatmap and pitch table."""

    def __init__(
        self,
        parent: QtWidgets.QWidget | None,
        summary,
        on_upload: Callable,
        on_save: Callable,
        session_dir: Optional[Path] = None,
    ) -> None:
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self.setWindowTitle("Session Summary")
        self.resize(900, 680)
        self._on_upload = on_upload
        self._on_save = on_save
        self._summary = summary

        if session_dir is None:
            session_dir = Path("recordings") / summary.session_id
        self._session_dir = session_dir

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the session summary dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)

        layout.addWidget(
            build_dialog_header(
                "Session Summary",
                f"{self._summary.session_id} • {self._summary.pitch_count} pitches reviewed",
                eyebrow="Review",
            )
        )

        layout.addLayout(self._build_metric_cards())

        content_splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Vertical)
        content_splitter.addWidget(self._build_heatmap_panel())
        content_splitter.addWidget(self._build_pitch_table_panel())
        content_splitter.setSizes([220, 420])
        layout.addWidget(content_splitter, 1)

        export_row = QtWidgets.QHBoxLayout()

        self._export_combo = QtWidgets.QComboBox()
        self._export_combo.addItem("Session Summary (JSON)", "summary_json")
        self._export_combo.addItem("Session Summary (CSV)", "summary_csv")
        self._export_combo.addItem("Training Report (JSON)", "training_report")
        self._export_combo.addItem("Manifests (ZIP)", "manifests_zip")
        self._style_manager.style_input(self._export_combo)

        save_button = QtWidgets.QPushButton("Save Session")
        self._style_manager.style_button(save_button, "primary")
        save_button.clicked.connect(lambda: self._on_save(self._export_combo.currentData()))

        upload_button = QtWidgets.QPushButton("Upload Session")
        self._style_manager.style_button(upload_button, "success")
        upload_button.clicked.connect(lambda: self._on_upload(self._summary))

        analyze_button = QtWidgets.QPushButton("Analyze Patterns")
        self._style_manager.style_button(analyze_button, "ghost")
        analyze_button.clicked.connect(self._on_analyze_patterns)

        close_button = QtWidgets.QPushButton("Close")
        self._style_manager.style_button(close_button, "ghost")
        close_button.clicked.connect(self.accept)

        export_row.addWidget(self._export_combo, 1)
        export_row.addWidget(save_button)
        export_row.addWidget(upload_button)
        export_row.addStretch()
        export_row.addWidget(analyze_button)
        export_row.addWidget(close_button)
        layout.addLayout(export_row)

        polish_form_controls(self)

    def _build_metric_cards(self) -> QtWidgets.QHBoxLayout:
        """Build top-line metric cards."""
        layout = QtWidgets.QHBoxLayout()
        cards = [
            ("Pitches", str(self._summary.pitch_count)),
            ("Strikes", str(self._summary.strikes)),
            ("Balls", str(self._summary.balls)),
            (
                "Strike Rate",
                f"{(self._summary.strikes / max(self._summary.pitch_count, 1)) * 100:.0f}%",
            ),
        ]
        for label, value in cards:
            card = QtWidgets.QFrame()
            self._style_manager.style_panel(card, "normal")
            card_layout = QtWidgets.QVBoxLayout(card)
            card_layout.setContentsMargins(14, 12, 14, 12)
            eyebrow = QtWidgets.QLabel(label)
            self._style_manager.style_label(eyebrow, "eyebrow")
            metric = QtWidgets.QLabel(value)
            self._style_manager.style_label(metric, "metricAccent")
            card_layout.addWidget(eyebrow)
            card_layout.addWidget(metric)
            layout.addWidget(card)
        return layout

    def _build_heatmap_panel(self) -> QtWidgets.QWidget:
        """Build the strike-zone heatmap panel."""
        panel = QtWidgets.QFrame()
        self._style_manager.style_panel(panel, "normal")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)

        title = QtWidgets.QLabel("Strike Zone Heatmap")
        self._style_manager.style_label(title, "sectionTitle")
        layout.addWidget(title)

        heatmap = QtWidgets.QTableWidget(3, 3)
        style_data_table(heatmap, sortable=False, stretch_last=False, select_rows=False)
        heatmap.setHorizontalHeaderLabels(["Inside", "Middle", "Outside"])
        heatmap.setVerticalHeaderLabels(["Top", "Middle", "Bottom"])
        heatmap.verticalHeader().setVisible(True)
        heatmap.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        heatmap.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        heatmap.setMinimumHeight(180)

        max_count = max(max(row) for row in self._summary.heatmap) if self._summary.heatmap else 0
        theme = self._style_manager.theme
        cool = QtGui.QColor(theme.accent_primary_dim)
        hot = QtGui.QColor(theme.accent_primary)

        for row in range(3):
            for col in range(3):
                value = self._summary.heatmap[row][col]
                item = QtWidgets.QTableWidgetItem(str(value))
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                if max_count > 0 and value > 0:
                    weight = value / max_count
                    color = QtGui.QColor(
                        int(cool.red() + (hot.red() - cool.red()) * weight),
                        int(cool.green() + (hot.green() - cool.green()) * weight),
                        int(cool.blue() + (hot.blue() - cool.blue()) * weight),
                    )
                    item.setBackground(color)
                heatmap.setItem(row, col, item)

        layout.addWidget(heatmap)
        return panel

    def _build_pitch_table_panel(self) -> QtWidgets.QWidget:
        """Build the detailed pitch table panel."""
        panel = QtWidgets.QFrame()
        self._style_manager.style_panel(panel, "normal")
        layout = QtWidgets.QVBoxLayout(panel)
        layout.setContentsMargins(14, 12, 14, 14)

        title = QtWidgets.QLabel("Pitch Details")
        self._style_manager.style_label(title, "sectionTitle")
        layout.addWidget(title)

        table = QtWidgets.QTableWidget(len(self._summary.pitches), 7)
        style_data_table(table)
        table.setHorizontalHeaderLabels(
            ["Pitch", "Strike", "Zone", "Run (in)", "Rise (in)", "Speed", "Rotation"]
        )
        table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        table.setMinimumHeight(320)

        for row, pitch in enumerate(self._summary.pitches):
            zone = "-"
            if pitch.zone_row is not None and pitch.zone_col is not None:
                zone = f"{pitch.zone_row},{pitch.zone_col}"

            values = [
                pitch.pitch_id,
                "Yes" if pitch.is_strike else "No",
                zone,
                f"{pitch.run_in:.2f}",
                f"{pitch.rise_in:.2f}",
                f"{pitch.speed_mph:.1f}" if pitch.speed_mph is not None else "-",
                f"{pitch.rotation_rpm:.1f}" if pitch.rotation_rpm is not None else "-",
            ]

            for col, value in enumerate(values):
                item = QtWidgets.QTableWidgetItem(str(value))
                if col > 0:
                    item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                table.setItem(row, col, item)

        layout.addWidget(table)
        return panel

    def _on_analyze_patterns(self) -> None:
        """Open pattern analysis dialog."""
        from ui.dialogs.pattern_analysis_dialog import PatternAnalysisDialog

        dialog = PatternAnalysisDialog(self, self._session_dir)
        dialog.exec()


__all__ = ["SessionSummaryDialog"]
