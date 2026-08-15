"""Multi-pitcher comparison dashboard."""

from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from PySide6 import QtCore, QtWidgets

try:
    from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg as FigureCanvas
    from matplotlib.figure import Figure

    HAS_MATPLOTLIB = True
except ImportError:
    HAS_MATPLOTLIB = False

from analysis.trend_analyzer import TrendAnalyzer
from log_config.logger import get_logger
from ui.themes import apply_standard_layout, polish_form_controls, show_message_dialog

from .comparison_data import PitcherStats, export_comparison_csv, load_pitcher_stats
from .comparison_presentation import ComparisonChartPresenter, PitcherComparisonCard

logger = get_logger(__name__)


class ComparisonDashboard(QtWidgets.QWidget):
    """Dashboard for comparing stats across multiple pitchers."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._pitcher_stats: Dict[str, PitcherStats] = {}
        self._pitcher_cards: Dict[str, PitcherComparisonCard] = {}
        self._trend_analyzer = TrendAnalyzer()
        self._chart_presenter: Optional[ComparisonChartPresenter] = None

        from ui.themes import get_style_manager

        self._style_manager = get_style_manager()
        self._theme = self._style_manager.theme
        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        header = QtWidgets.QLabel("PITCHER COMPARISON")
        header.setObjectName("comparison_header")
        header.setAccessibleName("Pitcher comparison dashboard")

        self._cards_container = QtWidgets.QWidget()
        self._cards_layout = QtWidgets.QHBoxLayout(self._cards_container)
        self._cards_layout.setAlignment(QtCore.Qt.AlignmentFlag.AlignLeft)
        self._cards_layout.setContentsMargins(0, 0, 0, 0)

        cards_scroll = QtWidgets.QScrollArea()
        cards_scroll.setWidget(self._cards_container)
        cards_scroll.setWidgetResizable(True)
        cards_scroll.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        cards_scroll.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        cards_scroll.setMaximumHeight(self._theme.button_height_lg * 5)
        cards_scroll.setObjectName("comparison_cards_scroll")
        cards_scroll.setAccessibleName("Selected pitcher comparison cards")

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(header)
        layout.addWidget(self._build_add_section())
        layout.addWidget(cards_scroll)
        layout.addWidget(self._build_charts_section(), 1)
        layout.addWidget(self._build_export_section())
        apply_standard_layout(layout)

    def _build_add_section(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        widget.setObjectName("comparison_add_section")

        self._pitcher_combo = QtWidgets.QComboBox()
        self._pitcher_combo.setMinimumWidth(self._theme.button_height_lg * 4)
        self._pitcher_combo.setPlaceholderText("Select pitcher...")
        self._pitcher_combo.setAccessibleName("Pitcher to compare")

        add_btn = QtWidgets.QPushButton("Add to Comparison")
        add_btn.setObjectName("comparison_add_btn")
        add_btn.setAccessibleName("Add selected pitcher to comparison")
        add_btn.clicked.connect(self._on_add_pitcher)
        self._style_manager.style_button(add_btn, "success")

        layout = QtWidgets.QHBoxLayout(widget)
        layout.addWidget(self._pitcher_combo)
        layout.addWidget(add_btn)
        layout.addStretch()
        return widget

    def _build_charts_section(self) -> QtWidgets.QWidget:
        if not HAS_MATPLOTLIB:
            widget = QtWidgets.QWidget()
            layout = QtWidgets.QHBoxLayout(widget)
            layout.addWidget(self._build_chart_placeholder("Velocity chart requires matplotlib"))
            layout.addWidget(self._build_chart_placeholder("Accuracy chart requires matplotlib"))
            return widget

        velocity_frame, self._velocity_figure, self._velocity_canvas = self._build_chart(
            "VELOCITY COMPARISON",
            "Velocity comparison chart",
        )
        accuracy_frame, self._accuracy_figure, self._accuracy_canvas = self._build_chart(
            "STRIKE % COMPARISON",
            "Strike percentage comparison chart",
        )
        self._chart_presenter = ComparisonChartPresenter(
            self._theme,
            self._velocity_figure,
            self._velocity_canvas,
            self._accuracy_figure,
            self._accuracy_canvas,
        )

        splitter = QtWidgets.QSplitter(QtCore.Qt.Orientation.Horizontal)
        splitter.setObjectName("comparison_chart_splitter")
        splitter.setChildrenCollapsible(False)
        splitter.addWidget(velocity_frame)
        splitter.addWidget(accuracy_frame)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 1)
        return splitter

    def _build_chart(self, title_text: str, accessible_name: str):
        frame = QtWidgets.QFrame()
        frame.setObjectName("chart_container")
        frame.setAccessibleName(accessible_name)
        title = QtWidgets.QLabel(title_text)
        title.setObjectName("chart_title")

        figure = Figure(figsize=(5, 3), dpi=100)
        figure.patch.set_facecolor(self._theme.chart_background)
        canvas = FigureCanvas(figure)
        canvas.setMinimumHeight(self._theme.button_height_lg * 4)

        layout = QtWidgets.QVBoxLayout(frame)
        layout.addWidget(title)
        layout.addWidget(canvas, 1)
        return frame, figure, canvas

    def _build_chart_placeholder(self, text: str) -> QtWidgets.QFrame:
        frame = QtWidgets.QFrame()
        frame.setObjectName("chart_container")
        placeholder = QtWidgets.QLabel(text)
        placeholder.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        placeholder.setMinimumHeight(self._theme.button_height_lg * 4)
        layout = QtWidgets.QVBoxLayout(frame)
        layout.addWidget(placeholder)
        return frame

    def _build_export_section(self) -> QtWidgets.QWidget:
        widget = QtWidgets.QWidget()
        export_csv_btn = QtWidgets.QPushButton("Export CSV")
        export_csv_btn.setAccessibleName("Export pitcher comparison as CSV")
        export_csv_btn.clicked.connect(self._on_export_csv)
        self._style_manager.style_button(export_csv_btn, "primary")

        clear_btn = QtWidgets.QPushButton("Clear All")
        clear_btn.setAccessibleName("Clear all compared pitchers")
        clear_btn.clicked.connect(self._on_clear_all)

        layout = QtWidgets.QHBoxLayout(widget)
        layout.addStretch()
        layout.addWidget(clear_btn)
        layout.addWidget(export_csv_btn)
        return widget

    def _apply_style(self) -> None:
        theme = self._theme
        self.setStyleSheet(
            f"""
            ComparisonDashboard {{ background-color: {theme.background_dark}; }}
            #comparison_header {{
                font-size: {theme.font_size_subtitle}px;
                font-weight: 700;
                color: {theme.text_primary};
            }}
            #comparison_add_section {{
                background-color: {theme.surface_glass};
                border: {theme.border_width}px solid {theme.border_glass};
                border-radius: {theme.border_radius_small}px;
                padding: {theme.margin_tight}px;
            }}
            #comparison_cards_scroll {{ background-color: transparent; border: none; }}
            #chart_container {{
                background-color: {theme.surface_glass};
                border: {theme.border_width}px solid {theme.border_glass};
                border-radius: {theme.border_radius_small}px;
            }}
            #chart_title {{
                font-size: {theme.font_size_caption}px;
                font-weight: 700;
                color: {theme.accent_primary};
                padding-bottom: {theme.margin_tight // 2}px;
            }}
            """
        )
        polish_form_controls(self)

    def set_available_pitchers(self, pitchers: List[Tuple[str, str]]) -> None:
        """Set the available pitcher identifiers and display names."""
        self._pitcher_combo.clear()
        self._pitcher_combo.addItem("", "")
        for pitcher_id, name in pitchers:
            self._pitcher_combo.addItem(name, pitcher_id)

    def add_pitcher(self, stats: PitcherStats) -> None:
        """Add a pitcher to the comparison."""
        if stats.pitcher_id in self._pitcher_stats:
            return
        self._pitcher_stats[stats.pitcher_id] = stats
        card = PitcherComparisonCard(stats, self._cards_container)
        card.remove_requested.connect(self._on_remove_pitcher)
        self._pitcher_cards[stats.pitcher_id] = card
        self._cards_layout.addWidget(card)
        self._update_charts()
        logger.info("Added pitcher to comparison: {}", stats.display_name)

    def remove_pitcher(self, pitcher_id: str) -> None:
        """Remove a pitcher from the comparison."""
        if pitcher_id not in self._pitcher_stats:
            return
        del self._pitcher_stats[pitcher_id]
        card = self._pitcher_cards.pop(pitcher_id, None)
        if card is not None:
            self._cards_layout.removeWidget(card)
            card.deleteLater()
        self._update_charts()
        logger.info("Removed pitcher from comparison: {}", pitcher_id)

    def _on_add_pitcher(self) -> None:
        pitcher_id = self._pitcher_combo.currentData()
        if not pitcher_id:
            return
        self.add_pitcher(self._load_pitcher_stats(pitcher_id))

    def _load_pitcher_stats(self, pitcher_id: str) -> PitcherStats:
        name = next(
            (
                self._pitcher_combo.itemText(index)
                for index in range(self._pitcher_combo.count())
                if self._pitcher_combo.itemData(index) == pitcher_id
            ),
            pitcher_id,
        )
        return load_pitcher_stats(self._trend_analyzer, pitcher_id, name)

    def _on_remove_pitcher(self, pitcher_id: str) -> None:
        self.remove_pitcher(pitcher_id)

    def _on_clear_all(self) -> None:
        for pitcher_id in list(self._pitcher_stats):
            self.remove_pitcher(pitcher_id)

    def _update_charts(self) -> None:
        if self._chart_presenter is not None:
            self._chart_presenter.update(self._pitcher_stats)

    def _on_export_csv(self) -> None:
        if not self._pitcher_stats:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(
            self,
            "Export Comparison",
            f"pitcher_comparison_{datetime.now().strftime('%Y%m%d')}.csv",
            "CSV Files (*.csv)",
        )
        if path:
            self.export_comparison(Path(path))

    def export_comparison(self, path: Path) -> None:
        """Export comparison data to a CSV file."""
        try:
            export_comparison_csv(path, self._pitcher_stats.values())
        except (OSError, csv.Error) as exc:
            logger.error("Failed to export comparison: {}", exc)
            show_message_dialog(
                parent=self,
                title="Export Failed",
                message=f"Failed to export comparison:\n{exc}",
                level="warning",
            )
            return
        logger.info("Exported comparison to {}", path)
        show_message_dialog(
            parent=self,
            title="Export Complete",
            message=f"Comparison exported to:\n{path}",
            level="info",
        )


class ComparisonDashboardDialog(QtWidgets.QDialog):
    """Dialog wrapper for comparison dashboard."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        from ui.themes import get_style_manager

        theme = get_style_manager().theme
        self.setWindowTitle("Pitcher Comparison")
        self.setMinimumSize(theme.dialog_width_large, theme.dialog_height_large)
        self._dashboard = ComparisonDashboard()

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.setAccessibleName("Close pitcher comparison")
        close_btn.clicked.connect(self.accept)

        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(self._dashboard, 1)
        layout.addWidget(close_btn)
        apply_standard_layout(layout)
        polish_form_controls(self)

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
