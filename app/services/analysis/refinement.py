"""Online calibration refinement accumulation for AnalysisService.

Encapsulates the advisory refinement path that runs after a successful
terminal pitch verdict is published.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from app.contracts import PitchSummary
from app.events.event_types import PitchEndEvent
from calib.online_refinement import OnlineCalibrationRefiner
from configs.settings import AppConfig
from log_config.logger import get_logger

logger = get_logger(__name__)


class RefinementAccumulator:
    """Manages online calibration refinement state."""

    def __init__(self, config: AppConfig) -> None:
        self._enabled = config.metrics.online_refinement_enabled
        self._refiner: Optional[OnlineCalibrationRefiner] = None
        if self._enabled:
            try:
                config_path = Path("configs/default.yaml")
                self._refiner = OnlineCalibrationRefiner(config_path)
                logger.info("Online calibration refinement enabled")
            except Exception as e:
                logger.warning(f"Failed to initialize calibration refiner: {e}")
                self._enabled = False

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_summary(self) -> Optional[dict]:
        """Get refinement summary, or None if disabled."""
        if not self._enabled or not self._refiner:
            return None
        return self._refiner.get_refinement_summary()

    def accumulate(self, summary: PitchSummary, event: PitchEndEvent) -> None:
        """Accumulate trajectory for online calibration refinement.

        Raises on failure so the caller can log and continue.
        """
        if not self._refiner:
            return

        trajectory_data = {
            "timestamp_ns": summary.t_end_ns,
            "drag_k0_fit": summary.trajectory_drag_param or 0.1,
            "time_sync_residual_ns": 0,
            "plate_crossing_z_ft": summary.trajectory_plate_z_ft or 0.0,
            "mean_epipolar_error_px": summary.trajectory_rmse_px or 1.0,
            "max_epipolar_error_px": (summary.trajectory_rmse_px * 1.5) if summary.trajectory_rmse_px else 1.5,
            "num_observations": summary.sample_count,
            "confidence_score": summary.trajectory_confidence or 0.0,
        }

        accepted = self._refiner.accumulate_trajectory(trajectory_data)
        if not accepted:
            return

        logger.debug(
            "Trajectory %s accumulated for refinement (%d total)",
            summary.pitch_id,
            self._refiner.state.num_trajectories_accumulated,
        )

        if self._refiner.should_refine():
            result = self._refiner.refine_parameters()
            if result.get("proposed"):
                logger.warning(
                    "Calibration refinement proposal created in shadow mode; "
                    "configuration was not changed: %s",
                    "; ".join(result["changes"]),
                )
                logger.info("Refinement proposal confidence: %.2f", result["confidence"])
            else:
                logger.info("Refinement check: %s", result["reason"])

            health = self._refiner.validate_calibration_health()
            if health["alert"]:
                logger.warning("Calibration health alert: %s", health["reason"])
            else:
                logger.debug("Calibration health: %s", health["reason"])
