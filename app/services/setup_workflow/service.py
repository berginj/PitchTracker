"""One owner for saved configuration, setup generations, and readiness."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

import yaml

from app.services.rig_profile import RigProfileService
from app.services.setup_workflow.storage import CHECK_NAMES, configuration_file, contained, save_state
from configs.settings import AppConfig, load_config
from contracts.setup_workflow import SetupCheck, SetupReadiness
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureRequest, SetupCaptureResult
from contracts.versioning import APP_VERSION
from exceptions import ConfigError


class SetupWorkflowService:
    """Working revisions save immediately; completed profiles remain immutable."""

    def __init__(
        self, config_path: Path = Path("configs/default.yaml"),
        base_dir: Path = Path("calibration/rigs"), *, profile_id: str | None = None, backend: str = "uvc",
        use_active: bool = True,
    ):
        self.rigs = RigProfileService(base_dir=base_dir, config_path=config_path)
        profile = self.rigs.load(profile_id) if profile_id else (self.rigs.load_active() if use_active else None)
        if backend == "sim" and profile and profile.backend != "sim" and not profile_id:
            profile = None
        new_id = "new-sim" if backend == "sim" else "new"
        self.root = (base_dir.parent / "setups" / (profile.profile_id if profile else new_id)).resolve()
        if not self.root.is_relative_to((base_dir.parent / "setups").resolve()):
            raise ValueError("Setup profile identity escapes the intended workspace")
        self._lock = RLock()
        self.images: dict[str, Any] = {}
        self.image_metadata: dict[str, Any] = {}
        self.visit_checks: set[str] = set()
        self.unsaved_error = ""
        path = self.root / "state.json"
        if path.exists():
            self._state = json.loads(path.read_text(encoding="utf-8"))
            if self._state.get("schema_version") != "rig_setup_state.v1":
                raise ValueError("Unsupported saved setup state")
            load_config(self.config_path)
        else:
            source = self.rigs.effective_config_path(profile) if profile else config_path
            payload = yaml.safe_load(source.read_text(encoding="utf-8"))
            if profile:
                config = self.rigs.apply_profile_to_config(load_config(source), profile, preserve_camera_mode=False)
                from dataclasses import asdict
                payload["camera"] = asdict(config.camera)
            payload.setdefault("upload", {})["api_key"] = ""
            cfg = configuration_file(self.root, payload)
            self._state = {
                "schema_version": "rig_setup_state.v1", "setup_id": uuid4().hex,
                "app_version": APP_VERSION, "created_utc": datetime.now(timezone.utc).isoformat(),
                "base_profile_id": profile.profile_id if profile else None,
                "generation": 0, "changed": False, "backend": profile.backend if profile else backend,
                "optics_revision": profile.diagnostics.get("optics_revision", 0) if profile else 0,
                "config_file": cfg.name, "camera_ids": dict(profile.camera_serials) if profile else {},
                "board": dict(profile.board_metadata) if profile and profile.board_metadata else {
                    "pattern": "9x6", "square_mm": 30.0,
                },
                "artifacts": {}, "checks": {}, "targets": [], "captures": [], "regions": {},
            }
            if profile:
                calibration = self.rigs.calibration_path(profile)
                if calibration.is_file():
                    self._state["artifacts"]["calibration"] = self._copy_file(calibration)
                roi_path = self.rigs.roi_path(profile)
                if roi_path.is_file():
                    self._state["regions"] = json.loads(roi_path.read_text(encoding="utf-8"))
                self._state["field_transform"] = deepcopy(profile.field_transform)
                self._state["targets"] = deepcopy(profile.field_transform.get("targets", []))
                for target in self._state["targets"]:
                    for side in ("left", "right"):
                        filename = target.get("source_pair", {}).get(side, {}).get("file")
                        if filename:
                            source_image = self.rigs.profile_dir(profile.profile_id) / filename
                            if source_image.is_file():
                                self._copy_file(source_image)
                identity_path = self.rigs.calibration_path(profile).with_suffix(".identity.json")
                self._state["calibration_identity"] = (
                    json.loads(identity_path.read_text(encoding="utf-8")) if identity_path.is_file() else None
                )
            save_state(self.root, self._state)

    @property
    def state(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._state)

    @property
    def generation(self) -> int:
        return int(self._state["generation"])

    @property
    def config_path(self) -> Path:
        return contained(self.root, self._state["config_file"])

    @property
    def config(self) -> AppConfig:
        return load_config(self.config_path)

    def artifact(self, name: str) -> Path:
        filename = self._state["artifacts"].get(name)
        if not filename:
            raise ValueError(f"{name.capitalize()} is missing")
        path = contained(self.root, filename)
        if hashlib.sha256(path.read_bytes()).hexdigest() != path.stem:
            raise ValueError(f"Saved {name} artifact changed outside Setup")
        return path

    def _copy_file(self, source: Path) -> str:
        data = source.read_bytes()
        name = hashlib.sha256(data).hexdigest() + source.suffix.lower()
        destination = contained(self.root, name)
        if not destination.exists():
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open("xb") as handle:
                handle.write(data)
        return name

    def _commit(self, candidate: dict[str, Any]) -> None:
        candidate["updated_utc"] = datetime.now(timezone.utc).isoformat()
        try:
            save_state(self.root, candidate)
        except OSError as exc:
            self.unsaved_error = str(exc)
            raise
        self._state = candidate

    def _edit(self, candidate: dict[str, Any], invalidated: set[str]) -> None:
        from app.services.setup_workflow.runtime_access import prepare_edit
        with prepare_edit(self.rigs.base_dir):
            candidate["generation"] = self.generation + 1
            candidate["changed"] = True
            for name in invalidated:
                candidate["checks"].pop(name, None)
                self.visit_checks.discard(name)
            # Compatible checks survive a change to an independent input.
            for result in candidate["checks"].values():
                result["generation"] = candidate["generation"]
            self._commit(candidate)
            self.unsaved_error = ""

    def note_unsaved_failure(self, message: str) -> None:
        self.unsaved_error = message

    def import_legacy(self) -> None:
        """Copy explicitly selected workspace artifacts without changing originals."""
        source_root = self.rigs.config_path.resolve().parent.parent
        calibration = source_root / "calibration" / "stereo_calibration.npz"
        candidates = (source_root / "rois" / "shared_rois.json", source_root / "configs" / "roi.json")
        candidate = self.state
        if calibration.is_file():
            candidate["artifacts"]["calibration"] = self._copy_file(calibration)
            candidate["calibration_identity"] = None
        roi = next((path for path in candidates if path.is_file()), None)
        if roi is not None:
            candidate["regions"] = json.loads(roi.read_text(encoding="utf-8"))
        candidate["legacy_import"] = {"calibration": str(calibration), "roi": str(roi) if roi else None}
        self._edit(candidate, {"calibration", "field", "regions"})

    def update_settings(self, section: str, updates: dict[str, Any]) -> None:
        with self._lock:
            payload = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
            if section not in {"camera", "stereo", "tracking", "detector", "trajectory", "metrics"}:
                raise ValueError("These values are not rig setup settings")
            if all(payload.get(section, {}).get(key) == value for key, value in updates.items()):
                self.unsaved_error = ""
                return
            payload.setdefault(section, {}).update(updates)
            path = configuration_file(self.root, payload)
            # Also construct the typed config before admitting the edit.
            load_config(path)
            candidate = self.state
            candidate["config_file"] = path.name
            geometry_keys = {"width", "height", "pixfmt", "color_mode", "flip_left", "flip_right",
                             "fps", "rotation_left", "rotation_right", "vertical_offset_px"}
            invalidated = {"images"} if section in {"camera", "stereo"} else set()
            if section == "camera" and geometry_keys.intersection(updates):
                invalidated.update(CHECK_NAMES)
                candidate["captures"] = []
            self._edit(candidate, invalidated)

    def assign(self, left: str, right: str) -> None:
        if not left or not right or left == right:
            raise ValueError("Select two distinct camera identities")
        with self._lock:
            ids = {"left": left, "right": right}
            if ids == self._state["camera_ids"]:
                self.unsaved_error = ""
                return
            candidate = self.state
            candidate["camera_ids"] = ids
            candidate["captures"] = []
            candidate["targets"] = []
            candidate["regions"] = {}
            self._edit(candidate, set(CHECK_NAMES))
            self.images.clear()

    def mark_focus_adjusted(self) -> None:
        candidate = self.state
        candidate["optics_revision"] = candidate.get("optics_revision", 0) + 1
        candidate["captures"] = []
        candidate["targets"] = []
        self._edit(candidate, set(CHECK_NAMES))

    def update_board(self, pattern: str, square_mm: float) -> None:
        from math import isfinite
        cols, rows = (int(value) for value in pattern.lower().split("x"))
        if min(cols, rows) < 3 or not isfinite(square_mm) or square_mm <= 0:
            raise ValueError("Board dimensions and measured square size must be positive")
        with self._lock:
            board = {"pattern": pattern, "square_mm": square_mm}
            if board == self._state["board"]:
                self.unsaved_error = ""
                return
            candidate = self.state
            candidate["board"] = board
            candidate["captures"] = []
            self._edit(candidate, {"calibration", "field", "regions"})

    def select_rig(self, profile_id: str | None) -> None:
        fresh = SetupWorkflowService(
            self.rigs.config_path, self.rigs.base_dir, profile_id=profile_id, backend=self.state["backend"],
            use_active=False,
        )
        with self._lock:
            self.root = fresh.root
            self._state = fresh.state
            self.images.clear()
            self.visit_checks.clear()
            self.image_metadata = {}

    def remember_inventory(self, inventory: dict[str, Any]) -> None:
        candidate = self.state
        candidate["camera_inventory"] = deepcopy(inventory)
        self._commit(candidate)

    def calibration_request(self, output_dir: Path):
        from contracts.tooling import CalibrationRequest
        state = self.state
        if len(state["captures"]) < 10:
            raise ValueError("Capture at least 10 distinct board pairs with varied positions and angles")
        return CalibrationRequest(
            tuple(contained(self.root, pair["left"]["file"]) for pair in state["captures"]),
            tuple(contained(self.root, pair["right"]["file"]) for pair in state["captures"]),
            state["board"]["pattern"], state["board"]["square_mm"], self.config_path,
            mode="full", write_updates=False, output_dir=output_dir,
        )

    def calibration_identity(self) -> dict[str, Any]:
        config = self.config
        return {
            "camera_ids": self.state["camera_ids"], "width": config.camera.width, "height": config.camera.height,
            "transforms": {key: getattr(config.camera, key) for key in (
                "flip_left", "flip_right", "rotation_left", "rotation_right", "vertical_offset_px",
            )},
            "board": self.state["board"],
            "optics_revision": self.state.get("optics_revision", 0),
            "capture_format": {"fps": config.camera.fps, "pixfmt": config.camera.pixfmt,
                               "color_mode": config.camera.color_mode},
        }

    def record_check(self, name: str, passed: bool, diagnostics: dict[str, Any], generation: int) -> None:
        with self._lock:
            if generation != self.generation:
                raise ValueError("Discarded checks for an earlier setup configuration")
            candidate = self.state
            candidate["checks"][name] = SetupCheck(passed, generation, diagnostics).to_payload()
            self._commit(candidate)
            self.visit_checks.add(name)

    def build_capture_request(self, purpose: SetupCapturePurpose) -> SetupCaptureRequest:
        if self.unsaved_error:
            raise ValueError("Resolve the unsaved configuration before capture")
        ids = self.state["camera_ids"]
        request = SetupCaptureRequest(
            uuid4().hex, purpose, ids.get("left", ""), ids.get("right", ""), self.config_path,
            60 if purpose == SetupCapturePurpose.CHECKS else 1, overall_deadline_ms=45_000,
            backend=self.state["backend"], config_sha256=hashlib.sha256(self.config_path.read_bytes()).hexdigest(),
            assignment_generation=self.generation,
        )
        from app.services.setup_workflow.runtime_access import begin_setup_capture
        begin_setup_capture(id(self), self.rigs.base_dir)
        return request

    def release_capture(self) -> None:
        from app.services.setup_workflow.runtime_access import end_setup_capture
        end_setup_capture(id(self))

    def apply_capture_result(self, result: SetupCaptureResult) -> object:
        from app.services.setup_workflow.capture_checks import apply_capture_result
        try:
            return apply_capture_result(self, result)
        finally:
            self.release_capture()

    def accept_calibration(self, source: Path, *, generated: bool = False) -> None:
        from app.services.setup_workflow.geometry import accept_calibration
        accept_calibration(self, source, generated=generated)

    def validate_calibration(self) -> None:
        from app.services.setup_workflow.geometry import validate_calibration
        validate_calibration(self)

    def update_targets(self, targets: list[dict[str, Any]]) -> None:
        candidate = self.state
        if targets == candidate["targets"]:
            self.unsaved_error = ""
            return
        candidate["targets"] = deepcopy(targets)

        def material(rows):
            return [{key: value for key, value in row.items()
                     if key not in {"source_pair", "calibration_sha256", "confirmed_sides"}} for row in rows]
        if material(targets) == material(self.state["targets"]):
            candidate["checks"].pop("field", None)
            self.visit_checks.discard("field")
            self._commit(candidate)
            return
        self._edit(candidate, {"field"})

    def use_observed_white_balance(self) -> None:
        from math import isfinite
        values = []
        for side in ("left", "right"):
            control = self.state.get("capture_context", {}).get("controls", {}).get(side, {})
            value = float(control.get("resolved_wb") or 0)
            if not control.get("readback_verified") or not isfinite(value) or value <= 0:
                raise ValueError("Capture both cameras with verified locked white balance first")
            values.append(value)
        if abs(values[0] - values[1]) / values[0] > 0.1:
            raise ValueError("Observed white balances differ by more than 10%; set an explicit shared value")
        self.update_settings("camera", {"wb": int(round(values[0]))})

    def fit_field(self) -> None:
        from app.services.setup_workflow.geometry import fit_field
        fit_field(self)

    def save_region(self, side: str, kind: str, polygon: list[list[int]]) -> None:
        from app.services.setup_workflow.geometry import save_region
        save_region(self, side, kind, polygon)

    def validate_regions(self) -> None:
        from app.services.setup_workflow.geometry import validate_regions
        validate_regions(self)

    def readiness(self, *, current_visit: bool = True) -> SetupReadiness:
        blockers = []
        if self.unsaved_error:
            blockers.append("Configuration changes have not been saved")
        try:
            config = self.config
            if config.camera.color_mode and config.camera.wb is None:
                blockers.append("Pin a verified white balance in Cameras, then rerun image checks")
            if hashlib.sha256(self.config_path.read_bytes()).hexdigest() != self.config_path.stem.removeprefix("config-"):
                blockers.append("Saved configuration was modified outside Setup")
        except (OSError, ValueError, ConfigError):
            blockers.append("Saved configuration is missing or unreadable")
        for name in CHECK_NAMES:
            check = self._state["checks"].get(name, {})
            if not check.get("passed") or check.get("generation") != self.generation:
                blockers.append(f"Complete {name} checks")
            elif current_visit and name not in self.visit_checks:
                blockers.append(f"Recheck {name} during this visit")
        return SetupReadiness("Needs checks" if blockers else "Ready for research recording", tuple(blockers), not blockers)

    def finish(self) -> str:
        from app.services.setup_workflow.publish import finish_setup
        return finish_setup(self)
