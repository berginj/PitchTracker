"""Online calibration parameter refinement.

This module enables automatic refinement of calibration parameters using
accumulated pitch tracking data. It can refine:
- Drag coefficient (drag_k0): Global average from trajectory fits
- Time sync offset: Systematic time synchronization bias
- Plate plane Z: Strike zone reference location

Parameters that CANNOT be refined (require full recalibration):
- Baseline: Requires known world scale
- Focal length: Requires multi-view geometry
- Rotation/Translation: Requires extrinsic reference

The refinement process:
1. Accumulate high-confidence trajectories (>70% confidence, <2px residuals)
2. After N trajectories, analyze systematic biases
3. Refine parameters if bias exceeds threshold
4. Update config with refined values
5. Monitor calibration health (epipolar error trend)
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional, List, Dict, Any
import numpy as np
import yaml
import logging

logger = logging.getLogger(__name__)


@dataclass
class RefinementState:
    """State for online calibration refinement."""

    # Refinable parameters
    drag_k0: float = 0.1  # Default drag coefficient
    time_sync_offset_ns: int = 0  # Systematic time sync bias
    plate_plane_z_ft: float = 0.0  # Strike zone reference

    # Accumulation state
    num_trajectories_accumulated: int = 0
    trajectories_buffer: List[Dict[str, Any]] = field(default_factory=list)

    # Health monitoring
    epipolar_error_trend: List[float] = field(default_factory=list)
    refinement_confidence: float = 0.0  # 0-1, higher = more confident

    # Metadata
    last_refinement_date: Optional[str] = None
    refinement_count: int = 0


@dataclass
class TrajectoryStats:
    """Statistics from a high-confidence trajectory."""

    timestamp_ns: int
    drag_k0_fit: float
    time_sync_residual_ns: float
    plate_crossing_z_ft: float
    mean_epipolar_error_px: float
    max_epipolar_error_px: float
    num_observations: int
    confidence_score: float


class OnlineCalibrationRefiner:
    """Online refinement of calibration parameters."""

    # Quality thresholds
    MIN_CONFIDENCE = 0.70  # Minimum trajectory confidence
    MAX_EPIPOLAR_ERROR = 2.0  # Maximum epipolar error (px)
    MIN_OBSERVATIONS = 10  # Minimum observations per trajectory

    # Refinement thresholds
    MIN_TRAJECTORIES = 50  # Accumulate N before refining
    BIAS_THRESHOLD_PERCENT = 10.0  # Refine if bias > 10%
    TIME_SYNC_THRESHOLD_MS = 5.0  # Refine if bias > 5ms

    # Health monitoring
    EPIPOLAR_ALERT_THRESHOLD = 5.0  # Alert if error > 5px
    RECALIBRATION_INTERVAL_DAYS = 30

    def __init__(self, config_path: Path):
        """Initialize refiner.

        Args:
            config_path: Path to configuration YAML file
        """
        self.config_path = config_path
        self.state = self._load_state()

    def _load_state(self) -> RefinementState:
        """Load refinement state from config."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            metrics = config.get('metrics', {})
            stereo = config.get('stereo', {})

            return RefinementState(
                drag_k0=metrics.get('drag_k0_default', 0.1),
                time_sync_offset_ns=stereo.get('time_sync_offset_ns', 0),
                plate_plane_z_ft=metrics.get('plate_plane_z_ft', 0.0),
                last_refinement_date=metrics.get('last_refinement_date'),
            )
        except Exception as e:
            logger.warning(f"Failed to load refinement state: {e}. Using defaults.")
            return RefinementState()

    def _save_state(self) -> None:
        """Save refinement state to config."""
        try:
            with open(self.config_path, 'r') as f:
                config = yaml.safe_load(f)

            # Update refinement parameters
            config.setdefault('metrics', {})['drag_k0_default'] = float(self.state.drag_k0)
            config['metrics']['last_refinement_date'] = self.state.last_refinement_date
            config.setdefault('metrics', {})['plate_plane_z_ft'] = float(self.state.plate_plane_z_ft)

            config.setdefault('stereo', {})['time_sync_offset_ns'] = int(self.state.time_sync_offset_ns)

            with open(self.config_path, 'w') as f:
                yaml.dump(config, f, default_flow_style=False, sort_keys=False)

            logger.info(f"Saved refinement state: drag_k0={self.state.drag_k0:.4f}, "
                       f"time_sync_offset={self.state.time_sync_offset_ns}ns, "
                       f"plate_z={self.state.plate_plane_z_ft:.2f}ft")
        except Exception as e:
            logger.error(f"Failed to save refinement state: {e}")

    def accumulate_trajectory(self, trajectory_result: Dict[str, Any]) -> bool:
        """Accumulate a trajectory for refinement.

        Args:
            trajectory_result: Dictionary with trajectory data including:
                - timestamp_ns: Trajectory timestamp
                - drag_k0_fit: Fitted drag coefficient
                - time_sync_residual_ns: Time synchronization residual
                - plate_crossing_z_ft: Z coordinate at plate crossing
                - mean_epipolar_error_px: Mean epipolar error
                - max_epipolar_error_px: Maximum epipolar error
                - num_observations: Number of 3D observations
                - confidence_score: Overall trajectory confidence

        Returns:
            True if trajectory accepted, False if rejected
        """
        # Extract statistics
        stats = TrajectoryStats(
            timestamp_ns=trajectory_result.get('timestamp_ns', 0),
            drag_k0_fit=trajectory_result.get('drag_k0_fit', 0.1),
            time_sync_residual_ns=trajectory_result.get('time_sync_residual_ns', 0),
            plate_crossing_z_ft=trajectory_result.get('plate_crossing_z_ft', 0.0),
            mean_epipolar_error_px=trajectory_result.get('mean_epipolar_error_px', 999.0),
            max_epipolar_error_px=trajectory_result.get('max_epipolar_error_px', 999.0),
            num_observations=trajectory_result.get('num_observations', 0),
            confidence_score=trajectory_result.get('confidence_score', 0.0),
        )

        # Quality check
        if stats.confidence_score < self.MIN_CONFIDENCE:
            logger.debug(f"Rejected trajectory: low confidence ({stats.confidence_score:.2f})")
            return False

        if stats.mean_epipolar_error_px > self.MAX_EPIPOLAR_ERROR:
            logger.debug(f"Rejected trajectory: high epipolar error ({stats.mean_epipolar_error_px:.2f}px)")
            return False

        if stats.num_observations < self.MIN_OBSERVATIONS:
            logger.debug(f"Rejected trajectory: insufficient observations ({stats.num_observations})")
            return False

        # Accept trajectory
        self.state.trajectories_buffer.append(trajectory_result)
        self.state.num_trajectories_accumulated += 1
        self.state.epipolar_error_trend.append(stats.mean_epipolar_error_px)

        # Limit trend history to last 100 trajectories
        if len(self.state.epipolar_error_trend) > 100:
            self.state.epipolar_error_trend = self.state.epipolar_error_trend[-100:]

        logger.debug(f"Accumulated trajectory {self.state.num_trajectories_accumulated}: "
                    f"drag={stats.drag_k0_fit:.4f}, epipolar_error={stats.mean_epipolar_error_px:.2f}px")

        return True

    def should_refine(self) -> bool:
        """Check if we have enough data to refine parameters."""
        return self.state.num_trajectories_accumulated >= self.MIN_TRAJECTORIES

    def refine_parameters(self) -> Dict[str, Any]:
        """Refine calibration parameters using accumulated trajectories.

        Returns:
            Dictionary with refinement results:
                - refined: True if refinement applied
                - drag_k0_old, drag_k0_new: Drag coefficient before/after
                - time_sync_offset_old, time_sync_offset_new: Time sync before/after
                - plate_z_old, plate_z_new: Plate Z before/after
                - confidence: Refinement confidence (0-1)
                - reason: Description of changes
        """
        if not self.should_refine():
            return {
                'refined': False,
                'reason': f'Insufficient trajectories ({self.state.num_trajectories_accumulated}/{self.MIN_TRAJECTORIES})',
            }

        logger.info(f"Refining parameters using {self.state.num_trajectories_accumulated} trajectories")

        # Extract statistics from buffer
        drag_k0_values = [t['drag_k0_fit'] for t in self.state.trajectories_buffer if 'drag_k0_fit' in t]
        time_sync_values = [t['time_sync_residual_ns'] for t in self.state.trajectories_buffer if 'time_sync_residual_ns' in t]
        plate_z_values = [t['plate_crossing_z_ft'] for t in self.state.trajectories_buffer if 'plate_crossing_z_ft' in t]

        # Store old values
        old_drag_k0 = self.state.drag_k0
        old_time_sync = self.state.time_sync_offset_ns
        old_plate_z = self.state.plate_plane_z_ft

        refined = False
        changes = []

        # 1. Refine drag coefficient
        if len(drag_k0_values) >= self.MIN_TRAJECTORIES // 2:
            new_drag_k0 = float(np.median(drag_k0_values))
            drag_change_percent = abs(new_drag_k0 - old_drag_k0) / old_drag_k0 * 100

            if drag_change_percent > self.BIAS_THRESHOLD_PERCENT:
                self.state.drag_k0 = new_drag_k0
                refined = True
                changes.append(f"drag_k0: {old_drag_k0:.4f} → {new_drag_k0:.4f} ({drag_change_percent:.1f}% change)")
                logger.info(f"Refined drag_k0: {old_drag_k0:.4f} → {new_drag_k0:.4f}")

        # 2. Refine time sync offset
        if len(time_sync_values) >= self.MIN_TRAJECTORIES // 2:
            median_residual_ns = float(np.median(time_sync_values))
            median_residual_ms = median_residual_ns / 1e6

            if abs(median_residual_ms) > self.TIME_SYNC_THRESHOLD_MS:
                self.state.time_sync_offset_ns += int(median_residual_ns)
                refined = True
                changes.append(f"time_sync_offset: {old_time_sync}ns → {self.state.time_sync_offset_ns}ns ({median_residual_ms:.2f}ms bias)")
                logger.info(f"Refined time_sync_offset: {old_time_sync}ns → {self.state.time_sync_offset_ns}ns")

        # 3. Refine plate plane Z (if we have plate crossing data)
        if len(plate_z_values) >= self.MIN_TRAJECTORIES // 2:
            new_plate_z = float(np.median(plate_z_values))
            plate_change_ft = abs(new_plate_z - old_plate_z)

            # Only refine if change is significant (> 1 foot)
            if plate_change_ft > 1.0:
                self.state.plate_plane_z_ft = new_plate_z
                refined = True
                changes.append(f"plate_plane_z: {old_plate_z:.2f}ft → {new_plate_z:.2f}ft ({plate_change_ft:.2f}ft change)")
                logger.info(f"Refined plate_plane_z: {old_plate_z:.2f}ft → {new_plate_z:.2f}ft")

        # Calculate refinement confidence
        self.state.refinement_confidence = min(
            1.0,
            self.state.num_trajectories_accumulated / (self.MIN_TRAJECTORIES * 2)
        )

        # Update metadata
        if refined:
            self.state.last_refinement_date = datetime.now().isoformat()
            self.state.refinement_count += 1
            self._save_state()

        # Clear buffer
        self.state.trajectories_buffer.clear()
        self.state.num_trajectories_accumulated = 0

        return {
            'refined': refined,
            'drag_k0_old': old_drag_k0,
            'drag_k0_new': self.state.drag_k0,
            'time_sync_offset_old': old_time_sync,
            'time_sync_offset_new': self.state.time_sync_offset_ns,
            'plate_z_old': old_plate_z,
            'plate_z_new': self.state.plate_plane_z_ft,
            'confidence': self.state.refinement_confidence,
            'changes': changes,
            'reason': '; '.join(changes) if changes else 'No significant biases detected',
        }

    def validate_calibration_health(self) -> Dict[str, Any]:
        """Validate calibration health using epipolar error trend.

        Returns:
            Dictionary with health assessment:
                - healthy: True if calibration is healthy
                - mean_error_px: Mean epipolar error
                - trend: 'stable', 'improving', or 'degrading'
                - alert: True if recalibration recommended
                - reason: Description of health status
        """
        if len(self.state.epipolar_error_trend) < 10:
            return {
                'healthy': True,
                'mean_error_px': 0.0,
                'trend': 'unknown',
                'alert': False,
                'reason': 'Insufficient data for health assessment',
            }

        # Calculate statistics
        recent_errors = self.state.epipolar_error_trend[-20:]  # Last 20 trajectories
        mean_error = float(np.mean(recent_errors))

        # Detect trend using linear regression
        x = np.arange(len(recent_errors))
        y = np.array(recent_errors)
        slope, _ = np.polyfit(x, y, 1)

        # Classify trend
        if slope > 0.1:
            trend = 'degrading'
        elif slope < -0.1:
            trend = 'improving'
        else:
            trend = 'stable'

        # Check for alerts
        alert = mean_error > self.EPIPOLAR_ALERT_THRESHOLD

        # Check recalibration interval
        if self.state.last_refinement_date:
            try:
                last_refinement = datetime.fromisoformat(self.state.last_refinement_date)
                days_since_refinement = (datetime.now() - last_refinement).days

                if days_since_refinement > self.RECALIBRATION_INTERVAL_DAYS:
                    alert = True
                    reason = f"Recalibration recommended (last refinement {days_since_refinement} days ago)"
                else:
                    reason = f"Calibration healthy (mean error: {mean_error:.2f}px, trend: {trend})"
            except ValueError:
                reason = f"Calibration healthy (mean error: {mean_error:.2f}px, trend: {trend})"
        else:
            reason = f"Calibration healthy (mean error: {mean_error:.2f}px, trend: {trend})"

        if alert and mean_error > self.EPIPOLAR_ALERT_THRESHOLD:
            reason = f"Alert: High epipolar error ({mean_error:.2f}px). Recalibration recommended."

        return {
            'healthy': not alert,
            'mean_error_px': mean_error,
            'trend': trend,
            'alert': alert,
            'reason': reason,
        }

    def get_refinement_summary(self) -> Dict[str, Any]:
        """Get summary of refinement state.

        Returns:
            Dictionary with refinement summary
        """
        health = self.validate_calibration_health()

        return {
            'drag_k0': self.state.drag_k0,
            'time_sync_offset_ns': self.state.time_sync_offset_ns,
            'plate_plane_z_ft': self.state.plate_plane_z_ft,
            'trajectories_accumulated': self.state.num_trajectories_accumulated,
            'refinement_count': self.state.refinement_count,
            'refinement_confidence': self.state.refinement_confidence,
            'last_refinement_date': self.state.last_refinement_date,
            'calibration_healthy': health['healthy'],
            'mean_epipolar_error_px': health['mean_error_px'],
            'error_trend': health['trend'],
        }
