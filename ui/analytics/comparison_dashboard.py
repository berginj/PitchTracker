"""Multi-pitcher comparison dashboard.

Provides:
- Side-by-side stat comparison across pitchers
- Bar charts for velocity comparison
- Accuracy comparison visualization
- Export to CSV/PDF
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import numpy as np
from PySide6 import QtCore, QtGui, QtWidgets

# Try to import matplotlib for charts
try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from analysis.trend_analyzer import SessionSummary, TrendAnalyzer
from ui.themes import apply_standard_layout, polish_form_controls, show_message_dialog

logger = logging.getLogger(__name__)


@dataclass
class PitcherStats:
    """Aggregated stats for a pitcher."""

    pitcher_id: str
    display_name: str
    sessions_count: int
    total_pitches: int

    avg_velocity: float
    max_velocity: float
    velocity_std: float

    avg_strike_pct: float
    avg_consistency: float

    # Per-pitch type averages (if available)
    velocity_by_type: Dict[str, float]


class PitcherComparisonCard(QtWidgets.QFrame):
    """Card showing a single pitcher's stats for comparison."""

    remove_requested = QtCore.Signal(str)  # pitcher_id

    def __init__(
        self,
        stats: PitcherStats,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._stats = stats
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        """Build card UI."""
        # Header with name and remove button
        header_layout = QtWidgets.QHBoxLayout()

        name_label = QtWidgets.QLabel(self._stats.display_name)
        name_label.setObjectName("comparison_card_name")

        remove_btn = QtWidgets.QPushButton("X")
        remove_btn.setObjectName("comparison_card_remove")
        remove_btn.setMaximumWidth(24)
        remove_btn.clicked.connect(
            lambda: self.remove_requested.emit(self._stats.pitcher_id)
        )

        header_layout.addWidget(name_label)
        header_layout.addStretch()
        header_layout.addWidget(remove_btn)

        # Stats grid
        stats_layout = QtWidgets.QGridLayout()

        row = 0

        # Velocity stats
        stats_layout.addWidget(
            self._create_stat_label("Avg Velocity:"), row, 0
        )
        stats_layout.addWidget(
            self._create_stat_value(f"{self._stats.avg_velocity:.1f} mph"),
            row,
            1,
        )
        row += 1

        stats_layout.addWidget(
            self._create_stat_label("Max Velocity:"), row, 0
        )
        stats_layout.addWidget(
            self._create_stat_value(f"{self._stats.max_velocity:.1f} mph"),
            row,
            1,
        )
        row += 1

        # Accuracy stats
        stats_layout.addWidget(
            self._create_stat_label("Strike %:"), row, 0
        )
        stats_layout.addWidget(
            self._create_stat_value(f"{self._stats.avg_strike_pct * 100:.1f}%"),
            row,
            1,
        )
        row += 1

        # Consistency
        stats_layout.addWidget(
            self._create_stat_label("Consistency:"), row, 0
        )
        stats_layout.addWidget(
            self._create_stat_value(f"{self._stats.avg_consistency * 100:.0f}%"),
            row,
            1,
        )
        row += 1

        # Session info
        stats_layout.addWidget(
            self._create_stat_label("Sessions:"), row, 0
        )
        stats_layout.addWidget(
            self._create_stat_value(f"{self._stats.sessions_count}"),
            row,
            1,
        )
        row += 1

        stats_layout.addWidget(
            self._create_stat_label("Total Pitches:"), row, 0
        )
        stats_layout.addWidget(
            self._create_stat_value(f"{self._stats.total_pitches}"),
            row,
            1,
        )

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addLayout(header_layout)
        layout.addLayout(stats_layout)
        layout.addStretch()

        self.setLayout(layout)
        self.setMinimumWidth(180)

    def _create_stat_label(self, text: str) -> QtWidgets.QLabel:
        """Create stat label widget."""
        label = QtWidgets.QLabel(text)
        label.setObjectName("comparison_stat_label")
        return label

    def _create_stat_value(self, text: str) -> QtWidgets.QLabel:
        """Create stat value widget."""
        label = QtWidgets.QLabel(text)
        label.setObjectName("comparison_stat_value")
        return label

    def _apply_style(self) -> None:
        """Apply styling."""
        try:
            from ui.themes import get_style_manager

            theme = get_style_manager().theme

            self.setStyleSheet(f"""
                PitcherComparisonCard {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                }}
                #comparison_card_name {{
                    font-size: 14px;
                    font-weight: bold;
                    color: {theme.text_primary};
                }}
                #comparison_card_remove {{
                    background-color: transparent;
                    border: 1px solid {theme.accent_error_dim};
                    border-radius: 4px;
                    color: {theme.accent_error};
                    font-size: 10px;
                }}
                #comparison_card_remove:hover {{
                    background-color: {theme.accent_error_dim};
                }}
                #comparison_stat_label {{
                    font-size: 11px;
                    color: {theme.text_muted};
                }}
                #comparison_stat_value {{
                    font-size: 11px;
                    font-weight: bold;
                    color: {theme.text_secondary};
                }}
            """)

        except ImportError:
            pass

    @property
    def stats(self) -> PitcherStats:
        """Get pitcher stats."""
        return self._stats


class ComparisonDashboard(QtWidgets.QWidget):
    """Dashboard for comparing stats across multiple pitchers.

    Features:
    - Add/remove pitchers for comparison
    - Bar charts comparing velocities
    - Strike percentage comparison
    - Export to CSV
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._pitcher_stats: Dict[str, PitcherStats] = {}
        self._pitcher_cards: Dict[str, PitcherComparisonCard] = {}
        self._trend_analyzer = TrendAnalyzer()

        from ui.themes import get_style_manager
        self._theme = get_style_manager().theme

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        """Build the dashboard UI."""
        # Header
        header = QtWidgets.QLabel("PITCHER COMPARISON")
        header.setObjectName("comparison_header")

        # Add pitcher section
        add_section = self._build_add_section()

        # Pitcher cards (horizontal scroll)
        self._cards_container = QtWidgets.QWidget()
        self._cards_layout = QtWidgets.QHBoxLayout()
        self._cards_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._cards_container.setLayout(self._cards_layout)

        cards_scroll = QtWidgets.QScrollArea()
        cards_scroll.setWidget(self._cards_container)
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setHorizontalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        cards_scroll.setVerticalScrollBarPolicy(
            QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        cards_scroll.setMaximumHeight(220)
        cards_scroll.setObjectName("comparison_cards_scroll")

        # Charts section
        charts = self._build_charts_section()

        # Export section
        export_section = self._build_export_section()

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(header)
        layout.addWidget(add_section)
        layout.addWidget(cards_scroll)
        layout.addWidget(charts, 1)
        layout.addWidget(export_section)

        self.setLayout(layout)

    def _build_add_section(self) -> QtWidgets.QWidget:
        """Build the add pitcher section."""
        widget = QtWidgets.QWidget()
        widget.setObjectName("comparison_add_section")

        self._pitcher_combo = QtWidgets.QComboBox()
        self._pitcher_combo.setMinimumWidth(200)
        self._pitcher_combo.setPlaceholderText("Select pitcher...")

        add_btn = QtWidgets.QPushButton("+ Add to Comparison")
        add_btn.setObjectName("comparison_add_btn")
        add_btn.clicked.connect(self._on_add_pitcher)

        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._pitcher_combo)
        layout.addWidget(add_btn)
        layout.addStretch()

        widget.setLayout(layout)
        return widget

    def _build_charts_section(self) -> QtWidgets.QWidget:
        """Build the charts section."""
        widget = QtWidgets.QWidget()
        widget.setObjectName("comparison_charts")

        layout = QtWidgets.QHBoxLayout()

        # Velocity comparison chart
        self._velocity_chart = self._build_velocity_chart()
        layout.addWidget(self._velocity_chart, 1)

        # Strike percentage chart
        self._accuracy_chart = self._build_accuracy_chart()
        layout.addWidget(self._accuracy_chart, 1)

        widget.setLayout(layout)
        return widget

    def _build_velocity_chart(self) -> QtWidgets.QWidget:
        """Build velocity comparison chart."""
        widget = QtWidgets.QFrame()
        widget.setObjectName("chart_container")

        title = QtWidgets.QLabel("VELOCITY COMPARISON")
        title.setObjectName("chart_title")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(title)

        if HAS_MATPLOTLIB:
            self._velocity_figure = Figure(figsize=(5, 3), dpi=100)
            self._velocity_figure.patch.set_facecolor(self._theme.background_dark)
            self._velocity_canvas = FigureCanvas(self._velocity_figure)
            self._velocity_canvas.setMinimumHeight(200)
            layout.addWidget(self._velocity_canvas, 1)
        else:
            placeholder = QtWidgets.QLabel(
                "Velocity chart requires matplotlib"
            )
            placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(200)
            layout.addWidget(placeholder, 1)

        widget.setLayout(layout)
        return widget

    def _build_accuracy_chart(self) -> QtWidgets.QWidget:
        """Build accuracy comparison chart."""
        widget = QtWidgets.QFrame()
        widget.setObjectName("chart_container")

        title = QtWidgets.QLabel("STRIKE % COMPARISON")
        title.setObjectName("chart_title")

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(title)

        if HAS_MATPLOTLIB:
            self._accuracy_figure = Figure(figsize=(5, 3), dpi=100)
            self._accuracy_figure.patch.set_facecolor(self._theme.background_dark)
            self._accuracy_canvas = FigureCanvas(self._accuracy_figure)
            self._accuracy_canvas.setMinimumHeight(200)
            layout.addWidget(self._accuracy_canvas, 1)
        else:
            placeholder = QtWidgets.QLabel(
                "Accuracy chart requires matplotlib"
            )
            placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
            placeholder.setMinimumHeight(200)
            layout.addWidget(placeholder, 1)

        widget.setLayout(layout)
        return widget

    def _build_export_section(self) -> QtWidgets.QWidget:
        """Build export buttons section."""
        widget = QtWidgets.QWidget()

        export_csv_btn = QtWidgets.QPushButton("Export CSV")
        export_csv_btn.clicked.connect(self._on_export_csv)

        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.clicked.connect(self._on_clear_all)

        layout = QtWidgets.QHBoxLayout()
        layout.addStretch()
        layout.addWidget(clear_btn)
        layout.addWidget(export_csv_btn)

        widget.setLayout(layout)
        return widget

    def _apply_style(self) -> None:
        """Apply glass-themed styling."""
        try:
            from ui.themes import get_style_manager

            theme = get_style_manager().theme

            self.setStyleSheet(f"""
                ComparisonDashboard {{
                    background-color: {theme.background_dark};
                }}
                #comparison_header {{
                    font-size: 18px;
                    font-weight: bold;
                    color: {theme.text_primary};
                }}
                #comparison_add_section {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                    padding: 8px;
                }}
                #comparison_add_btn {{
                    background-color: {theme.accent_success_dim};
                    border: 1px solid {theme.accent_success};
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: {theme.accent_success};
                    font-weight: bold;
                }}
                #comparison_add_btn:hover {{
                    background-color: {theme.accent_success};
                    color: white;
                }}
                #comparison_cards_scroll {{
                    background-color: transparent;
                    border: none;
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
                QPushButton {{
                    background-color: transparent;
                    border: 1px solid {theme.border_glass};
                    border-radius: 4px;
                    padding: 6px 12px;
                    color: {theme.text_secondary};
                }}
                QPushButton:hover {{
                    background-color: {theme.surface_glass_hover};
                }}
                QComboBox {{
                    background-color: {theme.input_background};
                    border: 1px solid {theme.border_glass};
                    border-radius: 4px;
                    padding: 6px;
                    color: {theme.text_primary};
                }}
            """)

        except ImportError:
            pass

    def set_available_pitchers(self, pitchers: List[Tuple[str, str]]) -> None:
        """Set list of available pitchers to add.

        Args:
            pitchers: List of (pitcher_id, display_name) tuples
        """
        self._pitcher_combo.clear()
        self._pitcher_combo.addItem("", "")  # Empty placeholder

        for pitcher_id, name in pitchers:
            self._pitcher_combo.addItem(name, pitcher_id)

    def add_pitcher(self, stats: PitcherStats) -> None:
        """Add a pitcher to the comparison.

        Args:
            stats: Pitcher statistics
        """
        if stats.pitcher_id in self._pitcher_stats:
            return  # Already added

        self._pitcher_stats[stats.pitcher_id] = stats

        # Create card
        card = PitcherComparisonCard(stats)
        card.remove_requested.connect(self._on_remove_pitcher)
        self._pitcher_cards[stats.pitcher_id] = card
        self._cards_layout.addWidget(card)

        # Update charts
        self._update_charts()

        logger.info(f"Added pitcher to comparison: {stats.display_name}")

    def remove_pitcher(self, pitcher_id: str) -> None:
        """Remove a pitcher from comparison.

        Args:
            pitcher_id: Pitcher identifier
        """
        if pitcher_id not in self._pitcher_stats:
            return

        del self._pitcher_stats[pitcher_id]

        # Remove card
        card = self._pitcher_cards.pop(pitcher_id, None)
        if card:
            card.deleteLater()

        # Update charts
        self._update_charts()

        logger.info(f"Removed pitcher from comparison: {pitcher_id}")

    def _on_add_pitcher(self) -> None:
        """Handle add pitcher button click."""
        pitcher_id = self._pitcher_combo.currentData()
        if not pitcher_id:
            return

        # Load pitcher stats from trend analyzer
        stats = self._load_pitcher_stats(pitcher_id)
        if stats:
            self.add_pitcher(stats)

    def _load_pitcher_stats(self, pitcher_id: str) -> Optional[PitcherStats]:
        """Load aggregated stats for a pitcher.

        Args:
            pitcher_id: Pitcher identifier

        Returns:
            PitcherStats if data available, None otherwise
        """
        # Get display name from combo
        name = pitcher_id
        for i in range(self._pitcher_combo.count()):
            if self._pitcher_combo.itemData(i) == pitcher_id:
                name = self._pitcher_combo.itemText(i)
                break

        # Load session summaries
        summaries = self._trend_analyzer._load_summaries_for_pitcher(
            pitcher_id, days=365
        )

        if not summaries:
            # Create placeholder stats
            return PitcherStats(
                pitcher_id=pitcher_id,
                display_name=name,
                sessions_count=0,
                total_pitches=0,
                avg_velocity=0.0,
                max_velocity=0.0,
                velocity_std=0.0,
                avg_strike_pct=0.0,
                avg_consistency=0.0,
                velocity_by_type={},
            )

        # Aggregate stats across sessions
        velocities = [s.avg_velocity_mph for s in summaries]
        max_velocities = [s.max_velocity_mph for s in summaries]
        strike_pcts = [s.strike_percentage for s in summaries]
        consistencies = [s.consistency_score for s in summaries]
        total_pitches = sum(s.total_pitches for s in summaries)

        return PitcherStats(
            pitcher_id=pitcher_id,
            display_name=name,
            sessions_count=len(summaries),
            total_pitches=total_pitches,
            avg_velocity=float(np.mean(velocities)) if velocities else 0.0,
            max_velocity=max(max_velocities) if max_velocities else 0.0,
            velocity_std=float(np.std(velocities)) if len(velocities) > 1 else 0.0,
            avg_strike_pct=float(np.mean(strike_pcts)) if strike_pcts else 0.0,
            avg_consistency=float(np.mean(consistencies)) if consistencies else 0.0,
            velocity_by_type={},
        )

    def _on_remove_pitcher(self, pitcher_id: str) -> None:
        """Handle remove pitcher request."""
        self.remove_pitcher(pitcher_id)

    def _on_clear_all(self) -> None:
        """Clear all pitchers from comparison."""
        pitcher_ids = list(self._pitcher_stats.keys())
        for pitcher_id in pitcher_ids:
            self.remove_pitcher(pitcher_id)

    def _update_charts(self) -> None:
        """Update comparison charts."""
        self._update_velocity_chart()
        self._update_accuracy_chart()

    def _update_velocity_chart(self) -> None:
        """Update velocity comparison bar chart."""
        if not HAS_MATPLOTLIB:
            return

        self._velocity_figure.clear()
        ax = self._velocity_figure.add_subplot(111)

        # Style
        ax.set_facecolor(self._theme.background_dark)
        ax.tick_params(colors=self._theme.text_muted)
        ax.spines["bottom"].set_color(self._theme.border_glass)
        ax.spines["left"].set_color(self._theme.border_glass)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        if not self._pitcher_stats:
            ax.text(
                0.5,
                0.5,
                "Add pitchers to compare",
                ha="center",
                va="center",
                color=self._theme.text_muted,
                transform=ax.transAxes,
            )
            self._velocity_canvas.draw()
            return

        # Data
        names = [s.display_name for s in self._pitcher_stats.values()]
        avg_velocities = [s.avg_velocity for s in self._pitcher_stats.values()]
        max_velocities = [s.max_velocity for s in self._pitcher_stats.values()]

        x = np.arange(len(names))
        width = 0.35

        # Bars
        ax.bar(
            x - width / 2,
            avg_velocities,
            width,
            label="Avg",
            color=self._theme.accent_primary,
            alpha=0.8,
        )
        ax.bar(
            x + width / 2,
            max_velocities,
            width,
            label="Max",
            color=self._theme.accent_success,
            alpha=0.8,
        )

        ax.set_ylabel("Velocity (mph)", color=self._theme.text_muted, fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
        ax.legend(loc="upper right", fontsize=8)

        self._velocity_figure.tight_layout()
        self._velocity_canvas.draw()

    def _update_accuracy_chart(self) -> None:
        """Update strike percentage comparison chart."""
        if not HAS_MATPLOTLIB:
            return

        self._accuracy_figure.clear()
        ax = self._accuracy_figure.add_subplot(111)

        # Style
        ax.set_facecolor(self._theme.background_dark)
        ax.tick_params(colors=self._theme.text_muted)
        ax.spines["bottom"].set_color(self._theme.border_glass)
        ax.spines["left"].set_color(self._theme.border_glass)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)

        if not self._pitcher_stats:
            ax.text(
                0.5,
                0.5,
                "Add pitchers to compare",
                ha="center",
                va="center",
                color=self._theme.text_muted,
                transform=ax.transAxes,
            )
            self._accuracy_canvas.draw()
            return

        # Data
        names = [s.display_name for s in self._pitcher_stats.values()]
        strike_pcts = [s.avg_strike_pct * 100 for s in self._pitcher_stats.values()]

        x = np.arange(len(names))

        # Color by performance
        colors = []
        for pct in strike_pcts:
            if pct >= 65:
                colors.append(self._theme.accent_success)  # Green - good
            elif pct >= 55:
                colors.append(self._theme.accent_warning)  # Orange - average
            else:
                colors.append(self._theme.accent_error)  # Red - below average

        ax.bar(x, strike_pcts, color=colors, alpha=0.8)

        ax.set_ylabel("Strike %", color=self._theme.text_muted, fontsize=9)
        ax.set_xticks(x)
        ax.set_xticklabels(names, rotation=45, ha="right", fontsize=8)
        ax.axhline(y=60, color=self._theme.border_glass, linestyle="--", linewidth=1)

        self._accuracy_figure.tight_layout()
        self._accuracy_canvas.draw()

    def _on_export_csv(self) -> None:
        """Export comparison data to CSV."""
        if not self._pitcher_stats:
            return

        # Get save path
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Comparison",
            f"pitcher_comparison_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)",
        )

        if not path:
            return

        self.export_comparison(Path(path))

    def export_comparison(self, path: Path) -> None:
        """Export comparison data to CSV file.

        Args:
            path: Output file path
        """
        try:
            with open(path, "w", newline="") as f:
                writer = csv.writer(f)

                # Header
                writer.writerow([
                    "Pitcher",
                    "Sessions",
                    "Total Pitches",
                    "Avg Velocity (mph)",
                    "Max Velocity (mph)",
                    "Velocity Std",
                    "Strike %",
                    "Consistency %",
                ])

                # Data rows
                for stats in self._pitcher_stats.values():
                    writer.writerow([
                        stats.display_name,
                        stats.sessions_count,
                        stats.total_pitches,
                        f"{stats.avg_velocity:.1f}",
                        f"{stats.max_velocity:.1f}",
                        f"{stats.velocity_std:.2f}",
                        f"{stats.avg_strike_pct * 100:.1f}",
                        f"{stats.avg_consistency * 100:.1f}",
                    ])

            logger.info(f"Exported comparison to {path}")

            # Show confirmation
            show_message_dialog(
                parent=self,
                title="Export Complete",
                message=f"Comparison exported to:\n{path}",
                level="info"
            )

        except Exception as e:
            logger.error(f"Failed to export comparison: {e}")
            show_message_dialog(
                parent=self,
                title="Export Failed",
                message=f"Failed to export comparison:\n{e}",
                level="warning"
            )


class ComparisonDashboardDialog(QtWidgets.QDialog):
    """Dialog wrapper for comparison dashboard."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Pitcher Comparison")
        self.setMinimumSize(900, 700)

        self._dashboard = ComparisonDashboard()

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(self.accept)

        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(self._dashboard, 1)
        layout.addWidget(close_btn)

        self.setLayout(layout)
        apply_standard_layout(layout)
        polish_form_controls([close_btn])

    @property
    def dashboard(self) -> ComparisonDashboard:
        """Get the dashboard widget."""
        return self._dashboard


__all__ = [
    "PitcherStats",
    "PitcherComparisonCard",
    "ComparisonDashboard",
    "ComparisonDashboardDialog",
]
