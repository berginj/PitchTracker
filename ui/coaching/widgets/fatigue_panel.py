"""Fatigue monitoring panel for real-time pitcher fatigue display."""

from __future__ import annotations

from typing import List, Optional

from PySide6 import QtCore, QtGui, QtWidgets

from analysis.fatigue_detector import FatigueDetector, FatigueMetrics

# Import type-only to avoid circular imports
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


class FatiguePanel(QtWidgets.QFrame):
    """Real-time fatigue monitoring panel for coaching sessions.

    Displays:
    - Composite fatigue score (0-100) with progress bar
    - Individual fatigue indicators (velocity, movement, trajectory)
    - Recommendation status (Continue/Monitor/Rest)
    - Contributing factors for fatigue

    Updates automatically when new pitch data is provided.
    """

    # Signals
    fatigue_alert = QtCore.Signal(str)  # Emitted when recommendation changes

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._detector = FatigueDetector()
        self._last_recommendation = "Continue"
        self._all_pitches: List["PitchSummary"] = []

        self._build_ui()
        self._apply_style()

    def _build_ui(self) -> None:
        """Build the fatigue panel UI."""
        # Title
        title_label = QtWidgets.QLabel("FATIGUE MONITOR")
        title_label.setObjectName("fatigue_title")

        # Main fatigue score with progress bar
        score_layout = QtWidgets.QHBoxLayout()
        score_label = QtWidgets.QLabel("Score:")
        score_label.setObjectName("fatigue_metric_label")

        self._score_bar = QtWidgets.QProgressBar()
        self._score_bar.setMinimum(0)
        self._score_bar.setMaximum(100)
        self._score_bar.setValue(0)
        self._score_bar.setTextVisible(False)
        self._score_bar.setMinimumWidth(80)
        self._score_bar.setMaximumHeight(18)

        self._score_value = QtWidgets.QLabel("0")
        self._score_value.setObjectName("fatigue_score_value")
        self._score_value.setMinimumWidth(30)

        score_layout.addWidget(score_label)
        score_layout.addWidget(self._score_bar)
        score_layout.addWidget(self._score_value)

        # Individual metrics
        metrics_layout = QtWidgets.QFormLayout()
        metrics_layout.setSpacing(4)

        self._velocity_label = QtWidgets.QLabel("--")
        self._velocity_label.setObjectName("fatigue_metric_value")
        metrics_layout.addRow("Velocity:", self._velocity_label)

        self._movement_label = QtWidgets.QLabel("--")
        self._movement_label.setObjectName("fatigue_metric_value")
        metrics_layout.addRow("Movement:", self._movement_label)

        self._trend_label = QtWidgets.QLabel("--")
        self._trend_label.setObjectName("fatigue_metric_value")
        metrics_layout.addRow("Trend:", self._trend_label)

        # Status indicator
        status_layout = QtWidgets.QHBoxLayout()
        status_label = QtWidgets.QLabel("Status:")
        status_label.setObjectName("fatigue_metric_label")

        self._status_indicator = QtWidgets.QLabel("CONTINUE")
        self._status_indicator.setObjectName("fatigue_status_continue")
        self._status_indicator.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)

        status_layout.addWidget(status_label)
        status_layout.addWidget(self._status_indicator, 1)

        # Contributing factors (collapsible)
        self._factors_label = QtWidgets.QLabel("")
        self._factors_label.setObjectName("fatigue_factors")
        self._factors_label.setWordWrap(True)
        self._factors_label.hide()

        # Main layout
        layout = QtWidgets.QVBoxLayout()
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        layout.addWidget(title_label)
        layout.addLayout(score_layout)
        layout.addLayout(metrics_layout)
        layout.addLayout(status_layout)
        layout.addWidget(self._factors_label)

        self.setLayout(layout)
        self.setMinimumWidth(180)
        self.setMaximumWidth(220)

    def _apply_style(self) -> None:
        """Apply glass-themed styling."""
        try:
            from ui.themes import get_style_manager
            sm = get_style_manager()
            theme = sm.theme

            self.setStyleSheet(f"""
                FatiguePanel {{
                    background-color: {theme.surface_glass};
                    border: 1px solid {theme.border_glass};
                    border-radius: {theme.border_radius_small}px;
                }}

                #fatigue_title {{
                    font-size: 11px;
                    font-weight: bold;
                    color: {theme.accent_primary};
                    padding-bottom: 4px;
                }}

                #fatigue_metric_label {{
                    font-size: 10px;
                    color: {theme.text_secondary};
                }}

                #fatigue_metric_value {{
                    font-size: 10px;
                    color: {theme.text_primary};
                }}

                #fatigue_score_value {{
                    font-size: 14px;
                    font-weight: bold;
                    color: {theme.text_primary};
                }}

                #fatigue_status_continue {{
                    background-color: {theme.accent_success_dim};
                    border: 1px solid {theme.accent_success};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                    color: {theme.accent_success};
                }}

                #fatigue_status_monitor {{
                    background-color: {theme.accent_warning_dim};
                    border: 1px solid {theme.accent_warning};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                    color: {theme.accent_warning};
                }}

                #fatigue_status_rest {{
                    background-color: {theme.accent_error_dim};
                    border: 1px solid {theme.accent_error};
                    border-radius: 4px;
                    padding: 4px 8px;
                    font-size: 11px;
                    font-weight: bold;
                    color: {theme.accent_error};
                }}

                #fatigue_factors {{
                    font-size: 9px;
                    color: {theme.text_muted};
                    padding-top: 4px;
                }}

                QProgressBar {{
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 4px;
                }}

                QProgressBar::chunk {{
                    background-color: {theme.accent_success};
                    border-radius: 3px;
                }}
            """)
        except ImportError:
            # Fallback styling without theme system
            self.setStyleSheet("""
                FatiguePanel {
                    background-color: rgba(30, 40, 55, 0.9);
                    border: 1px solid rgba(255, 255, 255, 0.1);
                    border-radius: 8px;
                }
                #fatigue_title {
                    font-weight: bold;
                    color: #64C8FF;
                }
            """)

    def update_pitches(self, pitches: List["PitchSummary"]) -> None:
        """Update fatigue metrics with new pitch data.

        Args:
            pitches: All pitches in current session
        """
        self._all_pitches = pitches

        if len(pitches) < 5:
            # Not enough data for meaningful analysis
            self._set_insufficient_data()
            return

        # Get recent pitches (last 10 or all if fewer)
        recent = pitches[-10:]

        # Analyze fatigue
        metrics = self._detector.analyze(recent, pitches)

        # Update UI
        self._update_display(metrics)

        # Check for recommendation change
        if metrics.recommendation != self._last_recommendation:
            self._last_recommendation = metrics.recommendation
            self.fatigue_alert.emit(metrics.recommendation)

    def _set_insufficient_data(self) -> None:
        """Set display for insufficient data."""
        self._score_bar.setValue(0)
        self._score_value.setText("--")
        self._velocity_label.setText("--")
        self._movement_label.setText("--")
        self._trend_label.setText("--")
        self._status_indicator.setText("WAITING")
        self._status_indicator.setObjectName("fatigue_status_continue")
        self._factors_label.hide()
        self._apply_style()  # Refresh styling

    def _update_display(self, metrics: FatigueMetrics) -> None:
        """Update display with fatigue metrics.

        Args:
            metrics: Computed fatigue metrics
        """
        # Update score
        score = int(metrics.fatigue_score)
        self._score_bar.setValue(score)
        self._score_value.setText(str(score))

        # Color score bar based on level
        self._update_score_bar_color(score)

        # Update individual metrics
        self._velocity_label.setText(f"{metrics.velocity_drop_pct:+.1f}%")
        self._movement_label.setText(f"{metrics.movement_variance_pct:+.0f}%")

        trend = metrics.velocity_trend_mph_per_pitch
        trend_str = f"{trend:+.2f} mph/pitch"
        self._trend_label.setText(trend_str)

        # Update status indicator
        self._update_status(metrics.recommendation)

        # Update factors
        if metrics.contributing_factors and metrics.contributing_factors[0] != "Insufficient data for analysis":
            self._factors_label.setText("\n".join(f"- {f}" for f in metrics.contributing_factors))
            self._factors_label.show()
        else:
            self._factors_label.hide()

    def _update_score_bar_color(self, score: int) -> None:
        """Update progress bar color based on fatigue score.

        Args:
            score: Fatigue score (0-100)
        """
        try:
            from ui.themes import get_style_manager
            theme = get_style_manager().theme

            if score < 30:
                color = theme.accent_success
            elif score < 60:
                color = theme.accent_warning
            else:
                color = theme.accent_error

            self._score_bar.setStyleSheet(f"""
                QProgressBar {{
                    background-color: rgba(255, 255, 255, 0.1);
                    border: 1px solid rgba(255, 255, 255, 0.2);
                    border-radius: 4px;
                }}
                QProgressBar::chunk {{
                    background-color: {color};
                    border-radius: 3px;
                }}
            """)
        except ImportError:
            pass

    def _update_status(self, recommendation: str) -> None:
        """Update status indicator with recommendation.

        Args:
            recommendation: "Continue", "Monitor", or "Rest"
        """
        self._status_indicator.setText(recommendation.upper())

        if recommendation == "Continue":
            self._status_indicator.setObjectName("fatigue_status_continue")
        elif recommendation == "Monitor":
            self._status_indicator.setObjectName("fatigue_status_monitor")
        else:  # Rest
            self._status_indicator.setObjectName("fatigue_status_rest")

        # Re-apply style to update based on object name
        self._apply_style()

    def clear(self) -> None:
        """Clear the fatigue panel for new session."""
        self._all_pitches = []
        self._last_recommendation = "Continue"
        self._set_insufficient_data()


