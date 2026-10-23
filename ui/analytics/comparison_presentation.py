"""Reusable card and chart presentation for the comparison dashboard."""

from __future__ import annotations

from typing import Mapping, Optional, Protocol

import numpy as np
from PySide6 import QtCore, QtWidgets

from .comparison_data import PitcherStats, format_metric
from ui.themes import get_style_manager, polish_form_controls


class ChartCanvas(Protocol):
    def draw(self) -> None: ...


class PitcherComparisonCard(QtWidgets.QFrame):
    """Card showing a single pitcher's stats for comparison."""

    remove_requested = QtCore.Signal(str)

    def __init__(
        self,
        stats: PitcherStats,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._stats = stats
        from ui.themes import get_style_manager

        self._theme = get_style_manager().theme
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        header_layout = QtWidgets.QHBoxLayout()
        name_label = QtWidgets.QLabel(self._stats.display_name)
        name_label.setTextFormat(QtCore.Qt.TextFormat.PlainText)
        name_label.setObjectName("comparison_card_name")

        remove_btn = QtWidgets.QPushButton("X")
        remove_btn.setObjectName("comparison_card_remove")
        remove_btn.setAccessibleName(f"Remove {self._stats.display_name} from comparison")
        remove_btn.setToolTip(f"Remove {self._stats.display_name}")
        remove_btn.setMinimumSize(self._theme.button_height_sm, self._theme.button_height_sm)
        remove_btn.setAccessibleDescription("Remove this player from the browsed comparison only.")
        remove_btn.clicked.connect(lambda: self.remove_requested.emit(self._stats.pitcher_id))

        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(remove_btn)

        stats_layout = QtWidgets.QGridLayout()
        rows = (
            ("Session mean speed (mph):", format_metric(self._stats.avg_velocity)),
            ("Maximum speed (mph):", format_metric(self._stats.max_velocity)),
            ("Session mean strike %:", format_metric(self._stats.avg_strike_pct, scale=100)),
            ("Recorded consistency %:", format_metric(self._stats.avg_consistency, scale=100)),
            ("Sessions:", f"{self._stats.sessions_count}"),
            ("Total Pitches:", f"{self._stats.total_pitches}"),
        )
        for row, (label_text, value_text) in enumerate(rows):
            stats_layout.addWidget(self._create_stat_label(label_text), row, 0)
            stats_layout.addWidget(self._create_stat_value(value_text), row, 1)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(
            self._theme.margin_normal,
            self._theme.margin_normal,
            self._theme.margin_normal,
            self._theme.margin_normal,
        )
        layout.addLayout(header_layout)
        layout.addLayout(stats_layout)
        layout.addStretch()
        self.setMinimumWidth(self._theme.button_height_lg * 4)

    @staticmethod
    def _create_stat_label(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("comparison_stat_label")
        return label

    @staticmethod
    def _create_stat_value(text: str) -> QtWidgets.QLabel:
        label = QtWidgets.QLabel(text)
        label.setObjectName("comparison_stat_value")
        return label

    def _apply_style(self) -> None:
        sm = get_style_manager()
        sm.style_panel(self)
        for label in self.findChildren(QtWidgets.QLabel):
            sm.style_label(label, "sectionTitle" if label.objectName() == "comparison_card_name" else "muted")
        polish_form_controls(self)

    @property
    def stats(self) -> PitcherStats:
        """Get pitcher stats."""
        return self._stats


class ComparisonChartPresenter:
    """Render comparison data into the dashboard's matplotlib figures."""

    def __init__(
        self,
        theme,
        velocity_figure,
        velocity_canvas: ChartCanvas,
        accuracy_figure,
        accuracy_canvas: ChartCanvas,
    ) -> None:
        self._theme = theme
        self._velocity_figure = velocity_figure
        self._velocity_canvas = velocity_canvas
        self._accuracy_figure = accuracy_figure
        self._accuracy_canvas = accuracy_canvas

    def update(self, stats_by_id: Mapping[str, PitcherStats]) -> None:
        """Refresh both charts from the ordered pitcher mapping."""
        stats = list(stats_by_id.values())
        self._update_velocity(stats)
        self._update_accuracy(stats)

    def _prepare_axis(self, figure, canvas: ChartCanvas, has_data: bool):
        figure.clear()
        axis = figure.add_subplot(111)
        axis.set_facecolor(self._theme.chart_background)
        axis.tick_params(colors=self._theme.text_muted)
        axis.spines["bottom"].set_color(self._theme.border_glass)
        axis.spines["left"].set_color(self._theme.border_glass)
        axis.spines["top"].set_visible(False)
        axis.spines["right"].set_visible(False)
        if not has_data:
            axis.text(
                0.5,
                0.5,
                "Add pitchers to compare",
                ha="center",
                va="center",
                color=self._theme.text_muted,
                transform=axis.transAxes,
            )
            canvas.draw()
        return axis

    def _update_velocity(self, stats: list[PitcherStats]) -> None:
        axis = self._prepare_axis(self._velocity_figure, self._velocity_canvas, bool(stats))
        if not stats:
            return
        names = [item.display_name for item in stats]
        positions = np.arange(len(names))
        width = 0.35
        axis.bar(
            positions - width / 2,
            [item.avg_velocity if item.avg_velocity is not None else np.nan for item in stats],
            width,
            label="Avg",
            color=self._theme.chart_blue,
            alpha=0.8,
        )
        axis.bar(
            positions + width / 2,
            [item.max_velocity if item.max_velocity is not None else np.nan for item in stats],
            width,
            label="Max",
            color=self._theme.chart_green,
            alpha=0.8,
        )
        self._finish_axis(axis, names, "Velocity (mph)")
        for position, item in enumerate(stats):
            if item.avg_velocity is None and item.max_velocity is None:
                axis.text(position, .05, "Unavailable", transform=axis.get_xaxis_transform(), ha="center", fontsize=9)
        axis.legend(loc="upper right", fontsize=self._theme.font_size_caption)
        self._velocity_figure.tight_layout()
        self._velocity_canvas.draw()

    def _update_accuracy(self, stats: list[PitcherStats]) -> None:
        axis = self._prepare_axis(self._accuracy_figure, self._accuracy_canvas, bool(stats))
        if not stats:
            return
        names = [item.display_name for item in stats]
        strike_pcts = [item.avg_strike_pct * 100 if item.avg_strike_pct is not None else np.nan for item in stats]
        colors = [self._accuracy_color(percent) for percent in strike_pcts]
        positions = np.arange(len(names))
        axis.bar(positions, strike_pcts, color=colors, alpha=0.8)
        self._finish_axis(axis, names, "Session mean strike %")
        for position, item in enumerate(stats):
            if item.avg_strike_pct is None:
                axis.text(position, .05, "Unavailable", transform=axis.get_xaxis_transform(), ha="center", fontsize=9)
        self._accuracy_figure.tight_layout()
        self._accuracy_canvas.draw()

    def _finish_axis(self, axis, names: list[str], ylabel: str) -> None:
        positions = np.arange(len(names))
        axis.set_ylabel(ylabel, color=self._theme.text_muted, fontsize=self._theme.font_size_caption)
        axis.set_xticks(positions)
        axis.set_xticklabels(
            names,
            rotation=45,
            ha="right",
            fontsize=self._theme.font_size_caption,
        )

    def _accuracy_color(self, percent: float) -> str:
        return str(self._theme.chart_blue)
