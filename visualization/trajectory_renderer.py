"""Trajectory visualization renderer for video overlays.

Projects 3D ball trajectories onto 2D video frames for:
- Review mode playback with trajectory trails
- Side-by-side pitch comparison
- Live tracking visualization
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import List, Optional, Tuple

import cv2
import numpy as np

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from contracts import StereoObservation
    from stereo.simple_stereo import StereoGeometry


class RenderStyle(Enum):
    """Trajectory rendering styles."""

    SOLID = "solid"  # Solid line
    GRADIENT = "gradient"  # Color gradient from start to end
    DOTTED = "dotted"  # Dotted line
    TRAIL = "trail"  # Fading trail effect


@dataclass(frozen=True)
class ProjectedPoint:
    """A 3D point projected to 2D image coordinates."""

    u: float  # X coordinate in pixels
    v: float  # Y coordinate in pixels
    z_ft: float  # Original depth for size scaling
    timestamp_ns: int  # Original timestamp


@dataclass(frozen=True)
class TrajectoryRenderConfig:
    """Configuration for trajectory rendering."""

    style: RenderStyle = RenderStyle.GRADIENT
    line_thickness: int = 2
    show_release_point: bool = True
    show_plate_crossing: bool = True
    show_timestamps: bool = False
    color_start: Tuple[int, int, int] = (100, 200, 255)  # Cyan (BGR)
    color_end: Tuple[int, int, int] = (100, 100, 255)  # Red (BGR)
    marker_radius: int = 6
    trail_fade_length: int = 10  # Number of points to fade


class TrajectoryRenderer:
    """Renders 3D trajectories onto 2D video frames.

    Uses camera calibration data to project 3D stereo observations
    to 2D image coordinates for visualization.

    Usage:
        renderer = TrajectoryRenderer(geometry, camera="left")
        frame_with_overlay = renderer.render_on_frame(frame, observations)
    """

    def __init__(
        self,
        geometry: "StereoGeometry",
        camera: str = "left",
        config: Optional[TrajectoryRenderConfig] = None,
    ) -> None:
        """Initialize trajectory renderer.

        Args:
            geometry: Stereo camera geometry for projection
            camera: Which camera to render for ("left" or "right")
            config: Rendering configuration
        """
        self._geometry = geometry
        self._camera = camera
        self._config = config or TrajectoryRenderConfig()

    def project_point(
        self,
        x_ft: float,
        y_ft: float,
        z_ft: float,
        timestamp_ns: int = 0,
    ) -> Optional[ProjectedPoint]:
        """Project a 3D point to 2D image coordinates.

        Args:
            x_ft: X coordinate in feet (horizontal, left positive)
            y_ft: Y coordinate in feet (vertical, up positive)
            z_ft: Z coordinate in feet (depth, away from cameras)
            timestamp_ns: Original timestamp

        Returns:
            ProjectedPoint if projection is valid, None if out of frame
        """
        if z_ft <= 0:
            return None

        # Project to image coordinates
        # u = focal * X / Z + cx
        # v = focal * Y / Z + cy (Y is inverted in image space)
        u = self._geometry.focal_length_px * x_ft / z_ft + self._geometry.cx
        v = self._geometry.cy - self._geometry.focal_length_px * y_ft / z_ft

        return ProjectedPoint(u=u, v=v, z_ft=z_ft, timestamp_ns=timestamp_ns)

    def project_trajectory(
        self,
        observations: List["StereoObservation"],
    ) -> List[ProjectedPoint]:
        """Project a full trajectory to 2D points.

        Args:
            observations: List of 3D stereo observations

        Returns:
            List of projected 2D points
        """
        projected = []
        for obs in observations:
            point = self.project_point(obs.X, obs.Y, obs.Z, obs.t_ns)
            if point is not None:
                projected.append(point)
        return projected

    def render_on_frame(
        self,
        frame: np.ndarray,
        observations: List["StereoObservation"],
        config: Optional[TrajectoryRenderConfig] = None,
    ) -> np.ndarray:
        """Render trajectory overlay on a video frame.

        Args:
            frame: Input video frame (BGR)
            observations: 3D trajectory observations
            config: Optional override config

        Returns:
            Frame with trajectory overlay (same dimensions)
        """
        cfg = config or self._config

        # Project trajectory to 2D
        projected = self.project_trajectory(observations)
        if not projected:
            return frame

        # Create overlay (draw on copy)
        overlay = frame.copy()

        # Draw trajectory based on style
        if cfg.style == RenderStyle.SOLID:
            self._draw_solid(overlay, projected, cfg)
        elif cfg.style == RenderStyle.GRADIENT:
            self._draw_gradient(overlay, projected, cfg)
        elif cfg.style == RenderStyle.DOTTED:
            self._draw_dotted(overlay, projected, cfg)
        elif cfg.style == RenderStyle.TRAIL:
            self._draw_trail(overlay, projected, cfg)

        # Draw markers
        if cfg.show_release_point and projected:
            self._draw_marker(overlay, projected[0], cfg.color_start, "R", cfg)

        if cfg.show_plate_crossing and projected:
            self._draw_marker(overlay, projected[-1], cfg.color_end, "X", cfg)

        return overlay

    def _draw_solid(
        self,
        frame: np.ndarray,
        points: List[ProjectedPoint],
        cfg: TrajectoryRenderConfig,
    ) -> None:
        """Draw solid line trajectory."""
        if len(points) < 2:
            return

        pts = np.array([(int(p.u), int(p.v)) for p in points], dtype=np.int32)
        cv2.polylines(frame, [pts], False, cfg.color_start, cfg.line_thickness, cv2.LINE_AA)

    def _draw_gradient(
        self,
        frame: np.ndarray,
        points: List[ProjectedPoint],
        cfg: TrajectoryRenderConfig,
    ) -> None:
        """Draw gradient line trajectory (color changes from start to end)."""
        if len(points) < 2:
            return

        for i in range(len(points) - 1):
            # Interpolate color
            t = i / (len(points) - 1)
            color = self._interpolate_color(cfg.color_start, cfg.color_end, t)

            p1 = (int(points[i].u), int(points[i].v))
            p2 = (int(points[i + 1].u), int(points[i + 1].v))
            cv2.line(frame, p1, p2, color, cfg.line_thickness, cv2.LINE_AA)

    def _draw_dotted(
        self,
        frame: np.ndarray,
        points: List[ProjectedPoint],
        cfg: TrajectoryRenderConfig,
    ) -> None:
        """Draw dotted trajectory with circles at each point."""
        for i, point in enumerate(points):
            t = i / max(len(points) - 1, 1)
            color = self._interpolate_color(cfg.color_start, cfg.color_end, t)

            # Scale marker size by depth (closer = larger)
            size = max(2, int(cfg.marker_radius * (1.0 - point.z_ft / 100.0)))
            center = (int(point.u), int(point.v))
            cv2.circle(frame, center, size, color, -1, cv2.LINE_AA)

    def _draw_trail(
        self,
        frame: np.ndarray,
        points: List[ProjectedPoint],
        cfg: TrajectoryRenderConfig,
    ) -> None:
        """Draw fading trail trajectory."""
        if len(points) < 2:
            return

        fade_len = min(cfg.trail_fade_length, len(points))
        start_idx = max(0, len(points) - fade_len)

        for i in range(start_idx, len(points) - 1):
            # Fade based on position in trail
            fade_t = (i - start_idx) / max(fade_len - 1, 1)
            alpha = int(255 * fade_t)

            color = self._interpolate_color(cfg.color_start, cfg.color_end, 0.5)
            color = (color[0], color[1], color[2])  # No alpha in BGR

            p1 = (int(points[i].u), int(points[i].v))
            p2 = (int(points[i + 1].u), int(points[i + 1].v))

            # Draw with variable thickness based on fade
            thickness = max(1, int(cfg.line_thickness * fade_t))
            cv2.line(frame, p1, p2, color, thickness, cv2.LINE_AA)

    def _draw_marker(
        self,
        frame: np.ndarray,
        point: ProjectedPoint,
        color: Tuple[int, int, int],
        label: str,
        cfg: TrajectoryRenderConfig,
    ) -> None:
        """Draw a labeled marker at a trajectory point."""
        center = (int(point.u), int(point.v))

        # Outer circle
        cv2.circle(frame, center, cfg.marker_radius + 2, (0, 0, 0), 2, cv2.LINE_AA)
        cv2.circle(frame, center, cfg.marker_radius, color, -1, cv2.LINE_AA)

        # Label
        label_pos = (center[0] + cfg.marker_radius + 4, center[1] + 4)
        cv2.putText(frame, label, label_pos, cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1, cv2.LINE_AA)

    def _interpolate_color(
        self,
        c1: Tuple[int, int, int],
        c2: Tuple[int, int, int],
        t: float,
    ) -> Tuple[int, int, int]:
        """Interpolate between two colors.

        Args:
            c1: Start color (BGR)
            c2: End color (BGR)
            t: Interpolation factor (0-1)

        Returns:
            Interpolated color (BGR)
        """
        t = max(0, min(1, t))
        return (
            int(c1[0] + (c2[0] - c1[0]) * t),
            int(c1[1] + (c2[1] - c1[1]) * t),
            int(c1[2] + (c2[2] - c1[2]) * t),
        )


def create_trajectory_overlay(
    frame: np.ndarray,
    observations: List["StereoObservation"],
    geometry: "StereoGeometry",
    camera: str = "left",
    style: RenderStyle = RenderStyle.GRADIENT,
) -> np.ndarray:
    """Convenience function to add trajectory overlay to a frame.

    Args:
        frame: Input video frame
        observations: 3D trajectory observations
        geometry: Stereo camera geometry
        camera: Which camera ("left" or "right")
        style: Rendering style

    Returns:
        Frame with trajectory overlay
    """
    config = TrajectoryRenderConfig(style=style)
    renderer = TrajectoryRenderer(geometry, camera, config)
    return renderer.render_on_frame(frame, observations)


__all__ = [
    "TrajectoryRenderer",
    "TrajectoryRenderConfig",
    "RenderStyle",
    "ProjectedPoint",
    "create_trajectory_overlay",
]
