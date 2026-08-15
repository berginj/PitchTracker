"""Trajectory overlay and diagnostics controller for ReviewWindow."""

from __future__ import annotations

import logging
from typing import List, Optional

from app.review import ReviewService
from visualization.trajectory_renderer import (
    RenderStyle,
    TrajectoryRenderConfig,
    TrajectoryRenderer,
)

logger = logging.getLogger(__name__)


class TrajectoryController:
    """Manages trajectory rendering state and diagnostics panel updates."""

    def __init__(self, service: ReviewService) -> None:
        self._service = service
        self._overlay_enabled = False
        self._renderer_left: Optional[TrajectoryRenderer] = None
        self._renderer_right: Optional[TrajectoryRenderer] = None
        self._current_observations: List = []

    @property
    def overlay_enabled(self) -> bool:
        return self._overlay_enabled

    @overlay_enabled.setter
    def overlay_enabled(self, value: bool) -> None:
        self._overlay_enabled = value

    @property
    def current_observations(self) -> List:
        return self._current_observations

    def init_renderers(self) -> None:
        """Initialize trajectory renderers for current session."""
        if not self._service.session:
            self._renderer_left = None
            self._renderer_right = None
            return

        try:
            from stereo.simple_stereo import StereoGeometry

            geometry = StereoGeometry(
                focal_length_px=1000.0,
                baseline_ft=0.5,
                cx=640.0,
                cy=360.0,
            )

            if self._service.session.calibration:
                cal = self._service.session.calibration
                geometry = StereoGeometry(
                    focal_length_px=cal.get("focal_length_px", 1000.0),
                    baseline_ft=cal.get("baseline_ft", 0.5),
                    cx=cal.get("cx", 640.0),
                    cy=cal.get("cy", 360.0),
                )

            config = TrajectoryRenderConfig(
                style=RenderStyle.GRADIENT,
                line_thickness=2,
                show_release_point=True,
                show_plate_crossing=True,
            )

            self._renderer_left = TrajectoryRenderer(geometry, camera="left", config=config)
            self._renderer_right = TrajectoryRenderer(geometry, camera="right", config=config)
            logger.info("Trajectory renderers initialized")

        except Exception as e:
            logger.warning(f"Could not initialize trajectory renderers: {e}")
            self._renderer_left = None
            self._renderer_right = None

    def load_trajectory_for_pitch(self, pitch_index: int) -> None:
        """Load trajectory observations for a pitch."""
        if not self._service.session:
            self._current_observations = []
            return

        pitches = self._service.session.pitches
        if pitch_index < 0 or pitch_index >= len(pitches):
            self._current_observations = []
            return

        pitch = pitches[pitch_index]
        if pitch.original_observations:
            self._current_observations = pitch.original_observations
            logger.debug(f"Loaded {len(self._current_observations)} trajectory observations")
        else:
            self._current_observations = []

    def apply_overlay(self, frame, camera: str):
        """Apply trajectory overlay to a frame. Returns frame (possibly modified)."""
        renderer = self._renderer_left if camera == "left" else self._renderer_right

        if renderer is None or not self._current_observations:
            return frame

        try:
            return renderer.render_on_frame(frame, self._current_observations)
        except Exception as e:
            logger.debug(f"Trajectory overlay failed: {e}")
            return frame

    def clear(self) -> None:
        """Reset all trajectory state."""
        self._renderer_left = None
        self._renderer_right = None
        self._current_observations = []
        self._overlay_enabled = False
