"""Pitch analysis for trajectory fitting and summary creation."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, List, Optional

from app.contracts import PitchSummary
from configs.settings import AppConfig
from contracts import RayObservation, StereoObservation
from metrics.simple_metrics import compute_plate_from_observations
from metrics.strike_zone import build_strike_zone, is_strike
from trajectory.camera_model import load_stereo_ray_camera_models
from trajectory.contracts import FailureCode, TrajectoryDiagnostics, TrajectoryFitRequest, TrajectoryFitResult
from trajectory.registry import TrajectoryFitterRegistry
from app.pipeline.analysis.observation_diagnostics import summarize_observations

logger = logging.getLogger(__name__)


class PitchAnalyzer:
    """Analyzes pitch observations to create summary with trajectory and metrics.

    Handles:
    - Strike zone calculation
    - Plate metrics computation
    - Trajectory fitting with physics-based drag model
    - Pitch summary creation
    """

    def __init__(
        self,
        config: AppConfig,
        get_ball_radius_fn,
        radar_speed_fn,
    ):
        """Initialize pitch analyzer.

        Args:
            config: Application configuration
            get_ball_radius_fn: Function to get current ball radius in inches
            radar_speed_fn: Function to get radar speed in mph (or None)
        """
        self._config = config
        self._get_ball_radius_fn = get_ball_radius_fn
        self._radar_speed_fn = radar_speed_fn
        self._trajectory_registry = TrajectoryFitterRegistry()

    def analyze_pitch(
        self,
        pitch_id: str,
        start_ns: int,
        end_ns: int,
        observations: List[StereoObservation],
        ray_observations: Optional[List[RayObservation]] = None,
    ):
        """Analyze pitch observations and create summary.

        Args:
            pitch_id: Pitch ID
            start_ns: Pitch start timestamp
            end_ns: Pitch end timestamp
            observations: List of stereo observations

        Returns:
            PitchSummary object
        """
        # Compute strike zone
        zone = build_strike_zone(
            plate_z_ft=self._config.metrics.plate_plane_z_ft,
            plate_width_in=self._config.strike_zone.plate_width_in,
            plate_length_in=self._config.strike_zone.plate_length_in,
            batter_height_in=self._config.strike_zone.batter_height_in,
            top_ratio=self._config.strike_zone.top_ratio,
            bottom_ratio=self._config.strike_zone.bottom_ratio,
        )
        radius_in = self._get_ball_radius_fn()
        strike = is_strike(observations, zone, radius_in)

        # Compute plate metrics
        metrics = compute_plate_from_observations(observations)
        observation_stats = summarize_observations(observations)

        # Get radar speed
        radar_speed = self._radar_speed_fn()

        # Fit trajectory
        ray_observations = list(ray_observations or [])
        trajectory_result, trajectory_mode, comparison = self._fit_trajectory_modes(
            observations=list(observations),
            ray_observations=ray_observations,
            radar_speed=radar_speed,
        )

        # Extract plate crossing
        crossing_xyz = trajectory_result.plate_crossing_xyz_ft if trajectory_result else None

        # Extract diagnostics
        diagnostics = trajectory_result.diagnostics if trajectory_result else None

        # Create summary
        summary = PitchSummary(
            pitch_id=pitch_id,
            t_start_ns=start_ns,
            t_end_ns=end_ns,
            is_strike=strike.is_strike,
            zone_row=strike.zone_row,
            zone_col=strike.zone_col,
            run_in=metrics.run_in,
            rise_in=metrics.rise_in,
            speed_mph=radar_speed,
            rotation_rpm=None,
            sample_count=metrics.sample_count,
            trajectory_plate_x_ft=crossing_xyz[0] if crossing_xyz else None,
            trajectory_plate_y_ft=crossing_xyz[1] if crossing_xyz else None,
            trajectory_plate_z_ft=crossing_xyz[2] if crossing_xyz else None,
            trajectory_plate_t_ns=trajectory_result.plate_crossing_t_ns if trajectory_result else None,
            trajectory_model=trajectory_result.model_name if trajectory_result else None,
            trajectory_expected_error_ft=trajectory_result.expected_plate_error_ft if trajectory_result else None,
            trajectory_confidence=trajectory_result.confidence if trajectory_result else None,
            # Diagnostics for online calibration refinement
            trajectory_drag_param=diagnostics.drag_param if diagnostics else None,
            trajectory_rmse_px=diagnostics.rmse_px if diagnostics else None,
            trajectory_rmse_3d_ft=diagnostics.rmse_3d_ft if diagnostics else None,
            trajectory_mode=trajectory_mode,
            trajectory_comparison=comparison,
            ray_rmse_px=diagnostics.rmse_px if diagnostics and trajectory_mode and trajectory_mode.startswith("ray_") else None,
            estimated_camera_time_offset_ms=diagnostics.estimated_camera_time_offset_ms if diagnostics else None,
            ray_failure_codes=_ray_failure_codes(comparison),
            observation_duration_ms=observation_stats["observation_duration_ms"],
            observation_rate_hz=observation_stats["observation_rate_hz"],
            observation_max_gap_ms=observation_stats["observation_max_gap_ms"],
            observation_z_span_ft=observation_stats["observation_z_span_ft"],
            observation_mean_confidence=observation_stats["observation_mean_confidence"],
        )

        return summary

    def update_config(self, config: AppConfig) -> None:
        """Update configuration.

        Args:
            config: New application configuration
        """
        self._config = config

    def _fit_trajectory_modes(
        self,
        observations: List[StereoObservation],
        ray_observations: List[RayObservation],
        radar_speed: Optional[float],
    ) -> tuple[Optional[TrajectoryFitResult], Optional[str], Dict[str, dict]]:
        trajectory_config = self._config.trajectory
        modes = [trajectory_config.primary_mode]
        for mode in trajectory_config.compare_modes:
            if mode not in modes:
                modes.append(mode)

        camera_models = self._load_ray_camera_models() if any(mode.startswith("ray_") for mode in modes) else {}
        comparison: Dict[str, dict] = {}
        results: Dict[str, TrajectoryFitResult] = {}

        for mode in modes:
            request = self._build_trajectory_request(
                mode=mode,
                observations=observations,
                ray_observations=ray_observations,
                camera_models=camera_models,
                radar_speed=radar_speed,
            )
            result = self._run_mode(mode, request)
            results[mode] = result
            comparison[mode] = _compact_trajectory_result(result)

        primary_mode = trajectory_config.primary_mode
        primary_result = results.get(primary_mode)
        if _result_is_usable(primary_result):
            return primary_result, primary_mode, comparison

        if (
            primary_mode.startswith("ray_")
            and trajectory_config.fallback_to_stereo
            and observations
        ):
            stereo_result = results.get("stereo_3d")
            if stereo_result is None:
                stereo_request = self._build_trajectory_request(
                    mode="stereo_3d",
                    observations=observations,
                    ray_observations=ray_observations,
                    camera_models=camera_models,
                    radar_speed=radar_speed,
                )
                stereo_result = self._run_mode("stereo_3d", stereo_request)
                comparison["stereo_3d"] = _compact_trajectory_result(stereo_result)
            if _result_is_usable(stereo_result):
                comparison[primary_mode]["fallback_used"] = "stereo_3d"
                return stereo_result, "stereo_3d", comparison

        return primary_result, primary_mode, comparison

    def _build_trajectory_request(
        self,
        mode: str,
        observations: List[StereoObservation],
        ray_observations: List[RayObservation],
        camera_models: dict,
        radar_speed: Optional[float],
    ) -> TrajectoryFitRequest:
        ray_config = self._config.trajectory.ray
        return TrajectoryFitRequest(
            observations=list(observations),
            plate_plane_z_ft=self._config.metrics.plate_plane_z_ft,
            ray_observations=list(ray_observations),
            camera_models=dict(camera_models),
            mode=mode,
            radar_speed_mph=radar_speed,
            radar_speed_ref="release",
            max_time_offset_ms=ray_config.max_time_offset_ms,
            time_offset_prior_ms=ray_config.time_offset_prior_ms,
            min_rays_per_camera=ray_config.min_rays_per_camera,
            max_candidates_per_frame=ray_config.max_candidates_per_frame,
            max_reprojection_px=ray_config.max_reprojection_px,
            robust_loss=ray_config.robust_loss,
        )

    def _run_mode(self, mode: str, request: TrajectoryFitRequest) -> TrajectoryFitResult:
        try:
            return self._trajectory_registry.create(mode).fit_trajectory(request)
        except ValueError:
            diagnostics = TrajectoryDiagnostics(failure_codes=[FailureCode.UNKNOWN_TRAJECTORY_MODE])
            return _failure_result(mode, diagnostics)
        except Exception as exc:
            logger.warning("Trajectory mode %s failed: %s", mode, exc, exc_info=True)
            diagnostics = TrajectoryDiagnostics(
                failure_codes=[FailureCode.REPROJECTION_FAILED],
                notes=[f"{exc.__class__.__name__}: {exc}"],
            )
            return _failure_result(mode, diagnostics)

    def _load_ray_camera_models(self) -> dict:
        try:
            return load_stereo_ray_camera_models(Path("calibration/stereo_calibration.npz"))
        except Exception as exc:
            logger.debug("Ray camera models unavailable: %s", exc)
            return {}


def _result_is_usable(result: Optional[TrajectoryFitResult]) -> bool:
    return bool(result and result.plate_crossing_xyz_ft is not None and result.confidence > 0.0)


def _compact_trajectory_result(result: TrajectoryFitResult) -> dict:
    return {
        "model_name": result.model_name,
        "plate_crossing_xyz_ft": result.plate_crossing_xyz_ft,
        "plate_crossing_t_ns": result.plate_crossing_t_ns,
        "expected_plate_error_ft": result.expected_plate_error_ft,
        "confidence": result.confidence,
        "diagnostics": result.diagnostics.to_dict(),
        "sample_count": len(result.samples),
        "residual_count": len(result.residuals),
    }


def _failure_result(model_name: str, diagnostics: TrajectoryDiagnostics) -> TrajectoryFitResult:
    return TrajectoryFitResult(
        model_name=model_name,
        samples=[],
        plate_crossing_xyz_ft=None,
        plate_crossing_t_ns=None,
        expected_plate_error_ft=None,
        confidence=0.0,
        diagnostics=diagnostics,
    )


def _ray_failure_codes(comparison: Dict[str, dict]) -> Optional[List[str]]:
    codes: List[str] = []
    for mode, result in comparison.items():
        if not mode.startswith("ray_"):
            continue
        diagnostics = result.get("diagnostics") or {}
        codes.extend(str(code) for code in diagnostics.get("failure_codes", []))
    return codes or None
