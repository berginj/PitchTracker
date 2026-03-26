"""Session analytics dashboard for post-session review.

Displays comprehensive session statistics including:
- Velocity trends over time
- Location heat maps
- Pitch type breakdown
- Fatigue progression
- Key performance metrics
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

# Try to import matplotlib for charts (optional)
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure
    import matplotlib.pyplot as plt
    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from typing import TYPE_CHECKING

from analysis.pattern_detection.pitch_classifier import classify_pitch_heuristic

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary, SessionSummary


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


class SessionDashboard(QtWidgets.QWidget):
    """Comprehensive session analytics dashboard.

    Shows detailed statistics and visualizations for a completed session.
    Can be embedded in other windows or shown as a dialog.
    """

    def __init__(
        self,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._pitches: List["PitchSummary"] = []
        self._session_name = ""
        self._pitcher_name = ""

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        """Build the dashboard UI."""
        # Header with session info
        self._header = self._build_header()

        # Stats cards row
        self._stats_row = self._build_stats_cards()

        # Main content with charts
        charts_layout = QtWidgets.QHBoxLayout()

        # Left side: Velocity chart
        self._velocity_chart = self._build_velocity_chart()
        charts_layout.addWidget(self._velocity_chart, 2)

        # Right side: Heat map and pitch type breakdown
        right_side = QtWidgets.QVBoxLayout()

        self._heat_map = self._build_heat_map()
        right_side.addWidget(self._heat_map)

        self._pitch_type_chart = self._build_pitch_type_chart()
        right_side.addWidget(self._pitch_type_chart)

        charts_layout.addLayout(right_side, 1)

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(16)

        layout.addWidget(self._header)
        layout.addLayout(self._stats_row)
        layout.addLayout(charts_layout, 1)

        self.setLayout(layout)

    def _build_header(self) -> QtWidgets.QWidget:
        """Build header with session information."""
        widget = QtWidgets.QWidget()

        self._title_label = QtWidgets.QLabel("SESSION SUMMARY")
        self._title_label.setObjectName("dashboard_title")

        self._session_info = QtWidgets.QLabel("")
        self._session_info.setObjectName("dashboard_session_info")

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 8)
        layout.addWidget(self._title_label)
        layout.addWidget(self._session_info)

        widget.setLayout(layout)
        return widget

    def _build_stats_cards(self) -> QtWidgets.QHBoxLayout:
        """Build row of stats cards."""
        layout = QtWidgets.QHBoxLayout()
        layout.setSpacing(12)

        # Create stat cards
        self._avg_velocity_card = self._create_stat_card("AVG VELOCITY", "--", "mph")
        self._max_velocity_card = self._create_stat_card("MAX VELOCITY", "--", "mph")
        self._strike_pct_card = self._create_stat_card("STRIKE %", "--", "%")
        self._total_pitches_card = self._create_stat_card("TOTAL PITCHES", "--", "")

        layout.addWidget(self._avg_velocity_card)
        layout.addWidget(self._max_velocity_card)
        layout.addWidget(self._strike_pct_card)
        layout.addWidget(self._total_pitches_card)
        layout.addStretch()

        return layout

    def _create_stat_card(
        self,
        label: str,
        value: str,
        unit: str,
    ) -> QtWidgets.QFrame:
        """Create a stats card widget.

        Args:
            label: Card title/label
            value: Main value to display
            unit: Unit suffix

        Returns:
            Configured QFrame widget
        """
        card = QtWidgets.QFrame()
        card.setObjectName("stat_card")
        card.setMinimumWidth(140)

        label_widget = QtWidgets.QLabel(label)
        label_widget.setObjectName("stat_card_label")

        value_widget = QtWidgets.QLabel(value)
        value_widget.setObjectName("stat_card_value")
        value_widget.setProperty("stat_value", True)

        unit_widget = QtWidgets.QLabel(unit)
        unit_widget.setObjectName("stat_card_unit")

        # Store references for updates
        card.value_label = value_widget
        card.unit_label = unit_widget

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(4)
        layout.addWidget(label_widget)

        value_row = QtWidgets.QHBoxLayout()
        value_row.addWidget(value_widget)
        value_row.addWidget(unit_widget)
        value_row.addStretch()
        layout.addLayout(value_row)

        card.setLayout(layout)
        return card

    def _build_velocity_chart(self) -> QtWidgets.QWidget:
        """Build velocity over time chart."""
        widget = QtWidgets.QFrame()
        widget.setObjectName("chart_container")

        title = QtWidgets.QLabel("VELOCITY OVER TIME")
        title.setObjectName("chart_title")

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(title)

        if HAS_MATPLOTLIB:
            # Create matplotlib figure
            self._velocity_figure = Figure(figsize=(6, 3), dpi=100)
            self._velocity_figure.patch.set_facecolor('#0a0e14')
            self._velocity_canvas = FigureCanvas(self._velocity_figure)
            self._velocity_canvas.setMinimumHeight(200)
            layout.addWidget(self._velocity_canvas)
        else:
            # Fallback without matplotlib
            placeholder = QtWidgets.QLabel("Velocity chart requires matplotlib")
            placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(200)
            layout.addWidget(placeholder)

        widget.setLayout(layout)
        return widget

    def _build_heat_map(self) -> QtWidgets.QWidget:
        """Build strike zone heat map."""
        widget = QtWidgets.QFrame()
        widget.setObjectName("chart_container")

        title = QtWidgets.QLabel("LOCATION HEAT MAP")
        title.setObjectName("chart_title")

        # Use simple grid for heat map
        self._heat_map_grid = HeatMapGrid()
        self._heat_map_grid.setMinimumSize(180, 180)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(title)
        layout.addWidget(self._heat_map_grid, 1)

        widget.setLayout(layout)
        return widget

    def _build_pitch_type_chart(self) -> QtWidgets.QWidget:
        """Build pitch type breakdown chart."""
        widget = QtWidgets.QFrame()
        widget.setObjectName("chart_container")

        title = QtWidgets.QLabel("PITCH TYPE BREAKDOWN")
        title.setObjectName("chart_title")

        self._pitch_type_list = QtWidgets.QWidget()
        self._pitch_type_layout = QtWidgets.QVBoxLayout()
        self._pitch_type_layout.setSpacing(4)
        self._pitch_type_list.setLayout(self._pitch_type_layout)

        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(12, 8, 12, 8)
        layout.addWidget(title)
        layout.addWidget(self._pitch_type_list)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _apply_style(self) -> None:
        """Apply glass-themed styling."""
        try:
            from ui.themes import get_style_manager
            sm = get_style_manager()
            theme = sm.theme

            self.setStyleSheet(f"""
                SessionDashboard {{
                    background-color: {theme.background_dark};
                }}

                #dashboard_title {{
                    font-size: 18px;
                    font-weight: bold;
                    color: {theme.text_primary};
                }}

                #dashboard_session_info {{
                    font-size: 12px;
                    color: {theme.text_secondary};
                }}

                #stat_card {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                }}

                #stat_card_label {{
                    font-size: 10px;
                    color: {theme.text_muted};
                }}

                #stat_card_value {{
                    font-size: 24px;
                    font-weight: bold;
                    color: {theme.accent_primary};
                }}

                #stat_card_unit {{
                    font-size: 12px;
                    color: {theme.text_secondary};
                    padding-top: 8px;
                }}

                #chart_container {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                }}

                #chart_title {{
                    font-size: 11px;
                    font-weight: bold;
                    color: {theme.accent_primary};
                    padding-bottom: 4px;
                }}
            """)
        except ImportError:
            pass

    def load_session(
        self,
        session_name: str,
        pitcher_name: str,
        pitches: List["PitchSummary"],
    ) -> None:
        """Load session data into dashboard.

        Args:
            session_name: Name of the session
            pitcher_name: Name of the pitcher
            pitches: List of pitch summaries
        """
        self._session_name = session_name
        self._pitcher_name = pitcher_name
        self._pitches = pitches

        # Update header
        timestamp = datetime.now().strftime("%B %d, %Y")
        self._session_info.setText(f"{pitcher_name} - {session_name} - {timestamp}")

        # Compute and display stats
        stats = self._compute_stats(pitches)
        self._update_stats_cards(stats)

        # Update charts
        self._update_velocity_chart(pitches)
        self._update_heat_map(pitches)
        self._update_pitch_type_chart(pitches)

    def _compute_stats(self, pitches: List["PitchSummary"]) -> DashboardStats:
        """Compute statistics from pitches.

        Args:
            pitches: List of pitch summaries

        Returns:
            Computed statistics
        """
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

        strikes = sum(1 for p in pitches if p.is_strike)
        balls = len(pitches) - strikes
        strike_pct = (strikes / len(pitches)) * 100 if pitches else 0.0

        velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
        avg_velocity = np.mean(velocities) if velocities else None
        max_velocity = max(velocities) if velocities else None
        min_velocity = min(velocities) if velocities else None
        velocity_std = np.std(velocities) if len(velocities) > 1 else None

        h_movements = [p.run_in for p in pitches]
        v_movements = [p.rise_in for p in pitches]

        return DashboardStats(
            total_pitches=len(pitches),
            strikes=strikes,
            balls=balls,
            strike_pct=strike_pct,
            avg_velocity=avg_velocity,
            max_velocity=max_velocity,
            min_velocity=min_velocity,
            velocity_std=velocity_std,
            avg_h_movement=np.mean(h_movements) if h_movements else 0.0,
            avg_v_movement=np.mean(v_movements) if v_movements else 0.0,
        )

    def _update_stats_cards(self, stats: DashboardStats) -> None:
        """Update stats cards with computed values.

        Args:
            stats: Computed statistics
        """
        # Avg velocity
        if stats.avg_velocity is not None:
            self._avg_velocity_card.value_label.setText(f"{stats.avg_velocity:.1f}")
        else:
            self._avg_velocity_card.value_label.setText("--")

        # Max velocity
        if stats.max_velocity is not None:
            self._max_velocity_card.value_label.setText(f"{stats.max_velocity:.1f}")
        else:
            self._max_velocity_card.value_label.setText("--")

        # Strike %
        self._strike_pct_card.value_label.setText(f"{stats.strike_pct:.0f}")

        # Total pitches
        self._total_pitches_card.value_label.setText(str(stats.total_pitches))

    def _update_velocity_chart(self, pitches: List["PitchSummary"]) -> None:
        """Update velocity over time chart.

        Args:
            pitches: List of pitch summaries
        """
        if not HAS_MATPLOTLIB:
            return

        velocities = [p.speed_mph for p in pitches if p.speed_mph is not None]
        if not velocities:
            return

        self._velocity_figure.clear()
        ax = self._velocity_figure.add_subplot(111)

        # Style for dark theme
        ax.set_facecolor('#0a0e14')
        ax.tick_params(colors='#ffffff80')
        ax.spines['bottom'].set_color('#ffffff30')
        ax.spines['left'].set_color('#ffffff30')
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)

        # Plot velocity
        x = list(range(1, len(velocities) + 1))
        ax.plot(x, velocities, color='#64C8FF', linewidth=2, marker='o', markersize=4)

        # Add trend line
        if len(velocities) > 2:
            z = np.polyfit(x, velocities, 1)
            p = np.poly1d(z)
            ax.plot(x, p(x), color='#FF6B6B', linewidth=1, linestyle='--', alpha=0.7)

        ax.set_xlabel('Pitch #', color='#ffffff80', fontsize=9)
        ax.set_ylabel('Velocity (mph)', color='#ffffff80', fontsize=9)

        self._velocity_figure.tight_layout()
        self._velocity_canvas.draw()

    def _update_heat_map(self, pitches: List["PitchSummary"]) -> None:
        """Update location heat map.

        Args:
            pitches: List of pitch summaries
        """
        # Count pitches in each zone (3x3 grid)
        zone_counts = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]

        for pitch in pitches:
            if pitch.zone_row is not None and pitch.zone_col is not None:
                row = min(max(pitch.zone_row, 0), 2)
                col = min(max(pitch.zone_col, 0), 2)
                zone_counts[row][col] += 1

        self._heat_map_grid.set_counts(zone_counts)

    def _update_pitch_type_chart(self, pitches: List["PitchSummary"]) -> None:
        """Update pitch type breakdown.

        Args:
            pitches: List of pitch summaries
        """
        # Clear existing items
        while self._pitch_type_layout.count():
            item = self._pitch_type_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        if not pitches:
            return

        # Classify pitches using heuristic classifier
        pitch_type_counts: dict = {}
        pitch_type_colors = {
            "Fastball (4-seam)": "#FF6B6B",
            "Fastball": "#FF8E8E",
            "Sinker": "#FFA07A",
            "Cutter": "#FFB347",
            "Slider": "#64C8FF",
            "Changeup": "#4FFFB0",
            "Curveball": "#9B59B6",
            "Curveball (slow)": "#8E44AD",
            "Unknown": "#888888",
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
            color = pitch_type_colors.get(pitch_type, "#888888")
            self._add_pitch_type_row(pitch_type, count, len(pitches), color)

    def _add_pitch_type_row(
        self,
        label: str,
        count: int,
        total: int,
        color: str,
    ) -> None:
        """Add a row to pitch type breakdown.

        Args:
            label: Type label
            count: Count of this type
            total: Total pitches
            color: Bar color
        """
        pct = (count / total * 100) if total > 0 else 0

        row = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 2, 0, 2)

        label_widget = QtWidgets.QLabel(f"{label}")
        label_widget.setStyleSheet("color: rgba(255, 255, 255, 0.8); font-size: 10px;")
        label_widget.setMinimumWidth(60)

        bar = QtWidgets.QProgressBar()
        bar.setMinimum(0)
        bar.setMaximum(100)
        bar.setValue(int(pct))
        bar.setTextVisible(False)
        bar.setMaximumHeight(12)
        bar.setStyleSheet(f"""
            QProgressBar {{
                background-color: rgba(255, 255, 255, 0.1);
                border-radius: 3px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
                border-radius: 3px;
            }}
        """)

        pct_label = QtWidgets.QLabel(f"{pct:.0f}%")
        pct_label.setStyleSheet("color: rgba(255, 255, 255, 0.6); font-size: 10px;")
        pct_label.setMinimumWidth(35)

        layout.addWidget(label_widget)
        layout.addWidget(bar, 1)
        layout.addWidget(pct_label)

        row.setLayout(layout)
        self._pitch_type_layout.addWidget(row)


class HeatMapGrid(QtWidgets.QWidget):
    """3x3 heat map grid widget for strike zone visualization."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._counts = [[0, 0, 0], [0, 0, 0], [0, 0, 0]]
        self._max_count = 1

    def set_counts(self, counts: List[List[int]]) -> None:
        """Set zone counts.

        Args:
            counts: 3x3 grid of pitch counts
        """
        self._counts = counts
        self._max_count = max(max(row) for row in counts) or 1
        self.update()

    def paintEvent(self, event: QtGui.QPaintEvent) -> None:
        """Paint the heat map grid."""
        painter = QtGui.QPainter(self)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)

        rect = self.rect()
        cell_w = rect.width() / 3
        cell_h = rect.height() / 3

        # Draw cells with heat coloring
        for row in range(3):
            for col in range(3):
                count = self._counts[row][col]
                intensity = count / self._max_count

                # Color gradient from cool blue to hot red
                if intensity < 0.5:
                    r = int(100 * intensity * 2)
                    g = int(200 * intensity * 2)
                    b = 255
                else:
                    r = 255
                    g = int(200 * (1 - intensity) * 2)
                    b = int(100 * (1 - intensity) * 2)

                color = QtGui.QColor(r, g, b, int(100 + intensity * 155))

                cell_rect = QtCore.QRectF(
                    col * cell_w,
                    (2 - row) * cell_h,  # Flip Y so bottom is row 0
                    cell_w,
                    cell_h,
                )

                painter.fillRect(cell_rect, color)

                # Draw border
                painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 40), 1))
                painter.drawRect(cell_rect)

                # Draw count
                if count > 0:
                    painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255, 200)))
                    painter.drawText(cell_rect, QtCore.Qt.AlignmentFlag.AlignCenter, str(count))

        painter.end()


__all__ = ["SessionDashboard", "HeatMapGrid"]
