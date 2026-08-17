"""LiveSetupContext — shared hardware context for the canonical stereo setup workflow."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
import hashlib
from pathlib import Path
import uuid
from typing import TYPE_CHECKING, Any, Callable, Iterable, Optional

from capture.camera_device import CameraDevice
from capture.device_discovery import list_uvc_devices
from capture.uvc_backend import UvcCamera
from contracts.capability_observation import CapabilityObservation
from contracts.catalog import SIDE_UNASSIGNED, SIDE_LEFT, SIDE_RIGHT
from contracts.setup import CoarseRectificationResult, StereoOverlapResult, SyncCheckResult
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureRequest, SetupCaptureResult, SetupFrameRecord
from contracts.types import Frame
from exceptions import CameraError
from ui.setup.paired_preview_view import PairedPreviewSnapshot, empty_preview_snapshot

from ui.setup.providers.discovery import DeviceLister, discover_camera_selection
from ui.setup.providers.support import (
    CameraCatalog,
    _effective_pixfmt,
    _normalize_mode,
)

if TYPE_CHECKING:
    from calib.capture_qualification import CaptureQualification
    from ui.setup.camera_select_view import CameraSelectionSnapshot
    from ui.setup.focus_lock_view import FocusExposureSnapshot
    from contracts.setup import CalibrationQualityReport, StereoCalibrationProfile


@dataclass
class LiveSetupContext:
    """Shared hardware context carried through the canonical setup workflow."""

    catalog: Optional[CameraCatalog]
    list_devices: DeviceLister = list_uvc_devices
    camera_factory: Callable[[], CameraDevice] = UvcCamera
    config_path: Path = Path("configs/default.yaml")
    last_left_frames: list[Frame] = field(default_factory=list)
    last_right_frames: list[Frame] = field(default_factory=list)
    last_controls: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_modes: dict[str, dict[str, Any]] = field(default_factory=dict)
    last_capability_observations: dict[str, CapabilityObservation] = field(default_factory=dict)
    last_qualification: Optional["CaptureQualification"] = None
    last_sync: Optional[SyncCheckResult] = None
    last_focus: Optional["FocusExposureSnapshot"] = None
    last_overlap: Optional[StereoOverlapResult] = None
    last_rectification: Optional[CoarseRectificationResult] = None
    last_capture_diagnostics: dict[str, Any] = field(default_factory=dict)
    setup_capture_backend: str = "uvc"
    assignment_generation: int = 0
    rig_profile_dir: Path = Path("calibration/rigs")
    validated_camera_pairs_provider: Optional[Callable[[], Iterable[dict[str, Any]]]] = None

    def selection(self) -> "CameraSelectionSnapshot":
        from configs.settings import load_config

        config = load_config(self.config_path)
        validated_pairs = (
            list(self.validated_camera_pairs_provider())
            if self.validated_camera_pairs_provider is not None
            else self._previously_validated_camera_pairs()
        )
        return discover_camera_selection(
            list_devices=self.list_devices,
            catalog=self.catalog,
            requested_mode=(config.camera.width, config.camera.height, config.camera.fps),
            validated_pairs=validated_pairs,
        )

    def _previously_validated_camera_pairs(self) -> list[dict[str, Any]]:
        from app.services.rig_profile import RigProfileService

        return RigProfileService(
            base_dir=self.rig_profile_dir,
            config_path=self.config_path,
        ).previously_validated_camera_pairs()

    def assign(self, left_id: str, right_id: str) -> None:
        if left_id == right_id:
            raise ValueError("left and right cameras must be distinct")
        if self.catalog is None:
            raise RuntimeError("camera catalog is required to persist assignments")
        snapshot = self.selection()
        by_id = {camera.hardware_id: camera for camera in snapshot.cameras}
        missing_ids = [hardware_id for hardware_id in (left_id, right_id) if hardware_id not in by_id]
        if missing_ids:
            raise ValueError("camera is no longer connected: " + ", ".join(missing_ids))
        selected_ids = {left_id, right_id}
        known_devices = getattr(self.catalog, "known_devices", lambda: ())()
        for device in known_devices:
            if device.hardware_id in selected_ids or device.side not in {SIDE_LEFT, SIDE_RIGHT}:
                continue
            self.catalog.remember_device(
                device.hardware_id,
                getattr(device, "friendly_name", ""),
                model=getattr(device, "model", ""),
                side=SIDE_UNASSIGNED,
            )
        for hardware_id, side in ((left_id, SIDE_LEFT), (right_id, SIDE_RIGHT)):
            camera = by_id[hardware_id]
            self.catalog.remember_device(hardware_id, camera.friendly_name, side=side)
        self.catalog.save()
        self._reset_downstream_evidence()

    def _reset_downstream_evidence(self) -> None:
        """Invalidate every result that was measured for the previous camera pair."""
        self.assignment_generation += 1
        self.last_left_frames = []
        self.last_right_frames = []
        self.last_controls = {}
        self.last_modes = {}
        self.last_capability_observations = {}
        self.last_qualification = None
        self.last_sync = None
        self.last_focus = None
        self.last_overlap = None
        self.last_rectification = None
        self.last_capture_diagnostics = {}

    def assigned_ids(self) -> tuple[str, str]:
        snapshot = self.selection()
        left = [camera.hardware_id for camera in snapshot.cameras if camera.side == SIDE_LEFT]
        right = [camera.hardware_id for camera in snapshot.cameras if camera.side == SIDE_RIGHT]
        if len(left) != 1 or len(right) != 1 or left[0] == right[0]:
            raise RuntimeError("assign one distinct left and right camera first")
        return left[0], right[0]

    def build_capture_request(
        self,
        purpose: SetupCapturePurpose,
        *,
        frames: int | None = None,
        overall_deadline_ms: int = 45_000,
    ) -> SetupCaptureRequest:
        """Build a process-safe request bound to the current setup evidence."""
        default_frames = {
            SetupCapturePurpose.PREVIEW: 5,
            SetupCapturePurpose.SYNC: 60,
            SetupCapturePurpose.FOCUS: 3,
            SetupCapturePurpose.OVERLAP: 1,
            SetupCapturePurpose.RECTIFY: 1,
        }
        config_path = self.config_path.resolve()
        digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
        left_id, right_id = self.assigned_ids()
        return SetupCaptureRequest(
            correlation_id=f"setup_{purpose.value}_{uuid.uuid4().hex}",
            purpose=purpose,
            left_camera_id=left_id,
            right_camera_id=right_id,
            config_path=config_path,
            requested_frames_per_camera=frames or default_frames[purpose],
            overall_deadline_ms=overall_deadline_ms,
            backend=self.setup_capture_backend,
            config_sha256=digest,
            assignment_generation=self.assignment_generation,
        )

    @staticmethod
    def _frame_from_record(record: SetupFrameRecord) -> Frame:
        image = None
        if record.image_path is not None:
            import numpy as np

            image = np.load(record.image_path, allow_pickle=False)
        return Frame(
            camera_id=record.camera_id,
            frame_index=record.frame_index,
            t_capture_monotonic_ns=record.t_capture_monotonic_ns,
            image=image,
            width=record.width,
            height=record.height,
            pixfmt=record.pixfmt,
        )

    def apply_capture_result(self, result: SetupCaptureResult) -> object:
        """Validate and reduce a worker result on the UI-owning thread."""
        if result.assignment_generation != self.assignment_generation:
            raise RuntimeError("stale setup capture result for an earlier camera assignment")
        config_path = self.config_path.resolve()
        current_digest = hashlib.sha256(config_path.read_bytes()).hexdigest()
        if result.config_sha256 != current_digest:
            raise RuntimeError("stale setup capture result for an earlier configuration")
        left_frames = [self._frame_from_record(record) for record in result.left_frames]
        right_frames = [self._frame_from_record(record) for record in result.right_frames]
        if not left_frames or not right_frames:
            raise RuntimeError("setup capture did not return both camera streams")
        capability_observations: dict[str, CapabilityObservation] = {}
        for side, records in (("left", result.left_frames), ("right", result.right_frames)):
            if side not in result.capability_observations:
                continue
            observation = CapabilityObservation.from_payload(
                dict(result.capability_observations[side])
            )
            if observation.camera_id and observation.camera_id != records[0].camera_id:
                raise RuntimeError(f"{side} capability observation camera ID mismatch")
            capability_observations[side] = observation

        previous = (
            self.last_left_frames,
            self.last_right_frames,
            self.last_modes,
            self.last_controls,
            self.last_capability_observations,
            self.last_qualification,
            self.last_sync,
            self.last_focus,
            self.last_overlap,
            self.last_rectification,
            self.last_capture_diagnostics,
        )
        self.last_left_frames = left_frames
        self.last_right_frames = right_frames
        self.last_modes = {side: _normalize_mode(dict(mode)) for side, mode in result.modes.items()}
        self.last_controls = {side: dict(control) for side, control in result.controls.items()}
        self.last_capability_observations = capability_observations
        requested = result.requested_frames_per_camera
        self.last_capture_diagnostics = {
            "schema_version": result.schema_version,
            "correlation_id": result.correlation_id,
            "purpose": result.purpose.value,
            "duration_ms": (result.completed_monotonic_ns - result.started_monotonic_ns) / 1e6,
            "requested_frames_per_camera": requested,
            "received_frames": {
                "left": len(left_frames),
                "right": len(right_frames),
            },
            "read_error_count": dict(result.errors_by_side),
            "read_error_rate": {
                side: float(result.errors_by_side.get(side, 0)) / requested
                for side in ("left", "right")
            },
            "config_sha256": result.config_sha256,
            "assignment_generation": result.assignment_generation,
        }
        try:
            if result.purpose == SetupCapturePurpose.PREVIEW:
                return self._preview_from_frames(left_frames, right_frames)
            if result.purpose == SetupCapturePurpose.SYNC:
                return self._sync_from_frames(left_frames, right_frames)
            if result.purpose == SetupCapturePurpose.FOCUS:
                return self._focus_from_frames(left_frames, right_frames)
            if result.purpose == SetupCapturePurpose.OVERLAP:
                return self._overlap_from_frames(left_frames, right_frames)
            if result.purpose == SetupCapturePurpose.RECTIFY:
                return self._rectify_from_frames(left_frames, right_frames)
            raise RuntimeError(f"unsupported setup capture purpose: {result.purpose.value}")
        except Exception:
            (
                self.last_left_frames,
                self.last_right_frames,
                self.last_modes,
                self.last_controls,
                self.last_capability_observations,
                self.last_qualification,
                self.last_sync,
                self.last_focus,
                self.last_overlap,
                self.last_rectification,
                self.last_capture_diagnostics,
            ) = previous
            raise

    def capture(self, *, frames: int = 30) -> tuple[list[Frame], list[Frame]]:
        from configs.settings import load_config

        config = load_config(self.config_path)
        from app.pipeline.initialization import PipelineInitializer
        left_id, right_id = self.assigned_ids()
        left = self.camera_factory()
        right = self.camera_factory()
        left_frames: list[Frame] = []
        right_frames: list[Frame] = []
        try:
            left.open(left_id)
            right.open(right_id)
            PipelineInitializer.configure_camera(left, config, is_left=True)
            PipelineInitializer.configure_camera(right, config, is_left=False)
            self.last_modes = {
                "left": _normalize_mode(left.get_mode()),
                "right": _normalize_mode(right.get_mode()),
            }

            def _burst(camera: CameraDevice) -> list[Frame]:
                captured: list[Frame] = []
                for _ in range(max(1, frames)):
                    try:
                        captured.append(camera.read_frame(1000))
                    except CameraError:
                        continue
                return captured

            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="setup-capture") as executor:
                left_future = executor.submit(_burst, left)
                right_future = executor.submit(_burst, right)
                left_frames = left_future.result()
                right_frames = right_future.result()
            self.last_controls = {
                "left": left.get_controls() or {},
                "right": right.get_controls() or {},
            }
            self.last_capability_observations = {
                side: observation
                for side, camera in (("left", left), ("right", right))
                if (observation := camera.get_capability_observation()) is not None
            }
        finally:
            left.close()
            right.close()
        self.last_left_frames = left_frames
        self.last_right_frames = right_frames
        return left_frames, right_frames

    def preview(self) -> PairedPreviewSnapshot:
        try:
            left, right = self.capture(frames=5)
        except (CameraError, RuntimeError):
            return empty_preview_snapshot()
        return self._preview_from_frames(left, right)

    @staticmethod
    def _preview_from_frames(left: list[Frame], right: list[Frame]) -> PairedPreviewSnapshot:
        offsets = [abs(a.t_capture_monotonic_ns - b.t_capture_monotonic_ns) / 1e6 for a, b in zip(left, right)]
        max_offset = max(offsets, default=0.0)
        return PairedPreviewSnapshot(
            bool(left),
            bool(right),
            bool(offsets) and max_offset <= 5.0,
            left[-1].frame_index if left else -1,
            right[-1].frame_index if right else -1,
            max_offset,
            max(len(left), len(right)),
        )

    def sync(self) -> SyncCheckResult:
        left, right = self.capture(frames=60)
        return self._sync_from_frames(left, right)

    def _sync_from_frames(self, left: list[Frame], right: list[Frame]) -> SyncCheckResult:
        from calib.sync_check import check_sync
        from calib.capture_qualification import qualify_capture
        from app.monitoring.error_budget import ErrorBudget, MetricLimit
        from configs.settings import load_config

        config = load_config(self.config_path)
        self.last_sync = check_sync(
            [frame.t_capture_monotonic_ns for frame in left],
            [frame.t_capture_monotonic_ns for frame in right],
            config.stereo.pairing_tolerance_ms,
            max_speed_mph=float(config.metrics.velo_bounds_mph[1]),
        )
        requested_mode = {
            "width": config.camera.width,
            "height": config.camera.height,
            "fps": config.camera.fps,
            "pixfmt": _effective_pixfmt(config),
        }
        negotiated_mode = self.last_modes.get("left", {})
        modes_agree = negotiated_mode == self.last_modes.get("right", {})
        if not modes_agree:
            negotiated_mode = {"left": negotiated_mode, "right": self.last_modes.get("right", {})}
        tolerance = float(config.stereo.pairing_tolerance_ms)
        budget = ErrorBudget(
            "setup-capture-v1",
            "1",
            {
                "pair_skew_p95_ms": MetricLimit(tolerance * 0.5, tolerance, "ms"),
                "pair_skew_p99_ms": MetricLimit(tolerance * 0.75, tolerance * 1.5, "ms"),
                "frame_drop_rate": MetricLimit(0.01, 0.05, "ratio"),
                "unmatched_frame_rate": MetricLimit(0.01, 0.05, "ratio"),
                "mode_mismatch": MetricLimit(0.0, 0.0, "flag"),
                "controls_unverified": MetricLimit(0.0, 0.0, "flag"),
                "fps_shortfall_ratio_left": MetricLimit(0.05, 0.15, "ratio"),
                "fps_shortfall_ratio_right": MetricLimit(0.05, 0.15, "ratio"),
                "jitter_p95_ms_left": MetricLimit(1.0, 3.0, "ms"),
                "jitter_p95_ms_right": MetricLimit(1.0, 3.0, "ms"),
            },
        )
        pair_skews = [
            abs(a.t_capture_monotonic_ns - b.t_capture_monotonic_ns)
            for a, b in zip(left, right)
        ]
        controls_verified = modes_agree and all(
            bool(self.last_controls.get(side, {}).get("readback_verified")) for side in ("left", "right")
        )
        self.last_qualification = qualify_capture(
            [frame.t_capture_monotonic_ns for frame in left],
            [frame.t_capture_monotonic_ns for frame in right],
            pair_skews,
            requested_mode=requested_mode,
            negotiated_mode=negotiated_mode,
            expected_frames=60,
            controls_verified=controls_verified,
            budget=budget,
            qualification_id="setup-current",
        )
        return self.last_sync

    def focus(self) -> "FocusExposureSnapshot":
        left, right = self.capture(frames=3)
        return self._focus_from_frames(left, right)

    def _focus_from_frames(
        self,
        left: list[Frame],
        right: list[Frame],
    ) -> "FocusExposureSnapshot":
        from calib.stereo_setup.focus_lock import ExposureLockInput, ExposureValues, evaluate_exposure_lock, evaluate_focus_lock
        from configs.settings import load_config
        from ui.setup.focus_lock_view import FocusExposureSnapshot

        config = load_config(self.config_path)
        applied = ExposureValues(config.camera.exposure_us, config.camera.gain, float(config.camera.wb or 0))
        focus_results = []
        exposure_results = []
        for side, frame in (("left", left[-1]), ("right", right[-1])):
            if frame.image is None:
                raise RuntimeError(f"{side} focus capture is missing its image artifact")
            control = self.last_controls.get(side, {})
            focus_results.append(evaluate_focus_lock(
                side,
                frame.image,
                bool(control.get("autofocus_disabled", False)),
            ))
            readback = applied if control.get("readback_verified") else None
            exposure_results.append(evaluate_exposure_lock(
                side,
                ExposureLockInput(
                    applied,
                    readback,
                    bool(control.get("auto_exposure_disabled")),
                    bool(control.get("auto_white_balance_disabled")),
                ),
            ))
        self.last_focus = FocusExposureSnapshot(
            focus_left=focus_results[0],
            focus_right=focus_results[1],
            exposure_left=exposure_results[0],
            exposure_right=exposure_results[1],
        )
        return self.last_focus

    def overlap(self) -> StereoOverlapResult:
        left, right = self.capture(frames=1)
        return self._overlap_from_frames(left, right)

    def _overlap_from_frames(
        self,
        left: list[Frame],
        right: list[Frame],
    ) -> StereoOverlapResult:
        from calib.stereo_setup.overlap import validate_overlap

        if left[-1].image is None or right[-1].image is None:
            raise RuntimeError("overlap capture is missing an image artifact")
        self.last_overlap = validate_overlap(left[-1].image, right[-1].image)
        return self.last_overlap

    def rectify(self) -> CoarseRectificationResult:
        left, right = self.capture(frames=1)
        return self._rectify_from_frames(left, right)

    def _rectify_from_frames(
        self,
        left: list[Frame],
        right: list[Frame],
    ) -> CoarseRectificationResult:
        from calib.stereo_setup.rectify import coarse_rectify

        if left[-1].image is None or right[-1].image is None:
            raise RuntimeError("rectification capture is missing an image artifact")
        self.last_rectification = coarse_rectify(left[-1].image, right[-1].image)
        return self.last_rectification

    def quality_report(self) -> "CalibrationQualityReport":
        from ui.setup.providers.profile import build_quality_report_for_context
        return build_quality_report_for_context(self)

    def persist_profile(self, stereo_profile: "StereoCalibrationProfile") -> str:
        from ui.setup.providers.profile import persist_profile_for_context
        return persist_profile_for_context(self, stereo_profile)
