"""Real-backend adapter providers for the canonical stereo setup workflow.

These convert live hardware backends into the Qt-free snapshot dataclasses that
the camera-select and paired-preview step widgets render. They are injected into
the widgets by the live wizard; the registry's test-safe defaults in
:mod:`ui.setup.stereo_steps` stay empty so the synthetic step tests never touch
hardware.

Every adapter takes its hardware dependency as an injected parameter so the
logic is unit-testable with fakes and the :class:`SimulatedCamera` backend.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from dataclasses import replace
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
from itertools import combinations
from pathlib import Path
import math
import shutil
import uuid
from typing import TYPE_CHECKING, Any, Callable, Dict, Iterable, List, Optional, Sequence

from capture.camera_device import CameraDevice
from capture.device_discovery import list_uvc_devices
from capture.simulated_camera import SimulatedCamera
from capture.uvc_backend import UvcCamera
from contracts.catalog import SIDE_UNASSIGNED
from contracts.catalog import SIDE_LEFT, SIDE_RIGHT
from contracts.quality import QUALITY_DEGRADED
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureRequest, SetupCaptureResult, SetupFrameRecord
from contracts.types import Frame
from exceptions import CameraError
from ui.setup.camera_select_view import CameraSelectionSnapshot, DiscoveredCamera
from ui.setup.paired_preview_view import PairedPreviewSnapshot, empty_preview_snapshot

if TYPE_CHECKING:
    from ui.setup.state_machine import SetupStep
    from ui.setup.steps.base_step import BaseStep

DeviceLister = Callable[[], Sequence[Dict[str, Any]]]
PreviewProvider = Callable[[], PairedPreviewSnapshot]


def _new_profile_id() -> str:
    return (
        "rig_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "_"
        + uuid.uuid4().hex[:12]
    )


def _effective_pixfmt(config) -> str:
    pixfmt = config.camera.pixfmt
    return "YUYV" if config.camera.color_mode and pixfmt == "GRAY8" else pixfmt


def _normalize_mode(mode: Optional[dict]) -> dict:
    normalized = dict(mode or {})
    if str(normalized.get("pixfmt") or "").upper() == "YUY2":
        normalized["pixfmt"] = "YUYV"
    if "fps" in normalized:
        normalized["fps"] = float(normalized["fps"])
    return normalized


@dataclass
class LiveSetupContext:
    """Shared hardware context carried through the canonical setup workflow."""

    catalog: Optional[object]
    list_devices: DeviceLister = list_uvc_devices
    camera_factory: Callable[[], CameraDevice] = UvcCamera
    config_path: Path = Path("configs/default.yaml")
    last_left_frames: list[Frame] = field(default_factory=list)
    last_right_frames: list[Frame] = field(default_factory=list)
    last_controls: dict[str, dict] = field(default_factory=dict)
    last_modes: dict[str, dict] = field(default_factory=dict)
    last_qualification: object = None
    last_sync: object = None
    last_focus: object = None
    last_overlap: object = None
    last_rectification: object = None
    last_capture_diagnostics: dict = field(default_factory=dict)
    setup_capture_backend: str = "uvc"
    assignment_generation: int = 0
    rig_profile_dir: Path = Path("calibration/rigs")
    validated_camera_pairs_provider: Optional[Callable[[], Iterable[dict[str, Any]]]] = None

    def selection(self) -> CameraSelectionSnapshot:
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

    def apply_capture_result(self, result: SetupCaptureResult):
        """Validate and reduce a worker result on the UI-owning thread.

        No shared setup evidence is mutated until correlation-independent
        assignment/config checks and local artifact loading have succeeded.
        """
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

        previous = (
            self.last_left_frames,
            self.last_right_frames,
            self.last_modes,
            self.last_controls,
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

            # Read both cameras concurrently so achieved FPS and host-receive
            # skew are not artifacts of a serial setup loop.
            with ThreadPoolExecutor(max_workers=2, thread_name_prefix="setup-capture") as executor:
                left_future = executor.submit(_burst, left)
                right_future = executor.submit(_burst, right)
                left_frames = left_future.result()
                right_frames = right_future.result()
            self.last_controls = {
                "left": left.get_controls() or {},
                "right": right.get_controls() or {},
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

    def sync(self):
        left, right = self.capture(frames=60)
        return self._sync_from_frames(left, right)

    def _sync_from_frames(self, left: list[Frame], right: list[Frame]):
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

    def focus(self):
        left, right = self.capture(frames=3)
        return self._focus_from_frames(left, right)

    def _focus_from_frames(self, left: list[Frame], right: list[Frame]):
        from calib.stereo_setup.focus_lock import ExposureLockInput, ExposureValues, evaluate_exposure_lock, evaluate_focus_lock
        from configs.settings import load_config
        from ui.setup.focus_lock_view import FocusExposureSnapshot

        config = load_config(self.config_path)
        applied = ExposureValues(config.camera.exposure_us, config.camera.gain, float(config.camera.wb or 0))
        results = {}
        for side, frame in (("left", left[-1]), ("right", right[-1])):
            if frame.image is None:
                raise RuntimeError(f"{side} focus capture is missing its image artifact")
            control = self.last_controls.get(side, {})
            results[f"focus_{side}"] = evaluate_focus_lock(
                side,
                frame.image,
                bool(control.get("autofocus_disabled", False)),
            )
            readback = applied if control.get("readback_verified") else None
            results[f"exposure_{side}"] = evaluate_exposure_lock(
                side,
                ExposureLockInput(
                    applied,
                    readback,
                    bool(control.get("auto_exposure_disabled")),
                    bool(control.get("auto_white_balance_disabled")),
                ),
            )
        self.last_focus = FocusExposureSnapshot(**results)
        return self.last_focus

    def overlap(self):
        left, right = self.capture(frames=1)
        return self._overlap_from_frames(left, right)

    def _overlap_from_frames(self, left: list[Frame], right: list[Frame]):
        from calib.stereo_setup.overlap import validate_overlap

        if left[-1].image is None or right[-1].image is None:
            raise RuntimeError("overlap capture is missing an image artifact")
        self.last_overlap = validate_overlap(left[-1].image, right[-1].image)
        return self.last_overlap

    def rectify(self):
        left, right = self.capture(frames=1)
        return self._rectify_from_frames(left, right)

    def _rectify_from_frames(self, left: list[Frame], right: list[Frame]):
        from calib.stereo_setup.rectify import coarse_rectify

        if left[-1].image is None or right[-1].image is None:
            raise RuntimeError("rectification capture is missing an image artifact")
        self.last_rectification = coarse_rectify(left[-1].image, right[-1].image)
        return self.last_rectification

    def quality_report(self):
        from calib.stereo_setup.quality_report import build_quality_report
        from ui.setup.persist_profile_view import build_stereo_profile_from_report

        stereo = build_stereo_profile_from_report(Path("calibration"))
        if stereo is None:
            from ui.setup.quality_report_view import load_calibration_quality_report
            return load_calibration_quality_report(Path("calibration"))
        focus_locks = []
        exposure_locks = []
        if self.last_focus is not None:
            focus_locks = [self.last_focus.focus_left, self.last_focus.focus_right]
            exposure_locks = [self.last_focus.exposure_left, self.last_focus.exposure_right]
        report = build_quality_report(
            rms_reprojection_px=stereo.rms_reprojection_px,
            epipolar_error_px=(self.last_rectification.epipolar_error_after_px if self.last_rectification else stereo.epipolar_error_px),
            baseline_in=stereo.baseline_in,
            sync=self.last_sync,
            overlap=self.last_overlap,
            rectification=self.last_rectification,
            focus_locks=focus_locks,
            exposure_locks=exposure_locks,
            require_steps=True,
        )
        if self.last_qualification is not None:
            assessment = self.last_qualification.assessment
        else:
            assessment = None
        if assessment is not None and (
            assessment.status == QUALITY_DEGRADED or not assessment.permits_measurement
        ):
            from contracts.setup import QUALITY_GRADE_FAIL
            qualification_label = "degraded" if assessment.status == QUALITY_DEGRADED else "failed"
            reasons = ", ".join(assessment.reason_codes) or assessment.status
            report = replace(
                report,
                grade=QUALITY_GRADE_FAIL,
                passed=False,
                warnings=[
                    *report.warnings,
                    f"Capture qualification {qualification_label}: {reasons}",
                ],
            )
        return report

    def persist_profile(self, stereo_profile) -> str:
        from app.services.rig_profile import RigProfileService
        from app.services.rig_profile_models import PASS, WARN, RigProfile
        from configs.settings import load_config
        from ui.setup.field_alignment_view import load_or_estimate_field_alignment

        field_alignment = load_or_estimate_field_alignment(Path("calibration"))
        if not field_alignment.passed or field_alignment.transform is None:
            raise RuntimeError(field_alignment.recommendation)
        report = self.quality_report()
        if not report.passed:
            raise RuntimeError("Live setup checks have not all passed; profile was not activated.")
        config = load_config(self.config_path)
        authoritative_wb = config.camera.wb
        authoritative_wb_source = "configured" if authoritative_wb is not None else "not_applicable"
        resolved_wb_by_camera: dict[str, float] = {}
        if config.camera.color_mode and authoritative_wb is None:
            for side in ("left", "right"):
                controls = self.last_controls.get(side, {})
                value = controls.get("resolved_wb")
                source = controls.get("wb_source")
                try:
                    numeric_value = float(value)
                except (TypeError, ValueError):
                    numeric_value = 0.0
                if (
                    not controls.get("readback_verified")
                    or source != "auto_sampled_then_locked"
                    or not math.isfinite(numeric_value)
                    or numeric_value <= 0
                ):
                    raise RuntimeError(
                        f"{side.capitalize()} camera did not provide a verified auto-sampled white balance."
                    )
                resolved_wb_by_camera[side] = numeric_value
            left_wb = resolved_wb_by_camera["left"]
            right_wb = resolved_wb_by_camera["right"]
            if abs(left_wb - right_wb) / max(abs(left_wb), 1.0) > 0.1:
                raise RuntimeError(
                    "Camera white-balance samples differ by more than 10%; set and verify an explicit shared value."
                )
            # AppConfig currently has one authoritative WB value for both cameras.
            # Reuse an observed, verified value rather than inventing a default.
            authoritative_wb = int(round(left_wb))
            authoritative_wb_source = "auto_sampled_then_locked"
        if self.last_rectification is not None:
            stereo_profile = replace(
                stereo_profile,
                epipolar_error_px=float(self.last_rectification.epipolar_error_after_px),
            )
        left_id, right_id = self.assigned_ids()
        selection = {camera.hardware_id: camera for camera in self.selection().cameras}
        missing_ids = [camera_id for camera_id in (left_id, right_id) if camera_id not in selection]
        if missing_ids:
            raise RuntimeError("Assigned camera is no longer connected: " + ", ".join(missing_ids))
        profile_id = _new_profile_id()
        service = RigProfileService(base_dir=self.rig_profile_dir, config_path=self.config_path)
        profile_dir = service.profile_dir(profile_id)
        profile_dir.mkdir(parents=True, exist_ok=True)
        calibration_source = Path("calibration") / stereo_profile.calibration_file
        if not calibration_source.exists():
            raise RuntimeError(f"Calibration artifact missing: {calibration_source}")
        shutil.copy2(calibration_source, profile_dir / "stereo_calibration.npz")
        roi_source = next((path for path in (Path("rois/shared_rois.json"), Path("configs/roi.json")) if path.exists()), None)
        if roi_source is None:
            raise RuntimeError("ROI artifact missing; configure lane and plate ROIs before persistence.")
        shutil.copy2(roi_source, profile_dir / "roi.json")
        profile = RigProfile.from_config(
            profile_id,
            config,
            backend="uvc",
            left_serial=left_id,
            right_serial=right_id,
            quality_metrics={
                **report.to_payload(),
                "capture_qualification": None
                if self.last_qualification is None
                else {
                    **self.last_qualification.__dict__,
                    "assessment": self.last_qualification.assessment.to_payload(),
                },
            },
            diagnostics={"setup_source": "canonical_live_wizard"},
        )
        profile = replace(
            profile,
            stereo_profile=stereo_profile,
            field_transform={
                **field_alignment.transform.to_payload(),
                "fixture_source_sha256": field_alignment.fixture_source_sha256,
                "fixture_point_count": field_alignment.fixture_point_count,
            },
            hardware_fingerprint={
                "backend": "uvc",
                "left_serial": left_id,
                "right_serial": right_id,
                "left_friendly_name": selection[left_id].friendly_name,
                "right_friendly_name": selection[right_id].friendly_name,
            },
            camera_mode={
                **profile.camera_mode,
                **self.last_modes.get("left", {}),
            },
            approved_modes=[
                {
                    **profile.camera_mode,
                    **self.last_modes.get("left", {}),
                }
            ],
            control_settings={
                **profile.control_settings,
                "wb": authoritative_wb,
                "wb_source": authoritative_wb_source,
                "resolved_wb_by_camera": resolved_wb_by_camera,
                "readback": dict(self.last_controls),
            },
            runtime_validation_status=(
                WARN
                if self.last_qualification is not None
                and self.last_qualification.assessment.status == QUALITY_DEGRADED
                else PASS
            ),
            error_budget={
                "budget_id": "field-pilot-v1",
                "version": "1",
                "limits": {
                    "pair_skew_p95_ms": {"warn": 0.5, "reject": 1.0, "units": "ms"},
                    "recording_drop_rate": {"warn": 0.01, "reject": 0.05, "units": "ratio"},
                    "analysis_drop_rate": {"warn": 0.0, "reject": 0.01, "units": "ratio"},
                    "tracklet_start_rate": {"warn": 0.5, "reject": 0.8, "units": "ratio"},
                    "pair_skew_rejection_rate": {"warn": 0.01, "reject": 0.05, "units": "ratio"},
                    "association_rejection_rate": {"warn": 0.2, "reject": 0.5, "units": "ratio"},
                },
            },
        )
        from app.services.setup_snapshot import assemble_setup_snapshot

        setup_snapshot = assemble_setup_snapshot(
            profile=profile,
            config=config,
            config_path=self.config_path,
            cameras=selection.values(),
            capture_qualification=self.last_qualification,
            capture_diagnostics={
                **self.last_capture_diagnostics,
                "modes": dict(self.last_modes),
                "sync": _setup_payload(self.last_sync),
                "focus": _setup_payload(self.last_focus),
                "overlap": _setup_payload(self.last_overlap),
                "rectification": _setup_payload(self.last_rectification),
            },
            calibration_path=profile_dir / "stereo_calibration.npz",
            roi_path=profile_dir / "roi.json",
        )
        profile = replace(
            profile,
            setup_snapshot=setup_snapshot.to_payload(),
            diagnostics={
                **profile.diagnostics,
                "setup_snapshot_fingerprint": setup_snapshot.fingerprint_sha256,
                "setup_snapshot_configuration_evidence_complete": (
                    setup_snapshot.assessment.configuration_evidence_complete
                ),
                "setup_snapshot_blockers": list(setup_snapshot.assessment.blockers),
            },
        )
        saved = service.save(profile, activate=True)
        return saved.profile_id


def discover_camera_selection(
    *,
    list_devices: DeviceLister = list_uvc_devices,
    catalog: Optional[object] = None,
    requested_mode: Optional[tuple[int, int, int]] = None,
    validated_pairs: Iterable[dict[str, Any]] = (),
) -> CameraSelectionSnapshot:
    """Adapt live UVC discovery + the camera catalog into a selection snapshot.

    Args:
        list_devices: Callable returning device dicts (keys ``serial`` /
            ``instance_id`` / ``friendly_name``). Injectable for tests.
        catalog: Optional ``CameraCatalogService``-like object exposing
            ``known_devices()`` (for carry-over side assignment) and
            ``match_model(friendly_name)`` (for recognition).

    Returns:
        A :class:`CameraSelectionSnapshot` reflecting the discovered cameras.
    """
    devices = list_devices() or []
    sides = _known_sides(catalog)
    recognize = getattr(catalog, "match_model", None) if catalog is not None else None

    cameras: List[DiscoveredCamera] = []
    for entry in devices:
        hardware_id = str(entry.get("serial") or entry.get("instance_id") or "")
        friendly = str(entry.get("friendly_name") or "")
        matched_model = recognize(friendly) if recognize is not None else None
        recognized = matched_model is not None
        capabilities = getattr(matched_model, "capabilities", None)
        global_shutter = bool(
            getattr(matched_model, "global_shutter", False)
            or getattr(capabilities, "global_shutter", False)
        )
        modes = tuple(
            (int(mode.width), int(mode.height), int(mode.fps))
            for mode in (getattr(capabilities, "supported_modes", ()) or ())
        )
        controls = tuple(str(item) for item in (getattr(capabilities, "controls", ()) or ()))
        cameras.append(
            DiscoveredCamera(
                hardware_id=hardware_id,
                friendly_name=friendly,
                side=sides.get(hardware_id, SIDE_UNASSIGNED),
                recognized=recognized,
                global_shutter=global_shutter,
                model=str(getattr(matched_model, "model", "") or ""),
                supported_modes=modes,
                controls=controls,
                sync_capable=getattr(capabilities, "sync_capable", None),
                instance_id=_optional_device_value(entry, "instance_id"),
                device_path=_optional_device_value(entry, "device_path", "path", "pnp_device_id"),
                usb_controller=_optional_device_value(entry, "usb_controller", "controller"),
                driver_version=_optional_device_value(entry, "driver_version"),
                firmware_version=_optional_device_value(entry, "firmware_version"),
                capability_score=_camera_capability_score(
                    recognized=recognized,
                    global_shutter=global_shutter,
                    sync_capable=getattr(capabilities, "sync_capable", None),
                    supported_modes=modes,
                    controls=controls,
                    requested_mode=requested_mode,
                ),
            )
        )
    return _apply_camera_recommendation(cameras, requested_mode, tuple(validated_pairs))


def _apply_camera_recommendation(
    cameras: list[DiscoveredCamera],
    requested_mode: Optional[tuple[int, int, int]],
    validated_pairs: tuple[dict[str, Any], ...],
) -> CameraSelectionSnapshot:
    by_id = {camera.hardware_id: camera for camera in cameras}
    for pair in validated_pairs:
        left_id = str(pair.get("left_id") or "")
        right_id = str(pair.get("right_id") or "")
        if left_id in by_id and right_id in by_id and left_id != right_id:
            profile_id = str(pair.get("profile_id") or "")
            reason = (
                f"Exact camera pair from previously validated profile {profile_id}; "
                "runtime will re-verify the approval and artifact bindings."
            )
            return _recommended_snapshot(
                cameras,
                left_id,
                right_id,
                source="previously_validated_profile",
                reason=reason,
                validated_profile_id=profile_id,
            )

    eligible = [camera for camera in cameras if camera.recognized and camera.global_shutter]
    if len(eligible) < 2:
        if len(cameras) < 2:
            return CameraSelectionSnapshot(
                cameras=tuple(cameras),
                recommendation_source="unavailable",
                recommendation_reason="Fewer than two cameras are available.",
            )
        return _best_camera_pair_snapshot(
            cameras,
            cameras,
            requested_mode,
            source="diagnostic_fallback",
            reason=(
                "No pair of two recognized global-shutter cameras is available. "
                "This fallback pair may be used for diagnostic setup only; "
                "production measurement remains blocked."
            ),
        )

    return _best_camera_pair_snapshot(
        cameras,
        eligible,
        requested_mode,
        source="capability_score",
        reason_prefix="Best compatible recognized global-shutter pair",
    )


def _best_camera_pair_snapshot(
    cameras: list[DiscoveredCamera],
    eligible: list[DiscoveredCamera],
    requested_mode: Optional[tuple[int, int, int]],
    *,
    source: str,
    reason: str = "",
    reason_prefix: str = "",
) -> CameraSelectionSnapshot:
    pair_candidates = []
    for first, second in combinations(eligible, 2):
        score = _camera_pair_score(first, second, requested_mode)
        tie_key = tuple(sorted((first.hardware_id, second.hardware_id)))
        pair_candidates.append((score, tie_key, first, second))
    best_score = max(item[0] for item in pair_candidates)
    _, _, first, second = min(
        (item for item in pair_candidates if item[0] == best_score),
        key=lambda item: item[1],
    )
    left, right = _recommended_sides(first, second)
    requested_text = (
        f"{requested_mode[0]}x{requested_mode[1]}@{requested_mode[2]}"
        if requested_mode is not None
        else "the requested mode"
    )
    if not reason:
        reason = (
            f"{reason_prefix} for {requested_text}; ranking considers requested-mode "
            "support, synchronization, common modes, controls, and throughput."
        )
    return _recommended_snapshot(
        cameras,
        left.hardware_id,
        right.hardware_id,
        source=source,
        reason=reason,
    )


def _recommended_snapshot(
    cameras: list[DiscoveredCamera],
    left_id: str,
    right_id: str,
    *,
    source: str,
    reason: str,
    validated_profile_id: str = "",
) -> CameraSelectionSnapshot:
    updated = []
    for camera in cameras:
        recommended_side = (
            SIDE_LEFT if camera.hardware_id == left_id else SIDE_RIGHT if camera.hardware_id == right_id else SIDE_UNASSIGNED
        )
        updated.append(
            replace(
                camera,
                recommended_side=recommended_side,
                recommendation_reason=reason if recommended_side != SIDE_UNASSIGNED else "",
                previously_validated=bool(validated_profile_id and recommended_side != SIDE_UNASSIGNED),
                validated_profile_id=validated_profile_id if recommended_side != SIDE_UNASSIGNED else "",
            )
        )
    return CameraSelectionSnapshot(
        cameras=tuple(updated),
        recommended_left_id=left_id,
        recommended_right_id=right_id,
        recommendation_source=source,
        recommendation_reason=reason,
    )


def _recommended_sides(first: DiscoveredCamera, second: DiscoveredCamera) -> tuple[DiscoveredCamera, DiscoveredCamera]:
    if first.side == SIDE_LEFT or second.side == SIDE_RIGHT:
        return first, second
    if second.side == SIDE_LEFT or first.side == SIDE_RIGHT:
        return second, first
    ordered = sorted((first, second), key=lambda camera: camera.hardware_id)
    return ordered[0], ordered[1]


def _camera_pair_score(
    first: DiscoveredCamera,
    second: DiscoveredCamera,
    requested_mode: Optional[tuple[int, int, int]],
) -> tuple[int, int, int, int, int, int]:
    first_modes = set(first.supported_modes)
    second_modes = set(second.supported_modes)
    common_modes = first_modes & second_modes
    requested_supported = int(requested_mode is not None and requested_mode in common_modes)
    both_sync = int(first.sync_capable is True and second.sync_capable is True)
    common_throughput = max((width * height * fps for width, height, fps in common_modes), default=0)
    common_controls = len(set(first.controls) & set(second.controls))
    same_model = int(bool(first.model) and first.model == second.model)
    return (
        requested_supported,
        both_sync,
        common_throughput,
        min(first.capability_score, second.capability_score),
        common_controls,
        same_model,
    )


def _camera_capability_score(
    *,
    recognized: bool,
    global_shutter: bool,
    sync_capable: Optional[bool],
    supported_modes: tuple[tuple[int, int, int], ...],
    controls: tuple[str, ...],
    requested_mode: Optional[tuple[int, int, int]],
) -> int:
    throughput = max((width * height * fps for width, height, fps in supported_modes), default=0)
    return (
        int(recognized) * 10**12
        + int(global_shutter) * 10**11
        + int(requested_mode is not None and requested_mode in supported_modes) * 10**10
        + int(sync_capable is True) * 10**9
        + len(set(controls) & {"exposure", "gain", "white_balance", "focus"}) * 10**7
        + throughput
    )


def _optional_device_value(entry: dict[str, Any], *names: str) -> Optional[str]:
    for name in names:
        value = entry.get(name)
        if value not in {None, ""}:
            return str(value)
    return None


def _setup_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return value.to_payload()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return value


def _known_sides(catalog: Optional[object]) -> Dict[str, str]:
    if catalog is None:
        return {}
    known = getattr(catalog, "known_devices", None)
    if known is None:
        return {}
    return {device.hardware_id: device.side for device in known()}


def capture_paired_preview(
    left: CameraDevice,
    right: CameraDevice,
    *,
    frames: int = 5,
    tolerance_ms: float = 5.0,
    timeout_ms: int = 1000,
    width: int = 64,
    height: int = 48,
    fps: int = 0,
    pixfmt: str = "GRAY8",
) -> PairedPreviewSnapshot:
    """Grab a short burst from a left/right camera pair and grade the pairing.

    Works with any :class:`CameraDevice` (real or :class:`SimulatedCamera`); the
    cameras must already be opened. A per-side read failure is recorded honestly
    rather than raised, so a single dead camera produces a failing snapshot.

    Returns:
        A :class:`PairedPreviewSnapshot` summarising stream health and offset.
    """
    left.set_mode(width, height, fps, pixfmt)
    right.set_mode(width, height, fps, pixfmt)

    left_ok = False
    right_ok = False
    last_left = -1
    last_right = -1
    observed = 0
    paired_count = 0
    max_offset_ms = 0.0

    for _ in range(max(1, frames)):
        left_frame = _read_side(left, timeout_ms)
        right_frame = _read_side(right, timeout_ms)
        if left_frame is not None:
            left_ok = True
            last_left = left_frame.frame_index
        if right_frame is not None:
            right_ok = True
            last_right = right_frame.frame_index
        if left_frame is not None or right_frame is not None:
            observed += 1
        if left_frame is not None and right_frame is not None:
            paired_count += 1
            offset_ms = abs(left_frame.t_capture_monotonic_ns - right_frame.t_capture_monotonic_ns) / 1e6
            max_offset_ms = max(max_offset_ms, offset_ms)

    return PairedPreviewSnapshot(
        left_ok=left_ok,
        right_ok=right_ok,
        paired_within_tolerance=paired_count > 0 and max_offset_ms <= tolerance_ms,
        left_frame_index=last_left,
        right_frame_index=last_right,
        pair_offset_ms=max_offset_ms,
        frames_observed=observed,
    )


def _read_side(camera: CameraDevice, timeout_ms: int) -> Optional[Frame]:
    try:
        return camera.read_frame(timeout_ms)
    except CameraError:
        return None


def simulated_paired_preview(
    *,
    frames: int = 5,
    tolerance_ms: float = 50.0,
) -> PairedPreviewSnapshot:
    """Convenience preview provider backed by two :class:`SimulatedCamera`.

    Useful for demos and self-tests on machines without stereo hardware. The
    default tolerance is generous because simulated capture is not time-locked.
    """
    left = SimulatedCamera()
    right = SimulatedCamera()
    left.open("sim-left")
    right.open("sim-right")
    try:
        return capture_paired_preview(left, right, frames=frames, tolerance_ms=tolerance_ms)
    finally:
        left.close()
        right.close()


def make_camera_preview_provider(
    left_serial: str,
    right_serial: str,
    *,
    camera_factory: Callable[[], CameraDevice] = UvcCamera,
    frames: int = 5,
    tolerance_ms: float = 8.0,
) -> PreviewProvider:
    """Create a paired-preview provider backed by the selected camera serials."""

    def _provider() -> PairedPreviewSnapshot:
        left = camera_factory()
        right = camera_factory()
        try:
            left.open(left_serial)
            right.open(right_serial)
            return capture_paired_preview(left, right, frames=frames, tolerance_ms=tolerance_ms)
        except CameraError:
            return empty_preview_snapshot()
        finally:
            left.close()
            right.close()

    return _provider


def build_live_stereo_step_widgets(
    *,
    catalog: Optional[object] = None,
    list_devices: DeviceLister = list_uvc_devices,
    preview_provider: Optional[PreviewProvider] = None,
    setup_capture_service=None,
    setup_capture_backend: str = "uvc",
) -> "Dict[SetupStep, BaseStep]":
    """Build the canonical registry with a shared live hardware context.

    Step 1 uses live UVC discovery. Subsequent capture-quality steps reuse the
    assignments through :class:`LiveSetupContext`; ``preview_provider`` may be
    supplied for deterministic tests.

    Args:
        catalog: Optional camera-catalog service for recognition / carry-over.
        list_devices: Device lister for step-1 discovery (injectable for tests).
        preview_provider: Optional callable yielding a paired-preview snapshot
            from live cameras. ``None`` leaves the step's empty default.

    Returns:
        A mapping with an entry for every canonical :class:`SetupStep`.
    """
    from ui.setup.stereo_steps import build_stereo_step_widgets
    from ui.setup.state_machine import SetupStep
    from ui.setup.steps import CameraSelectStep, PairedPreviewStep
    from ui.setup.steps import FocusLockStep, OverlapStep, PersistProfileStep, QualityReportStep, RectifyStep, SyncCheckStep
    from ui.setup.persist_profile_view import build_stereo_profile_from_report
    from app.services.capture.setup_capture import SupervisedSetupCaptureService
    from ui.setup.setup_capture_controller import SetupCaptureOperation

    widgets = build_stereo_step_widgets()
    context = LiveSetupContext(
        catalog=catalog,
        list_devices=list_devices,
        setup_capture_backend=setup_capture_backend,
    )
    capture_service = setup_capture_service or SupervisedSetupCaptureService()

    def _operation(purpose: SetupCapturePurpose) -> SetupCaptureOperation:
        return SetupCaptureOperation(
            capture_service,
            lambda purpose=purpose: context.build_capture_request(purpose),
            context.apply_capture_result,
        )

    widgets[SetupStep.SELECT_CAMERAS] = CameraSelectStep(
        snapshot_provider=context.selection,
        assignment_callback=context.assign if catalog is not None else None,
    )
    widgets[SetupStep.PAIRED_PREVIEW] = PairedPreviewStep(
        snapshot_provider=preview_provider or context.preview,
        operation=None if preview_provider is not None else _operation(SetupCapturePurpose.PREVIEW),
    )
    widgets[SetupStep.SYNC_CHECK] = SyncCheckStep(
        result_provider=context.sync,
        operation=_operation(SetupCapturePurpose.SYNC),
    )
    widgets[SetupStep.FOCUS_EXPOSURE_LOCK] = FocusLockStep(
        snapshot_provider=context.focus,
        operation=_operation(SetupCapturePurpose.FOCUS),
    )
    widgets[SetupStep.OVERLAP_VALIDATION] = OverlapStep(
        result_provider=context.overlap,
        operation=_operation(SetupCapturePurpose.OVERLAP),
    )
    widgets[SetupStep.COARSE_RECTIFY] = RectifyStep(
        result_provider=context.rectify,
        operation=_operation(SetupCapturePurpose.RECTIFY),
    )
    widgets[SetupStep.PERSIST_PROFILE] = PersistProfileStep(
        profile_provider=lambda: build_stereo_profile_from_report(Path("calibration")),
        persist_callback=context.persist_profile,
    )
    widgets[SetupStep.QUALITY_REPORT] = QualityReportStep(report_provider=context.quality_report)
    for widget in widgets.values():
        setattr(widget, "_live_setup_context", context)
    return widgets


__all__ = [
    "DeviceLister",
    "PreviewProvider",
    "LiveSetupContext",
    "build_live_stereo_step_widgets",
    "capture_paired_preview",
    "discover_camera_selection",
    "make_camera_preview_provider",
    "simulated_paired_preview",
]
