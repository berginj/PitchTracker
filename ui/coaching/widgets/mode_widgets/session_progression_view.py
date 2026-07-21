"""Session progression view mode for coaching UI."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtWidgets

from app.contracts import measurement_is_usable
from ui.coaching.strike_zone_mapping import (
    StrikeZoneOverlayConfig,
    calculate_overlay_layout,
)
from ui.coaching.widgets.camera_view_widget import CameraViewWidget
from ui.coaching.widgets.mode_widgets.base_mode_widget import BaseModeWidget
from ui.coaching.widgets.progression_charts_widget import (
    AccuracyTrendChart,
    FastestPitchWidget,
    StrikeRatioGauge,
    VelocityTrendChart,
)
from ui.themes import get_style_manager

if TYPE_CHECKING:
    from contracts import Frame
    from app.pipeline_service import PitchSummary
    from ui.coaching.session_history_tracker import SessionHistoryTracker

logger = logging.getLogger(__name__)


class SessionProgressionWidget(BaseModeWidget):
    """Mode 2: Session Progression View.

    Smaller camera (30-40%) with progression charts (60-70%).
    Tracks pitcher improvement during session with velocity trends,
    strike accuracy, and performance metrics.
    """

    def __init__(
        self,
        session_tracker: "SessionHistoryTracker",
        overlay_config: StrikeZoneOverlayConfig,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize session progression view mode.

        Args:
            session_tracker: Session history tracker for metrics
            overlay_config: Strike-zone overlay settings
            parent: Parent widget
        """
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._session_tracker = session_tracker
        self._overlay_config = overlay_config
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        # Top row: Camera (smaller) + Fastest pitch display
        top_widget = QtWidgets.QWidget()
        top_layout = QtWidgets.QHBoxLayout()

        # Camera view (smaller than broadcast mode)
        self._camera_widget = CameraViewWidget(min_width=400, min_height=300)
        self._camera_widget.setMaximumWidth(500)
        top_layout.addWidget(self._camera_widget, 2)

        # Fastest pitch widget
        self._fastest_widget = FastestPitchWidget()
        self._fastest_widget.setMinimumWidth(250)
        top_layout.addWidget(self._fastest_widget, 1)

        top_widget.setLayout(top_layout)

        # Middle row: Velocity trend chart (full width)
        velocity_group = QtWidgets.QGroupBox("Velocity Trend")
        self._velocity_chart = VelocityTrendChart()
        velocity_layout = QtWidgets.QVBoxLayout()
        velocity_layout.addWidget(self._velocity_chart)
        velocity_group.setLayout(velocity_layout)

        # Bottom row: Strike ratio gauge + Accuracy chart
        bottom_widget = QtWidgets.QWidget()
        bottom_layout = QtWidgets.QHBoxLayout()

        # Strike ratio gauge
        strike_group = QtWidgets.QGroupBox("Strike Ratio")
        self._strike_gauge = StrikeRatioGauge()
        self._classification_label = QtWidgets.QLabel("Classified: 0 • Unclassified: 0")
        self._style_manager.style_label(self._classification_label, "muted")
        strike_layout = QtWidgets.QVBoxLayout()
        strike_layout.addWidget(self._strike_gauge)
        strike_layout.addWidget(self._classification_label)
        strike_group.setLayout(strike_layout)
        bottom_layout.addWidget(strike_group, 1)

        # Accuracy trend chart
        accuracy_group = QtWidgets.QGroupBox("Accuracy Trend (Rolling 10)")
        self._accuracy_chart = AccuracyTrendChart()
        accuracy_layout = QtWidgets.QVBoxLayout()
        accuracy_layout.addWidget(self._accuracy_chart)
        accuracy_group.setLayout(accuracy_layout)
        bottom_layout.addWidget(accuracy_group, 2)

        bottom_widget.setLayout(bottom_layout)

        # Main layout: Stack vertically
        layout = QtWidgets.QVBoxLayout()
        layout.addWidget(top_widget, 1)
        layout.addWidget(velocity_group, 1)
        layout.addWidget(bottom_widget, 1)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        self.setLayout(layout)

        # Connect camera selection changes
        self._camera_widget.camera_changed.connect(self._on_camera_changed)
        self._apply_strike_zone_layout()

    def _on_camera_changed(self, camera: str) -> None:
        """Handle camera selection change.

        Args:
            camera: New camera selection ("left" or "right")
        """
        self._current_camera = camera
        logger.debug(f"Session progression: Camera changed to {camera}")

    def update_pitch_data(
        self,
        recent_pitches: List["PitchSummary"],
        *,
        new_pitches: Optional[List["PitchSummary"]] = None,
    ) -> None:
        """Update visualization with new pitch data.

        Args:
            recent_pitches: List of recent pitch summaries
        """
        if not recent_pitches:
            return

        # CoachWindow owns exactly-once insertion into the shared tracker. This
        # view only renders that state; appending here duplicated the latest
        # pitch on every UI timer tick.
        latest_pitch = recent_pitches[-1]

        # Update fastest pitch display
        fastest = self._session_tracker.get_fastest_pitch()
        if fastest is None:
            self._fastest_widget.clear()
        else:
            self._fastest_widget.set_speed(fastest)

        # Update velocity trend chart
        velocity_history = self._session_tracker.get_velocity_history()
        self._velocity_chart.update_data(velocity_history)

        # Update strike ratio gauge
        strikes, balls, strike_pct = self._session_tracker.get_strike_ball_ratio()
        unclassified = self._session_tracker.get_unclassified_count()
        self._strike_gauge.set_percentage(strike_pct)
        self._classification_label.setText(
            f"Classified: {strikes + balls} • Unclassified: {unclassified}"
        )

        # Update accuracy trend chart
        accuracy_history = self._session_tracker.get_strike_accuracy_history()
        self._accuracy_chart.update_data(accuracy_history)

        if (
            measurement_is_usable(latest_pitch)
            and latest_pitch.trajectory_plate_x_ft is not None
            and latest_pitch.trajectory_plate_y_ft is not None
        ):
            layout = calculate_overlay_layout(
                self._overlay_config,
                plate_x_ft=latest_pitch.trajectory_plate_x_ft,
                plate_y_ft=latest_pitch.trajectory_plate_y_ft,
            )
            self._camera_widget.set_strike_zone(
                layout.zone_left,
                layout.zone_right,
                layout.zone_top,
                layout.zone_bottom,
            )
            self._camera_widget.update_pitch_location(layout.pitch_x, layout.pitch_y)
        else:
            self._camera_widget.clear_pitch_location()

        logger.debug(
            f"Session progression: Updated with {self._session_tracker.get_pitch_count()} pitches, "
            f"fastest={fastest if fastest is not None else 'unavailable'} mph, "
            f"strike%={strike_pct*100:.1f}%, unclassified={unclassified}"
        )

    def update_camera_frames(self, left_frame: Optional["Frame"], right_frame: Optional["Frame"]) -> None:
        """Update camera preview frames.

        Args:
            left_frame: Left camera frame
            right_frame: Right camera frame
        """
        self._camera_widget.update_frames(left_frame, right_frame)

    def clear(self) -> None:
        """Clear all visualizations."""
        self._session_tracker.clear()
        self._fastest_widget.clear()
        self._velocity_chart.clear()
        self._strike_gauge.clear()
        self._accuracy_chart.clear()
        self._camera_widget.clear_pitch_location()
        logger.debug("Session progression: Cleared")

    def get_mode_name(self) -> str:
        """Return display name for this mode.

        Returns:
            Mode name
        """
        return "Session Progression"

    def set_camera_selection(self, camera: str) -> None:
        """Set camera selection.

        Args:
            camera: Camera to select ("left" or "right")
        """
        super().set_camera_selection(camera)
        self._camera_widget.set_active_camera(camera)

    def set_strike_zone_config(self, overlay_config: StrikeZoneOverlayConfig) -> None:
        """Update strike-zone configuration for overlay placement."""
        self._overlay_config = overlay_config
        self._apply_strike_zone_layout()

    def _apply_strike_zone_layout(self) -> None:
        """Apply current strike-zone bounds to the overlay."""
        layout = calculate_overlay_layout(
            self._overlay_config,
            plate_x_ft=0.0,
            plate_y_ft=(
                self._overlay_config.batter_height_in
                * (self._overlay_config.top_ratio + self._overlay_config.bottom_ratio)
                / 24.0
            ),
        )
        self._camera_widget.set_strike_zone(
            layout.zone_left,
            layout.zone_right,
            layout.zone_top,
            layout.zone_bottom,
        )


__all__ = ["SessionProgressionWidget"]
