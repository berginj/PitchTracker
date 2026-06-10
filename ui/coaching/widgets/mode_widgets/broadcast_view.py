"""Broadcast view mode for coaching UI."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtWidgets

from ui.coaching.strike_zone_mapping import (
    StrikeZoneOverlayConfig,
    calculate_overlay_layout,
)
from ui.coaching.widgets.camera_view_widget import CameraViewWidget
from ui.coaching.widgets.mode_widgets.base_mode_widget import BaseModeWidget
from ui.coaching.widgets.stats_panel_widget import StatsPanelWidget
from ui.themes import get_style_manager

if TYPE_CHECKING:
    from contracts import Frame
    from app.pipeline_service import PitchSummary

logger = logging.getLogger(__name__)


class BroadcastViewWidget(BaseModeWidget):
    """Mode 1: Broadcast View.

    Large camera view (70-80%) with statistics panel on right (20-30%).
    TV-style broadcast presentation with focus on live camera feed.
    """

    def __init__(
        self,
        overlay_config: StrikeZoneOverlayConfig,
        parent: Optional[QtWidgets.QWidget] = None,
    ):
        """Initialize broadcast view mode.

        Args:
            overlay_config: Strike-zone overlay settings
            parent: Parent widget
        """
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self._overlay_config = overlay_config
        self._build_ui()

    def _build_ui(self) -> None:
        """Build the widget UI."""
        # Large camera view on left (70-80% of space)
        self._camera_widget = CameraViewWidget(min_width=800, min_height=600)

        # Stats panel on right (20-30% of space)
        self._stats_panel = StatsPanelWidget()
        self._stats_panel.setMaximumWidth(400)

        # Layout: [Camera (3 parts)] [Stats (1 part)]
        layout = QtWidgets.QHBoxLayout()
        layout.addWidget(self._camera_widget, 3)
        layout.addWidget(self._stats_panel, 1)
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
        logger.debug(f"Broadcast view: Camera changed to {camera}")

    def update_pitch_data(self, recent_pitches: List["PitchSummary"]) -> None:
        """Update visualization with new pitch data.

        Args:
            recent_pitches: List of recent pitch summaries
        """
        if not recent_pitches:
            return

        # Update stats panel with latest pitch
        latest_pitch = recent_pitches[-1]
        self._stats_panel.update_latest_pitch(latest_pitch)
        self._stats_panel.update_recent_list(recent_pitches)

        if latest_pitch.trajectory_plate_x_ft is not None and latest_pitch.trajectory_plate_y_ft is not None:
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

    def update_camera_frames(self, left_frame: Optional["Frame"], right_frame: Optional["Frame"]) -> None:
        """Update camera preview frames.

        Args:
            left_frame: Left camera frame
            right_frame: Right camera frame
        """
        self._camera_widget.update_frames(left_frame, right_frame)

    def clear(self) -> None:
        """Clear all visualizations."""
        self._stats_panel.clear()
        self._camera_widget.clear_pitch_location()
        logger.debug("Broadcast view: Cleared")

    def get_mode_name(self) -> str:
        """Return display name for this mode.

        Returns:
            Mode name
        """
        return "Broadcast View"

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


__all__ = ["BroadcastViewWidget"]