class CompactFatigueIndicator(QtWidgets.QWidget):
    """Compact fatigue indicator for header bar.

    Shows just the score and status in a small widget.
    """

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._detector = FatigueDetector()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build compact indicator."""
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(4, 2, 4, 2)
        layout.setSpacing(4)

        # Icon
        icon_label = QtWidgets.QLabel("")
        icon_label.setObjectName("fatigue_icon")

        # Score
        self._score_label = QtWidgets.QLabel("--")
        self._score_label.setObjectName("fatigue_compact_score")

        # Status dot
        self._status_dot = QtWidgets.QLabel("●")
        self._status_dot.setObjectName("fatigue_status_dot_ok")

        layout.addWidget(icon_label)
        layout.addWidget(self._score_label)
        layout.addWidget(self._status_dot)

        self.setLayout(layout)
        self._apply_style()

    def _apply_style(self) -> None:
        """Apply styling."""
        try:
            from ui.themes import get_style_manager
            theme = get_style_manager().theme

            self.setStyleSheet(f"""
                #fatigue_icon {{
                    font-size: 12px;
                }}
                #fatigue_compact_score {{
                    font-size: 11px;
                    font-weight: bold;
                    color: {theme.text_primary};
                }}
                #fatigue_status_dot_ok {{
                    color: {theme.accent_success};
                    font-size: 14px;
                }}
                #fatigue_status_dot_warn {{
                    color: {theme.accent_warning};
                    font-size: 14px;
                }}
                #fatigue_status_dot_alert {{
                    color: {theme.accent_error};
                    font-size: 14px;
                }}
            """)
        except ImportError:
            pass

    def update_pitches(self, pitches: List["PitchSummary"]) -> None:
        """Update indicator with pitch data.

        Args:
            pitches: All pitches in current session
        """
        if len(pitches) < 5:
            self._score_label.setText("--")
            return

        recent = pitches[-10:]
        metrics = self._detector.analyze(recent, pitches)

        self._score_label.setText(str(int(metrics.fatigue_score)))

        if metrics.recommendation == "Continue":
            self._status_dot.setObjectName("fatigue_status_dot_ok")
        elif metrics.recommendation == "Monitor":
            self._status_dot.setObjectName("fatigue_status_dot_warn")
        else:
            self._status_dot.setObjectName("fatigue_status_dot_alert")

        self._apply_style()

    def reset(self) -> None:
        """Reset indicator to initial state (for pitcher switch)."""
        self._detector = FatigueDetector()
        self._score_label.setText("--")
        self._status_dot.setObjectName("fatigue_status_dot_ok")
        self._apply_style()


__all__ = [
    "FatiguePanel",
    "CompactFatigueIndicator",
]
