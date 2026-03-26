"""Fatigue monitoring panel for real-time pitcher fatigue display."""

from __future__ import annotations

from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtCore, QtWidgets

from analysis.fatigue_detector import FatigueDetector, FatigueMetrics
from ui.themes import get_style_manager, style_progress_bar, style_status_label

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


def _recommendation_tone(recommendation: str) -> str:
    """Map fatigue recommendations to shared semantic tones."""
    return {
        "Continue": "success",
        "Monitor": "warning",
        "Rest": "error",
    }.get(recommendation, "info")


def _score_variant(score: int) -> str:
    """Map numeric fatigue score to a progress-bar variant."""
    if score < 30:
        return "success"
    if score < 60:
        return "warning"
    return "danger"


class FatiguePanel(QtWidgets.QFrame):
    """Real-time fatigue monitoring panel for coaching sessions."""

    fatigue_alert = QtCore.Signal(str)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._detector = FatigueDetector()
        self._last_recommendation = "Continue"
        self._all_pitches: List["PitchSummary"] = []

        self._build_ui()

    def _build_ui(self) -> None:
        """Build the fatigue panel UI."""
        self._style_manager.style_panel(self, "normal")

        title_label = QtWidgets.QLabel("Fatigue Monitor")
        self._style_manager.style_label(title_label, "sectionTitle")

        score_layout = QtWidgets.QHBoxLayout()
        score_label = QtWidgets.QLabel("Score")
        self._style_manager.style_label(score_label, "muted")

        self._score_bar = QtWidgets.QProgressBar()
        self._score_bar.setMinimum(0)
        self._score_bar.setMaximum(100)
        self._score_bar.setValue(0)
        self._score_bar.setTextVisible(False)
        self._score_bar.setMinimumWidth(80)
        self._score_bar.setMaximumHeight(18)
        style_progress_bar(self._score_bar, "default")

        self._score_value = QtWidgets.QLabel("0")
        self._score_value.setMinimumWidth(30)
        self._style_manager.style_label(self._score_value, "metricAccent")

        score_layout.addWidget(score_label)
        score_layout.addWidget(self._score_bar, 1)
        score_layout.addWidget(self._score_value)

        metrics_layout = QtWidgets.QFormLayout()
        metrics_layout.setSpacing(4)

        self._velocity_label = QtWidgets.QLabel("--")
        self._movement_label = QtWidgets.QLabel("--")
        self._trend_label = QtWidgets.QLabel("--")
        for label in (self._velocity_label, self._movement_label, self._trend_label):
            self._style_manager.style_label(label, "muted")

        metrics_layout.addRow("Velocity:", self._velocity_label)
        metrics_layout.addRow("Movement:", self._movement_label)
        metrics_layout.addRow("Trend:", self._trend_label)

        status_layout = QtWidgets.QHBoxLayout()
        status_label = QtWidgets.QLabel("Status")
        self._style_manager.style_label(status_label, "muted")
        self._status_indicator = QtWidgets.QLabel("WAITING")
        self._status_indicator.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        style_status_label(self._status_indicator, "info", "WAITING")
        status_layout.addWidget(status_label)
        status_layout.addWidget(self._status_indicator, 1)

        self._factors_label = QtWidgets.QLabel("")
        self._factors_label.setWordWrap(True)
        self._style_manager.style_label(self._factors_label, "muted")
        self._factors_label.hide()

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)
        layout.addWidget(title_label)
        layout.addLayout(score_layout)
        layout.addLayout(metrics_layout)
        layout.addLayout(status_layout)
        layout.addWidget(self._factors_label)

        self.setMinimumWidth(180)
        self.setMaximumWidth(220)

    def update_pitches(self, pitches: List["PitchSummary"]) -> None:
        """Update fatigue metrics with new pitch data."""
        self._all_pitches = pitches

        if len(pitches) < 5:
            self._set_insufficient_data()
            return

        recent = pitches[-10:]
        metrics = self._detector.analyze(recent, pitches)
        self._update_display(metrics)

        if metrics.recommendation != self._last_recommendation:
            self._last_recommendation = metrics.recommendation
            self.fatigue_alert.emit(metrics.recommendation)

    def _set_insufficient_data(self) -> None:
        """Set display for insufficient data."""
        self._score_bar.setValue(0)
        style_progress_bar(self._score_bar, "default")
        self._score_value.setText("--")
        self._velocity_label.setText("--")
        self._movement_label.setText("--")
        self._trend_label.setText("--")
        style_status_label(self._status_indicator, "info", "WAITING")
        self._factors_label.hide()

    def _update_display(self, metrics: FatigueMetrics) -> None:
        """Update display with fatigue metrics."""
        score = int(metrics.fatigue_score)
        self._score_bar.setValue(score)
        style_progress_bar(self._score_bar, _score_variant(score))
        self._score_value.setText(str(score))

        self._velocity_label.setText(f"{metrics.velocity_drop_pct:+.1f}%")
        self._movement_label.setText(f"{metrics.movement_variance_pct:+.0f}%")
        self._trend_label.setText(f"{metrics.velocity_trend_mph_per_pitch:+.2f} mph/pitch")

        style_status_label(
            self._status_indicator,
            _recommendation_tone(metrics.recommendation),
            metrics.recommendation.upper(),
        )

        if (
            metrics.contributing_factors
            and metrics.contributing_factors[0] != "Insufficient data for analysis"
        ):
            self._factors_label.setText("\n".join(f"- {factor}" for factor in metrics.contributing_factors))
            self._factors_label.show()
        else:
            self._factors_label.hide()

    def clear(self) -> None:
        """Clear the fatigue panel for a new session."""
        self._all_pitches = []
        self._last_recommendation = "Continue"
        self._set_insufficient_data()


class CompactFatigueIndicator(QtWidgets.QWidget):
    """Compact fatigue indicator for header bars."""

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None) -> None:
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._detector = FatigueDetector()
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the compact indicator."""
        self._style_manager.style_panel(self, "subtle")

        self._score_label = QtWidgets.QLabel("--")
        self._style_manager.style_label(self._score_label, "metricAccent")

        self._status_chip = QtWidgets.QLabel("WAIT")
        style_status_label(self._status_chip, "info", "WAIT")

        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(6, 4, 6, 4)
        layout.setSpacing(6)
        layout.addWidget(self._score_label)
        layout.addWidget(self._status_chip)

    def update_pitches(self, pitches: List["PitchSummary"]) -> None:
        """Update indicator with pitch data."""
        if len(pitches) < 5:
            self._score_label.setText("--")
            style_status_label(self._status_chip, "info", "WAIT")
            return

        recent = pitches[-10:]
        metrics = self._detector.analyze(recent, pitches)
        self._score_label.setText(str(int(metrics.fatigue_score)))

        label = {
            "Continue": "OK",
            "Monitor": "MON",
            "Rest": "REST",
        }.get(metrics.recommendation, "WAIT")
        style_status_label(self._status_chip, _recommendation_tone(metrics.recommendation), label)

    def reset(self) -> None:
        """Reset indicator to initial state (for pitcher switch)."""
        self._detector = FatigueDetector()
        self._score_label.setText("--")
        self._status_dot.setObjectName("fatigue_status_dot_ok")
        self._apply_style()


__all__ = ["FatiguePanel", "CompactFatigueIndicator"]
