"""Accessible session analytics from recorded summaries, without refitting."""

from __future__ import annotations

from collections import Counter

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from app.contracts import PitchSummary, measurement_is_usable
from ui.measurement_presentation import displayed_speed, recorded_outcome, recorded_status, speed_provenance
from ui.themes import build_dialog_header, get_style_manager, style_data_table

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
except ImportError:
    HAS_MATPLOTLIB = False
else:
    HAS_MATPLOTLIB = True


class StatCard(QtWidgets.QFrame):
    def __init__(self, title: str, unit: str) -> None:
        super().__init__()
        sm = get_style_manager()
        sm.style_panel(self)
        layout = QtWidgets.QVBoxLayout(self)
        label = QtWidgets.QLabel(title)
        label.setWordWrap(True)
        sm.style_label(label, "eyebrow")
        self.value_label = QtWidgets.QLabel("Unavailable")
        sm.style_label(self.value_label, "metricAccent")
        self.unit_label = QtWidgets.QLabel(unit)
        layout.addWidget(label)
        layout.addWidget(self.value_label)
        layout.addWidget(self.unit_label)


class SessionDashboard(QtWidgets.QWidget):
    """Charts and a keyboard-readable table of the same recorded pitch selection."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self._pitches: list[PitchSummary] = []
        self._theme = get_style_manager().theme
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(build_dialog_header("Session Summary", "Recorded results · no physical accuracy approval"))
        self._session_info = QtWidgets.QLabel()
        self._session_info.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        self._session_info.setWordWrap(True)
        layout.addWidget(self._session_info)
        stats = QtWidgets.QGridLayout()
        self._avg_velocity_card = StatCard("Average speed", "mph")
        self._max_velocity_card = StatCard("Maximum speed", "mph")
        self._strike_pct_card = StatCard("Strike rate", "% of available calls")
        self._total_pitches_card = StatCard("Recorded pitches", "includes unavailable / rejected")
        for index, card in enumerate((self._avg_velocity_card, self._max_velocity_card,
                                      self._strike_pct_card, self._total_pitches_card)):
            stats.addWidget(card, index // 2, index % 2)
        layout.addLayout(stats)
        self._coverage = QtWidgets.QLabel()
        self._coverage.setWordWrap(True)
        self._coverage.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        layout.addWidget(self._coverage)
        self._tabs = QtWidgets.QTabWidget()
        self._tabs.setAccessibleName("Session analytics views")
        if HAS_MATPLOTLIB:
            self._velocity_figure = Figure(figsize=(6, 3), dpi=100)
            self._velocity_canvas = FigureCanvas(self._velocity_figure)
            self._velocity_canvas.setMinimumSize(0, 120)
            self._velocity_canvas.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored,
                                                QtWidgets.QSizePolicy.Policy.Expanding)
            self._velocity_canvas.setAccessibleName("Recorded speed chart; equivalent values in Pitch table")
            self._tabs.addTab(self._velocity_canvas, "Speed (mph)")
        else:
            label = QtWidgets.QLabel("Chart unavailable: matplotlib is not installed. Use the Pitch table.")
            label.setWordWrap(True)
            self._tabs.addTab(label, "Speed (mph)")
        self._heat_map_grid = HeatMapGrid()
        self._tabs.addTab(self._heat_map_grid, "Zone counts")
        self._table = QtWidgets.QTableWidget(0, 7)
        self._table.setAccessibleName("Recorded pitches and speed chart values")
        style_data_table(self._table, sortable=False)
        self._table.setHorizontalHeaderLabels(
            ["Pitch", "Speed (mph)", "Source / reference", "Result", "Status", "Zone row, col", "Reason"])
        self._table.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.ResizeToContents)
        self._tabs.addTab(self._table, "Pitch table")
        layout.addWidget(self._tabs, 1)
        self.load_session("No session selected", "", [])

    def load_session(self, session_name: str, pitcher_name: str, pitches: list[PitchSummary]) -> None:
        self._pitches = list(pitches)
        self._session_info.setText(f"{session_name} · {pitcher_name or 'Recorded player unavailable'}")
        speeds = [speed for pitch in pitches if (speed := displayed_speed(pitch)) is not None]
        sources = {speed_provenance(pitch) for pitch in pitches if displayed_speed(pitch) is not None}
        compatible = len(sources) == 1
        self._avg_velocity_card.value_label.setText(f"{np.mean(speeds):.1f}" if compatible else "Unavailable")
        self._max_velocity_card.value_label.setText(f"{max(speeds):.1f}" if compatible else "Unavailable")
        calls = [pitch for pitch in pitches if measurement_is_usable(pitch) and pitch.strike_call_available]
        strikes = sum(pitch.is_strike for pitch in calls)
        self._strike_pct_card.value_label.setText(f"{100 * strikes / len(calls):.0f}" if calls else "Unavailable")
        self._total_pitches_card.value_label.setText(str(len(pitches)))
        counts = [[0] * 3 for _ in range(3)]
        for pitch in pitches:
            if (measurement_is_usable(pitch) and pitch.zone_row in (0, 1, 2) and pitch.zone_col in (0, 1, 2)):
                assert pitch.zone_row is not None and pitch.zone_col is not None
                counts[pitch.zone_row][pitch.zone_col] += 1
        located = sum(map(sum, counts))
        statuses = "; ".join(f"{status}: {count}" for status, count in Counter(map(recorded_status, pitches)).items())
        provenance = next(iter(sources)) if compatible else "Mixed speed sources/references; combined speed unavailable"
        if not speeds:
            provenance = "No eligible recorded speed"
        self._coverage.setText(
            f"{len(speeds)}/{len(pitches)} speeds · {len(calls)}/{len(pitches)} calls "
            f"({strikes} strikes, {len(calls) - strikes} balls) · {located}/{len(pitches)} in-grid locations.\n"
            f"{provenance}. {statuses or 'No recorded pitches'}. Movement unavailable without validation.")
        self._heat_map_grid.set_counts(counts)
        self._update_table()
        self._update_velocity_chart()

    def _update_table(self) -> None:
        self._table.setRowCount(len(self._pitches))
        for row, pitch in enumerate(self._pitches):
            speed = displayed_speed(pitch)
            has_zone = (measurement_is_usable(pitch) and pitch.zone_row in (0, 1, 2) and pitch.zone_col in (0, 1, 2))
            zone = f"{pitch.zone_row}, {pitch.zone_col}" if has_zone else "Unavailable"
            reason = pitch.strike_call_reason or "; ".join(
                pitch.observation_rejection_reasons or pitch.observation_warning_reasons or [])
            for col, value in enumerate((pitch.pitch_id, f"{speed:.1f}" if speed is not None else "Unavailable",
                                         speed_provenance(pitch), recorded_outcome(pitch), recorded_status(pitch), zone, reason)):
                self._table.setItem(row, col, QtWidgets.QTableWidgetItem(value))

    def _update_velocity_chart(self) -> None:
        if not HAS_MATPLOTLIB:
            return
        self._velocity_figure.clear()
        ax = self._velocity_figure.add_subplot(111)
        ax.set_facecolor(self._theme.chart_background)
        self._velocity_figure.patch.set_facecolor(self._theme.surface_base)
        ax.tick_params(colors=self._theme.text_secondary)
        ax.spines[["top", "right"]].set_visible(False)
        sources = list(dict.fromkeys(speed_provenance(p) for p in self._pitches if displayed_speed(p) is not None))
        colors = (self._theme.chart_blue, self._theme.chart_green, self._theme.chart_orange)
        for index, source in enumerate(sources):
            values = [displayed_speed(p) if speed_provenance(p) == source else None for p in self._pitches]
            ax.plot(range(1, len(values) + 1), [v if v is not None else np.nan for v in values],
                    marker="o", color=colors[index % len(colors)], label=source)
        if sources:
            ax.legend(fontsize=9)
        else:
            ax.text(.5, .5, "No eligible speed data", transform=ax.transAxes, ha="center", color=self._theme.text_secondary)
        ax.set_xlabel("Recorded pitch number (gaps retained)")
        ax.set_ylabel("Speed (mph)")
        self._velocity_figure.tight_layout()
        self._velocity_canvas.draw()


class HeatMapGrid(QtWidgets.QTableWidget):
    """Text and color equivalent of canonical zero-based recorded zone counts."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(3, 3, parent)
        self.setAccessibleName("Zone counts; row zero is bottom, column zero is negative x")
        style_data_table(self, sortable=False, stretch_last=False, select_rows=False)
        self.setHorizontalHeaderLabels(["Negative x · col 0", "Center · col 1", "Positive x · col 2"])
        self.setVerticalHeaderLabels(["Top · row 2", "Middle · row 1", "Bottom · row 0"])
        self.verticalHeader().show()
        self.horizontalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.verticalHeader().setSectionResizeMode(QtWidgets.QHeaderView.ResizeMode.Stretch)
        self.set_counts([[0] * 3 for _ in range(3)])

    def set_counts(self, counts: list[list[int]]) -> None:
        theme = get_style_manager().theme
        maximum = max(map(max, counts)) or 1
        for row in range(3):
            for col in range(3):
                count = counts[row][col]
                item = QtWidgets.QTableWidgetItem(str(count))
                item.setTextAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
                item.setBackground(QtGui.QColor(theme.accent_primary_dim if count else theme.surface_base))
                item.setForeground(QtGui.QColor(theme.text_primary))
                font = item.font()
                font.setBold(count == maximum)
                item.setFont(font)
                self.setItem(2 - row, col, item)


__all__ = ["SessionDashboard", "HeatMapGrid"]
