"""Broadcast view mode for coaching UI."""

from __future__ import annotations

import logging
from math import isfinite
from typing import TYPE_CHECKING, List, Optional

from PySide6 import QtCore, QtWidgets

from app.contracts import measurement_is_usable
from ui.coaching.strike_zone_mapping import (
    StrikeZoneOverlayConfig,
    calculate_overlay_layout,
)
from ui.coaching.widgets.camera_view_widget import CameraViewWidget
from ui.coaching.widgets.mode_widgets.base_mode_widget import BaseModeWidget
from ui.coaching.widgets.stats_panel_widget import StatsPanelWidget
from ui.themes import get_style_manager
from ui.coaching.widgets.preview_splitter import PreviewSplitter

if TYPE_CHECKING:
    from contracts import Frame
    from app.contracts import PitchSummary

logger = logging.getLogger(__name__)


class BroadcastViewWidget(BaseModeWidget):
    """Latest-pitch feedback with a resizable secondary camera preview."""

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
        # Preview can shrink without pushing the feedback off screen.
        self._camera_widget = CameraViewWidget(min_width=160, min_height=120)

        # Stats panel on right (20-30% of space)
        self._stats_panel = StatsPanelWidget()
        self._stats_panel.setMinimumSize(285, 380)
        feedback = QtWidgets.QScrollArea(self)
        feedback.setAccessibleName("Latest pitch feedback and recent pitches")
        feedback.setWidgetResizable(True)
        feedback.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        feedback.setMinimumWidth(304)
        feedback.setMinimumHeight(0)
        feedback.setSizePolicy(QtWidgets.QSizePolicy.Policy.Preferred, QtWidgets.QSizePolicy.Policy.Ignored)
        feedback.setWidget(self._stats_panel)

        # Layout: [Camera (3 parts)] [Stats (1 part)]
        layout = QtWidgets.QHBoxLayout()
        self._splitter = PreviewSplitter(QtCore.Qt.Orientation.Horizontal, self)
        self._splitter.setAccessibleName("Resize pitch feedback and camera preview")
        self._splitter.setChildrenCollapsible(False)
        self._splitter.addWidget(feedback)
        self._splitter.addWidget(self._camera_widget)
        self._splitter.setStretchFactor(0, 2)
        self._splitter.setStretchFactor(1, 3)
        self._splitter.setSizes([360, 600])
        layout.addWidget(self._splitter)
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
            self.clear()
            return

        # Update stats panel with latest pitch
        latest_pitch = recent_pitches[-1]
        self._stats_panel.update_latest_pitch(latest_pitch)
        self._stats_panel.update_recent_list(recent_pitches)

        if (
            measurement_is_usable(latest_pitch)
            and getattr(latest_pitch, "strike_call_available", True)
            and latest_pitch.trajectory_plate_x_ft is not None
            and latest_pitch.trajectory_plate_y_ft is not None
            and isfinite(latest_pitch.trajectory_plate_x_ft) and isfinite(latest_pitch.trajectory_plate_y_ft)
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
        return "Latest Pitch"

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
