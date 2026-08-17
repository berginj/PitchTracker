"""Session analytics dashboard for post-session review."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import TYPE_CHECKING, List, Optional

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

from ui.themes import get_style_manager, style_progress_bar

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from analysis.pattern_detection.pitch_classifier import classify_pitch_heuristic

if TYPE_CHECKING:
    from app.contracts import PitchSummary


@dataclass
class DashboardStats:
    """Computed statistics for dashboard display."""

    total_pitches: int
    strikes: int
    balls: int
    strike_pct: float
    avg_velocity: Optional[float]
    max_velocity: Optional[float]
    min_velocity: Optional[float]
    velocity_std: Optional[float]
    avg_h_movement: float
    avg_v_movement: float


class StatCard(QtWidgets.QFrame):
    """Metric card with explicit label ownership."""

    def __init__(self) -> None:
        super().__init__()
        self.value_label = QtWidgets.QLabel()
        self.unit_label = QtWidgets.QLabel()


class SessionDashboard(QtWidgets.QWidget):
    """Comprehensive session analytics dashboard."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._theme = self._style_manager.theme
        self._pitches: List["PitchSummary"] = []
        self._session_name = ""
        self._pitcher_name = ""

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the dashboard UI."""
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)

        self._header = self._build_header()
        self._stats_row = self._build_stats_cards()

        charts_layout = QtWidgets.QHBoxLayout()
        self._velocity_chart = self._build_velocity_chart()
        charts_layout.addWidget(self._velocity_chart, 2)

        right_side = QtWidgets.QVBoxLayout()
        self._heat_map = self._build_heat_map()
        right_side.addWidget(self._heat_map)
        self._pitch_type_chart = self._build_pitch_type_chart()
        right_side.addWidget(self._pitch_type_chart)

        charts_layout.addLayout(right_side, 1)

        layout.addWidget(self._header)
        layout.addLayout(self._stats_row)
        layout.addLayout(charts_layout, 1)

    def _build_header(self) -> QtWidgets.QWidget:
        """Build header with session information."""
        widget = QtWidgets.QFrame()
        self._style_manager.style_panel(widget, "bold")

        self._title_label = QtWidgets.QLabel("Session Summary")
        self._style_manager.style_label(self._title_label, "pageTitle")

        self._session_info = QtWidgets.QLabel("")
        self._style_manager.style_label(self._session_info, "muted")

        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.addWidget(self._title_label)
        layout.addWidget(self._session_info)
        return widget

    def _build_stats_cards(self) -> QtWidgets.QHBoxLayout:
        """Build row of stats cards."""
        layout = QtWidgets.QHBoxLayout()
        self._avg_velocity_card = self._create_stat_card("Avg Velocity", "--", "mph")
        self._max_velocity_card = self._create_stat_card("Max Velocity", "--", "mph")
        self._strike_pct_card = self._create_stat_card("Strike Rate", "--", "%")
        self._total_pitches_card = self._create_stat_card("Total Pitches", "--", "")

        for card in (
            self._avg_velocity_card,
            self._max_velocity_card,
            self._strike_pct_card,
            self._total_pitches_card,
        ):
            layout.addWidget(card)
        return layout

    def _create_stat_card(self, label: str, value: str, unit: str) -> StatCard:
        """Create a stats card widget."""
        card = StatCard()
        self._style_manager.style_panel(card, "normal")
        card.setMinimumWidth(150)

        label_widget = QtWidgets.QLabel(label)
        self._style_manager.style_label(label_widget, "eyebrow")

        value_widget = card.value_label
        value_widget.setText(value)
        self._style_manager.style_label(value_widget, "metricAccent")

        unit_widget = card.unit_label
        unit_widget.setText(unit)
        self._style_manager.style_label(unit_widget, "muted")

        layout = QtWidgets.QVBoxLayout(card)
        layout.setContentsMargins(14, 12, 14, 12)
        layout.addWidget(label_widget)

        value_row = QtWidgets.QHBoxLayout()
        value_row.addWidget(value_widget)
        value_row.addWidget(unit_widget)
        value_row.addStretch()
        layout.addLayout(value_row)
        return card

    def _build_chart_shell(self, title: str) -> tuple[QtWidgets.QFrame, QtWidgets.QVBoxLayout]:
        """Create a consistent chart container."""
        widget = QtWidgets.QFrame()
        self._style_manager.style_panel(widget, "normal")

        title_label = QtWidgets.QLabel(title)
        self._style_manager.style_label(title_label, "sectionTitle")

        layout = QtWidgets.QVBoxLayout(widget)
        layout.setContentsMargins(14, 12, 14, 14)
        layout.addWidget(title_label)
        return widget, layout

    def _build_velocity_chart(self) -> QtWidgets.QWidget:
        """Build velocity over time chart."""
        widget, layout = self._build_chart_shell("Velocity Over Time")
        if HAS_MATPLOTLIB:
            self._velocity_figure = Figure(figsize=(6, 3), dpi=100)
            self._velocity_canvas = FigureCanvas(self._velocity_figure)
            self._velocity_canvas.setMinimumHeight(240)
            layout.addWidget(self._velocity_canvas)
        else:
            placeholder = QtWidgets.QLabel("Install matplotlib to view the velocity chart.")
            placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(240)
            self._style_manager.style_label(placeholder, "muted")
            layout.addWidget(placeholder)
        return widget

    def _build_heat_map(self) -> QtWidgets.QWidget:
        """Build strike zone heat map."""
        widget, layout = self._build_chart_shell("Location Heat Map")
        self._heat_map_grid = HeatMapGrid()
        self._heat_map_grid.setMinimumSize(210, 210)
        layout.addWidget(self._heat_map_grid, 1)
        return widget

    def _build_pitch_type_chart(self) -> QtWidgets.QWidget:
        """Build pitch type breakdown chart."""
        widget, layout = self._build_chart_shell("Pitch Breakdown")
        self._pitch_type_list = QtWidgets.QWidget()
        self._pitch_type_layout = QtWidgets.QVBoxLayout(self._pitch_type_list)
        self._pitch_type_layout.setSpacing(8)
        self._pitch_type_layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._pitch_type_list)
        layout.addStretch()
        return widget

    def load_session(
        self,
        session_name: str,
        pitcher_name: str,
        pitches: List["PitchSummary"],
    ) -> None:
        """Load session data into the dashboard."""
        self._session_name = session_name
        self._pitcher_name = pitcher_name
        self._pitches = pitches

        timestamp = datetime.now().strftime("%B %d, %Y")
        self._session_info.setText(f"{pitcher_name} | {session_name} | {timestamp}")

        stats = self._compute_stats(pitches)
        self._update_stats_cards(stats)
        self._update_velocity_chart(pitches)
        self._update_heat_map(pitches)
        self._update_pitch_type_chart(pitches)

    def _compute_stats(self, pitches: List["PitchSummary"]) -> DashboardStats:
        """Compute dashboard statistics from pitches."""
        if not pitches:
            return DashboardStats(
                total_pitches=0,
                strikes=0,
                balls=0,
                strike_pct=0.0,
                avg_velocity=None,
                max_velocity=None,
                min_velocity=None,
                velocity_std=None,
                avg_h_movement=0.0,
                avg_v_movement=0.0,
            )

        strikes = sum(1 for pitch in pitches if pitch.is_strike)
        balls = len(pitches) - strikes
        strike_pct = (strikes / len(pitches)) * 100 if pitches else 0.0

        velocities = [pitch.speed_mph for pitch in pitches if pitch.speed_mph is not None]
        h_movements = [pitch.run_in for pitch in pitches]
        v_movements = [pitch.rise_in for pitch in pitches]

        return DashboardStats(
            total_pitches=len(pitches),
            strikes=strikes,
            balls=balls,
            strike_pct=strike_pct,
            avg_velocity=float(np.mean(velocities)) if velocities else None,
            max_velocity=max(velocities) if velocities else None,
            min_velocity=min(velocities) if velocities else None,
            velocity_std=float(np.std(velocities)) if len(velocities) > 1 else None,
            avg_h_movement=float(np.mean(h_movements)) if h_movements else 0.0,
            avg_v_movement=float(np.mean(v_movements)) if v_movements else 0.0,
        )

    def _update_stats_cards(self, stats: DashboardStats) -> None:
        """Update stats cards with computed values."""
        self._avg_velocity_card.value_label.setText(
            f"{stats.avg_velocity:.1f}" if stats.avg_velocity is not None else "--"
        )
        self._max_velocity_card.value_label.setText(
            f"{stats.max_velocity:.1f}" if stats.max_velocity is not None else "--"
        )
        self._strike_pct_card.value_label.setText(f"{stats.strike_pct:.0f}")
        self._total_pitches_card.value_label.setText(str(stats.total_pitches))

    def _update_velocity_chart(self, pitches: List["PitchSummary"]) -> None:
        """Update velocity-over-time chart."""
        if not HAS_MATPLOTLIB:
            return

        velocities = [pitch.speed_mph for pitch in pitches if pitch.speed_mph is not None]
        self._velocity_figure.clear()
        ax = self._velocity_figure.add_subplot(111)
        ax.set_facecolor(self._theme.surface_base)
        self._velocity_figure.patch.set_facecolor(self._theme.surface_base)

        ax.tick_params(colors=self._theme.text_secondary)
        ax.spines["bottom"].set_color(self._theme.border_glass)
        ax.spines["left"].set_color(self._theme.border_glass)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.grid(True, axis="y", color=self._theme.border_glass, alpha=0.7, linewidth=0.8)

        if velocities:
            x_values = list(range(1, len(velocities) + 1))
            ax.plot(
                x_values,
                velocities,
                color=self._theme.accent_primary,
                linewidth=2.2,
                marker="o",
                markersize=4,
            )

            if len(velocities) > 2:
                trend = np.polyfit(x_values, velocities, 1)
                line = np.poly1d(trend)
                ax.plot(
                    x_values,
                    line(x_values),
                    color=self._theme.accent_warning,
                    linewidth=1.4,
                    linestyle="--",
                )
        else:
            ax.text(
                0.5,
                0.5,
                "No velocity data available",
                transform=ax.transAxes,
                ha="center",
                va="center",
                color=self._theme.text_muted,
            )

        ax.set_xlabel("Pitch #", color=self._theme.text_secondary, fontsize=9)
        ax.set_ylabel("Velocity (mph)", color=self._theme.text_secondary, fontsize=9)
        self._velocity_figure.tight_layout()
        self._velocity_canvas.draw()

    def _normalize_zone_index(self, index: int | None) -> int | None:
        """Normalize zone coordinates coming from either 0-2 or 1-3 semantics."""
        if index is None:
            return None
        if 1 <= index <= 3:
            return index - 1
        return index

    def _update_heat_map(self, pitches: List["PitchSummary"]) -> None:
        """Update location heat map."""
        zone_counts = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        for pitch in pitches:
            row = self._normalize_zone_index(pitch.zone_row)
            col = self._normalize_zone_index(pitch.zone_col)
            if row is not None and col is not None:
                row = min(max(row, 0), 2)
                col = min(max(col, 0), 2)
                zone_counts[row][col] += 1
        self._heat_map_grid.set_counts(zone_counts)

    def _update_pitch_type_chart(self, pitches: List["PitchSummary"]) -> None:
        """Update pitch breakdown rows."""
        while self._pitch_type_layout.count():
            item = self._pitch_type_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()

        if not pitches:
            empty_label = QtWidgets.QLabel("No pitch data available.")
            self._style_manager.style_label(empty_label, "muted")
            self._pitch_type_layout.addWidget(empty_label)
            return

        # Classify pitches using heuristic classifier
        pitch_type_counts: dict = {}
        pitch_type_colors = {
            "Fastball (4-seam)": "success",
            "Fastball": "success",
            "Sinker": "success",
            "Cutter": "info",
            "Slider": "info",
            "Changeup": "warning",
            "Curveball": "primary",
            "Curveball (slow)": "primary",
            "Unknown": "muted",
        }

        for pitch in pitches:
            # Prepare pitch data for classifier
            pitch_data = {
                "speed_mph": pitch.speed_mph,
                "run_in": pitch.run_in,
                "rise_in": pitch.rise_in,
                "pitch_id": getattr(pitch, "pitch_id", "unknown"),
            }

            try:
                classification = classify_pitch_heuristic(pitch_data)
                pitch_type = classification.heuristic_type
            except Exception:
                pitch_type = "Unknown"

            pitch_type_counts[pitch_type] = pitch_type_counts.get(pitch_type, 0) + 1

        # Sort by count (descending)
        sorted_types = sorted(
            pitch_type_counts.items(),
            key=lambda x: x[1],
            reverse=True,
        )

        # Add rows for each pitch type
        for pitch_type, count in sorted_types:
            variant = pitch_type_colors.get(pitch_type, "muted")
            self._add_pitch_type_row(pitch_type, count, len(pitches), variant)

    def _add_pitch_type_row(self, label: str, count: int, total: int, variant: str) -> None:
        """Add a row to the pitch breakdown panel."""
        pct = (count / total * 100) if total > 0 else 0.0

        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)

        label_widget = QtWidgets.QLabel(label)
        label_widget.setMinimumWidth(72)
        self._style_manager.style_label(label_widget, "muted")

        bar = QtWidgets.QProgressBar()
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(int(pct))
        bar.setTextVisible(False)
        bar.setMaximumHeight(10)
        style_progress_bar(bar, variant)

        pct_label = QtWidgets.QLabel(f"{pct:.0f}%")
        pct_label.setMinimumWidth(36)
        self._style_manager.style_label(pct_label, "muted")

        layout.addWidget(label_widget)
        layout.addWidget(bar, 1)
        layout.addWidget(pct_label)
        self._pitch_type_layout.addWidget(row)


class HeatMapGrid(QtWidgets.QWidget):
    """3x3 heat map grid widget for strike zone visualization."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._counts = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self._max_count = 1

    def set_counts(self, counts: List[List[int]]) -> None:
        """Set zone counts for the grid."""
        self._counts = counts
        self._max_count = max(max(row) for row in counts) or 1
        self.update()

    def _blend(self, low: QtGui.QColor, high: QtGui.QColor, weight: float) -> QtGui.QColor:
        """Blend two colors by weight."""
        weight = max(0.0, min(1.0, weight))
        return QtGui.QColor(
            int(low.red() + (high.red() - low.red()) * weight),
            int(low.green() + (high.green() - low.green()) * weight),
            int(low.blue() + (high.blue() - low.blue()) * weight),
        )

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the heat map grid."""
        del event
        theme = get_style_manager().theme
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.RenderHint.Antialiasing)

        rect = self.rect().adjusted(4, 4, -4, -4)
        cell_w = rect.width() / 3
        cell_h = rect.height() / 3
        cool = QtGui.QColor(theme.accent_primary_dim)
        hot = QtGui.QColor(theme.accent_primary)
        border = QtGui.QColor(theme.border_glass)
        text_color = QtGui.QColor(theme.text_primary)

        for row in range(3):
            for col in range(3):
                count = self._counts[row][col]
                intensity = count / self._max_count
                color = self._blend(cool, hot, intensity)
                color.setAlpha(110 + int(intensity * 120))

                cell_rect = QtCore.QRectF(
                    rect.left() + col * cell_w,
                    rect.top() + (2 - row) * cell_h,
                    cell_w,
                    cell_h,
                )

                painter.fillRect(cell_rect, color)
                painter.setPen(QtGui.QPen(border, 1))
                painter.drawRoundedRect(cell_rect, 8, 8)

                if count > 0:
                    painter.setPen(text_color)
                    painter.drawText(
                        cell_rect,
                        QtCore.Qt.AlignmentFlag.AlignCenter,
                        str(count),
                    )

        painter.end()


__all__ = ["SessionDashboard", "HeatMapGrid"]
