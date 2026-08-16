"""Typed result contracts for the stereo-rig setup state machine.

These dataclasses are durable, JSON-serializable records produced by the
individual setup steps (sync check, focus/exposure lock, overlap validation,
coarse rectification, ...). Keeping them as frozen contracts lets each setup
step be unit-tested in isolation with synthetic inputs and lets the wizard
persist a coherent setup profile.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, cast

# Sync-check verdicts (ordered worst -> best is not implied; treat as labels).
SYNC_VERDICT_GOOD = "GOOD"
SYNC_VERDICT_WARN = "WARN"
SYNC_VERDICT_POOR = "POOR"
SYNC_VERDICT_UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class SyncCheckResult:
    """Result of the setup-time left/right timestamp synchronization check.

    Produced from two streams of per-camera frame capture timestamps (host
    monotonic nanoseconds). It reports the measured pairing skew and whether it
    is small enough to trust stereo geometry at the target pitch speed.

    Attributes:
        sample_count: Number of left/right frames that were paired.
        unpaired_count: Frames that could not be paired within the tolerance.
        mean_delta_ms: Mean absolute left/right timestamp delta, milliseconds.
        p95_delta_ms: 95th-percentile absolute delta, milliseconds.
        max_delta_ms: Maximum absolute delta, milliseconds.
        jitter_ms: Standard deviation of the deltas, milliseconds.
        max_motion_in: Ball travel (inches) implied by max_delta at max_speed_mph.
        tolerance_ms: Pairing tolerance used for the check, milliseconds.
        max_speed_mph: Pitch speed used to convert timing skew to ball motion.
        verdict: One of SYNC_VERDICT_{GOOD,WARN,POOR,UNKNOWN}.
        passed: True when the verdict is acceptable to proceed (GOOD or WARN).
        recommendation: Human-readable guidance for the operator.
    """

    sample_count: int
    unpaired_count: int
    mean_delta_ms: float
    p95_delta_ms: float
    max_delta_ms: float
    jitter_ms: float
    max_motion_in: float
    tolerance_ms: float
    max_speed_mph: float
    verdict: str
    passed: bool
    recommendation: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "sample_count": self.sample_count,
            "unpaired_count": self.unpaired_count,
            "mean_delta_ms": self.mean_delta_ms,
            "p95_delta_ms": self.p95_delta_ms,
            "max_delta_ms": self.max_delta_ms,
            "jitter_ms": self.jitter_ms,
            "max_motion_in": self.max_motion_in,
            "tolerance_ms": self.tolerance_ms,
            "max_speed_mph": self.max_speed_mph,
            "verdict": self.verdict,
            "passed": self.passed,
            "recommendation": self.recommendation,
        }


# Per-camera focus/exposure/white-balance lock verdicts.
LOCK_VERDICT_LOCKED = "LOCKED"
LOCK_VERDICT_MARGINAL = "MARGINAL"
LOCK_VERDICT_UNLOCKED = "UNLOCKED"


@dataclass(frozen=True)
class FocusLockResult:
    """Result of the fixed-focus sharpness verification for a single camera.

    The target ArduCam cameras are fixed-focus, so this step verifies sharpness
    at the working distance and confirms autofocus is disabled, rather than
    adjusting focus.

    Attributes:
        camera_id: Camera label or serial this result applies to.
        sharpness: Focus score (e.g. variance of Laplacian) at working distance.
        sharpness_threshold: Minimum acceptable sharpness score.
        autofocus_disabled: True if autofocus is confirmed off/absent.
        verdict: One of LOCK_VERDICT_{LOCKED,MARGINAL,UNLOCKED}.
        passed: True when sharpness is acceptable and autofocus is disabled.
        recommendation: Human-readable guidance for the operator.
    """

    camera_id: str
    sharpness: float
    sharpness_threshold: float
    autofocus_disabled: bool
    verdict: str
    passed: bool
    recommendation: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "camera_id": self.camera_id,
            "sharpness": self.sharpness,
            "sharpness_threshold": self.sharpness_threshold,
            "autofocus_disabled": self.autofocus_disabled,
            "verdict": self.verdict,
            "passed": self.passed,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class ExposureLockResult:
    """Result of locking exposure/gain/white-balance for a single camera.

    Records the applied control values plus the values read back from the
    device so the wizard can verify the lock actually took effect (DirectShow
    silently ignores unsupported controls).

    Attributes:
        camera_id: Camera label or serial this result applies to.
        exposure_us: Applied exposure time in microseconds.
        gain: Applied analog/digital gain.
        white_balance_k: Applied white-balance color temperature in Kelvin.
        auto_exposure_disabled: True if auto-exposure is confirmed off.
        auto_white_balance_disabled: True if auto-white-balance is confirmed off.
        readback_verified: True if device readback matched the applied values.
        verdict: One of LOCK_VERDICT_{LOCKED,MARGINAL,UNLOCKED}.
        passed: True when all locks applied and verified.
        recommendation: Human-readable guidance for the operator.
    """

    camera_id: str
    exposure_us: float
    gain: float
    white_balance_k: float
    auto_exposure_disabled: bool
    auto_white_balance_disabled: bool
    readback_verified: bool
    verdict: str
    passed: bool
    recommendation: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "camera_id": self.camera_id,
            "exposure_us": self.exposure_us,
            "gain": self.gain,
            "white_balance_k": self.white_balance_k,
            "auto_exposure_disabled": self.auto_exposure_disabled,
            "auto_white_balance_disabled": self.auto_white_balance_disabled,
            "readback_verified": self.readback_verified,
            "verdict": self.verdict,
            "passed": self.passed,
            "recommendation": self.recommendation,
        }


# Stereo overlap / feature-match verdicts.
OVERLAP_VERDICT_GOOD = "GOOD"
OVERLAP_VERDICT_WARN = "WARN"
OVERLAP_VERDICT_POOR = "POOR"


@dataclass(frozen=True)
class StereoOverlapResult:
    """Result of validating that left/right cameras see the same scene.

    Produced by matching features between a synchronized left/right frame pair
    (e.g. ORB + RANSAC) and scoring the shared field of view. This gates coarse
    rectification: there is no point estimating epipolar geometry if the views
    barely overlap.

    Attributes:
        keypoints_left: Detected keypoints in the left frame.
        keypoints_right: Detected keypoints in the right frame.
        raw_matches: Candidate descriptor matches before geometric filtering.
        inlier_matches: Matches surviving RANSAC geometric verification.
        inlier_ratio: inlier_matches / max(raw_matches, 1).
        overlap_score: Estimated fraction of shared field of view, [0, 1].
        mean_match_distance_px: Mean descriptor-match pixel distance.
        verdict: One of OVERLAP_VERDICT_{GOOD,WARN,POOR}.
        passed: True when overlap is sufficient to attempt rectification.
        recommendation: Human-readable guidance for the operator.
    """

    keypoints_left: int
    keypoints_right: int
    raw_matches: int
    inlier_matches: int
    inlier_ratio: float
    overlap_score: float
    mean_match_distance_px: float
    verdict: str
    passed: bool
    recommendation: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "keypoints_left": self.keypoints_left,
            "keypoints_right": self.keypoints_right,
            "raw_matches": self.raw_matches,
            "inlier_matches": self.inlier_matches,
            "inlier_ratio": self.inlier_ratio,
            "overlap_score": self.overlap_score,
            "mean_match_distance_px": self.mean_match_distance_px,
            "verdict": self.verdict,
            "passed": self.passed,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class CoarseRectificationResult:
    """Result of targetless coarse stereo rectification.

    Produced by estimating the fundamental matrix from matched features and
    deriving uncalibrated rectifying homographies. Reports epipolar error before
    and after so the operator can see whether rectification actually helped.

    Attributes:
        fundamental_matrix: Estimated 3x3 F as a row-major 9-tuple, or None.
        left_homography: Left rectifying homography (9-tuple, row-major) or None.
        right_homography: Right rectifying homography (9-tuple, row-major) or None.
        epipolar_error_before_px: Mean symmetric epipolar error before rectify.
        epipolar_error_after_px: Mean vertical disparity after rectify.
        inlier_matches: Feature matches used to estimate F.
        converged: True if F estimation and homography derivation succeeded.
        passed: True when post-rectification epipolar error is acceptable.
        recommendation: Human-readable guidance for the operator.
    """

    fundamental_matrix: Tuple[float, ...]
    left_homography: Tuple[float, ...]
    right_homography: Tuple[float, ...]
    epipolar_error_before_px: float
    epipolar_error_after_px: float
    inlier_matches: int
    converged: bool
    passed: bool
    recommendation: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "fundamental_matrix": list(self.fundamental_matrix),
            "left_homography": list(self.left_homography),
            "right_homography": list(self.right_homography),
            "epipolar_error_before_px": self.epipolar_error_before_px,
            "epipolar_error_after_px": self.epipolar_error_after_px,
            "inlier_matches": self.inlier_matches,
            "converged": self.converged,
            "passed": self.passed,
            "recommendation": self.recommendation,
        }


@dataclass(frozen=True)
class StereoCalibrationProfile:
    """Durable, typed stereo calibration profile persisted inside a RigProfile.

    Captures the geometry needed to triangulate plus provenance so the loader
    can refuse quick-mode calibrations in production.

    Attributes:
        baseline_in: Camera baseline (distance between optical centers), inches.
        rms_reprojection_px: Stereo calibration RMS reprojection error, pixels.
        epipolar_error_px: Mean epipolar error, pixels.
        image_width: Calibration image width, pixels.
        image_height: Calibration image height, pixels.
        source: How the profile was produced ("targetless", "charuco", "quick").
        production_ready: True only for full, validated calibrations.
        calibration_file: Path to the backing NPZ, if any.
        created_utc: ISO-8601 UTC timestamp of creation.
        app_version: App version that produced the profile.
        schema_version: Contract/schema version for the profile.
    """

    baseline_in: float
    rms_reprojection_px: float
    epipolar_error_px: float
    image_width: int
    image_height: int
    source: str
    production_ready: bool
    calibration_file: str = ""
    created_utc: str = ""
    app_version: str = ""
    schema_version: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "baseline_in": self.baseline_in,
            "rms_reprojection_px": self.rms_reprojection_px,
            "epipolar_error_px": self.epipolar_error_px,
            "image_width": self.image_width,
            "image_height": self.image_height,
            "source": self.source,
            "production_ready": self.production_ready,
            "calibration_file": self.calibration_file,
            "created_utc": self.created_utc,
            "app_version": self.app_version,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_payload(cls, data: Dict[str, object]) -> "StereoCalibrationProfile":
        """Reconstruct from a dict produced by to_payload (tolerant of gaps)."""
        return cls(
            baseline_in=float(cast(float | str, data.get("baseline_in", 0.0) or 0.0)),
            rms_reprojection_px=float(cast(float | str, data.get("rms_reprojection_px", 0.0) or 0.0)),
            epipolar_error_px=float(cast(float | str, data.get("epipolar_error_px", 0.0) or 0.0)),
            image_width=int(cast(int | str, data.get("image_width", 0) or 0)),
            image_height=int(cast(int | str, data.get("image_height", 0) or 0)),
            source=str(data.get("source", "") or ""),
            production_ready=bool(data.get("production_ready", False)),
            calibration_file=str(data.get("calibration_file", "") or ""),
            created_utc=str(data.get("created_utc", "") or ""),
            app_version=str(data.get("app_version", "") or ""),
            schema_version=str(data.get("schema_version", "") or ""),
        )


QUALITY_GRADE_EXCELLENT = "EXCELLENT"
QUALITY_GRADE_GOOD = "GOOD"
QUALITY_GRADE_MARGINAL = "MARGINAL"
QUALITY_GRADE_FAIL = "FAIL"


@dataclass(frozen=True)
class CalibrationQualityReport:
    """Durable, typed quality report produced at the end of setup (step 9).

    Aggregates the verdicts of the individual setup steps into a single grade
    and a flat list of human-readable findings/warnings for the operator and
    for support bundles.

    Attributes:
        grade: One of QUALITY_GRADE_{EXCELLENT,GOOD,MARGINAL,FAIL}.
        rms_reprojection_px: Final stereo RMS reprojection error, pixels.
        epipolar_error_px: Final mean epipolar error, pixels.
        baseline_in: Estimated baseline, inches.
        sync: Optional sync-check result.
        overlap: Optional overlap-validation result.
        rectification: Optional coarse-rectification result.
        focus_locks: Per-camera focus-lock results.
        exposure_locks: Per-camera exposure-lock results.
        warnings: Non-fatal findings the operator should be aware of.
        passed: True when the rig is acceptable for live tracking.
        created_utc: ISO-8601 UTC timestamp of creation.
    """

    grade: str
    rms_reprojection_px: float
    epipolar_error_px: float
    baseline_in: float
    passed: bool
    sync: SyncCheckResult | None = None
    overlap: StereoOverlapResult | None = None
    rectification: CoarseRectificationResult | None = None
    focus_locks: List[FocusLockResult] = field(default_factory=list)
    exposure_locks: List[ExposureLockResult] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    created_utc: str = ""

    def to_payload(self) -> Dict[str, object]:
        """Return a JSON-serializable dict for manifests/reports."""
        return {
            "grade": self.grade,
            "rms_reprojection_px": self.rms_reprojection_px,
            "epipolar_error_px": self.epipolar_error_px,
            "baseline_in": self.baseline_in,
            "passed": self.passed,
            "sync": self.sync.to_payload() if self.sync else None,
            "overlap": self.overlap.to_payload() if self.overlap else None,
            "rectification": (self.rectification.to_payload() if self.rectification else None),
            "focus_locks": [lock.to_payload() for lock in self.focus_locks],
            "exposure_locks": [lock.to_payload() for lock in self.exposure_locks],
            "warnings": list(self.warnings),
            "created_utc": self.created_utc,
        }
