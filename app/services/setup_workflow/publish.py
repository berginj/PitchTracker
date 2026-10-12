"""Publish checked rig revisions without replacing previously completed artifacts."""

from __future__ import annotations

from dataclasses import replace
import json
from types import SimpleNamespace
from typing import TYPE_CHECKING
from uuid import uuid4

import numpy as np

from app.services.rig_profile_models import RigProfile, PASS
from app.services.rig_profile_persistence import atomic_write_text
from app.services.setup_snapshot import assemble_setup_snapshot
from calib.capture_qualification import CaptureQualification
from contracts.quality import QualityAssessment
from contracts.capability_observation import CapabilityObservation
from contracts.setup import StereoCalibrationProfile
from contracts.versioning import APP_VERSION, SCHEMA_VERSION

if TYPE_CHECKING:
    from app.services.setup_workflow.service import SetupWorkflowService


def finish_setup(service: SetupWorkflowService) -> str:
    readiness = service.readiness()
    if not readiness.permits_recording:
        raise ValueError("; ".join(readiness.blockers))
    state = service.state
    if state["base_profile_id"] and not state["changed"]:
        base = service.rigs.load(state["base_profile_id"])
        validation = service.rigs.validate_for_runtime(
            base, config=service.config, backend=state["backend"],
            left_serial=state["camera_ids"]["left"], right_serial=state["camera_ids"]["right"],
        )
        if validation.is_critical:
            raise ValueError("; ".join(validation.issues))
        atomic_write_text(
            service.rigs.profile_dir(base.profile_id) / f"preflight-{uuid4().hex}.json",
            json.dumps({"schema_version": "setup_preflight.v1", "checks": state["checks"]}, indent=2),
        )
        return base.profile_id

    from app.services.setup_workflow.runtime_access import prepare_edit
    with prepare_edit(service.rigs.base_dir):
        profile_id = "rig_" + uuid4().hex
        directory = service.rigs.profile_dir(profile_id)
        directory.mkdir(parents=True, exist_ok=False)
        import shutil
        shutil.copy2(service.config_path, directory / "effective_config.yaml")
        shutil.copy2(service.artifact("calibration"), directory / "stereo_calibration.npz")
        shutil.copy2(service.artifact("regions"), directory / "roi.json")
        for target in state["targets"]:
            for side in ("left", "right"):
                filename = target["source_pair"][side]["file"]
                shutil.copy2(service.root / filename, directory / filename)
        atomic_write_text(directory / "stereo_calibration.identity.json", json.dumps(state["calibration_identity"], indent=2))
        config = service.config
        with np.load(service.artifact("calibration"), allow_pickle=False) as matrices:
            stereo = StereoCalibrationProfile(
                float(np.linalg.norm(matrices["T"])) / 25.4,
                float(matrices["rms_error_px"]),
                float(state["checks"]["field"]["diagnostics"].get("calibrated_epipolar_error_px", 0.0)),
                config.camera.width, config.camera.height, "charuco", True,
                "stereo_calibration.npz", app_version=APP_VERSION, schema_version=SCHEMA_VERSION,
            )
        profile = RigProfile.from_config(
            profile_id, config, backend=state["backend"], left_serial=state["camera_ids"]["left"],
            right_serial=state["camera_ids"]["right"], calibration_file="stereo_calibration.npz", roi_file="roi.json",
        )
        previous = service.rigs.load(state["base_profile_id"]) if state["base_profile_id"] else None
        profile = replace(
            profile, profile_revision=previous.profile_revision + 1 if previous else 1,
            effective_config_file="effective_config.yaml", stereo_profile=stereo, board_metadata=state["board"],
            field_transform=state["field_transform"], runtime_validation_status=PASS,
            quality_metrics={"guided_checks": state["checks"]},
            control_settings={**profile.control_settings, "readback": state["capture_context"]["controls"]},
            diagnostics={"setup_source": "guided_setup", "previous_profile_id": state["base_profile_id"],
                         "optics_revision": state.get("optics_revision", 0)},
        )
        raw = state["checks"]["images"]["diagnostics"]["qualification"]
        qualification = CaptureQualification(**{**raw, "assessment": QualityAssessment.from_payload(raw["assessment"])})
        camera_rows = state.get("camera_inventory", {})
        cameras = [
            SimpleNamespace(**{**camera_rows.get(side, {}), "hardware_id": identity})
            for side, identity in state["camera_ids"].items()
        ]
        snapshot = assemble_setup_snapshot(
            profile=profile, config=config, config_path=directory / "effective_config.yaml",
            cameras=cameras, capture_qualification=qualification,
            capture_diagnostics=state["capture_context"], calibration_path=directory / "stereo_calibration.npz",
            roi_path=directory / "roi.json",
            capability_observations={
                side: CapabilityObservation.from_payload(payload)
                for side, payload in state["capture_context"].get("capability_observations", {}).items()
            },
        )
        profile = service.rigs.save(replace(profile, setup_snapshot=snapshot.to_payload()))
        validation = service.rigs.validate_for_runtime(
            profile, config=config, backend=state["backend"],
            left_serial=state["camera_ids"]["left"], right_serial=state["camera_ids"]["right"],
        )
        if validation.is_critical:
            raise ValueError("; ".join(validation.issues))
        candidate = service.state
        candidate["published_profile_id"] = profile_id
        service._commit(candidate)
        service.rigs.activate(profile_id)
        candidate["changed"] = False
        service._commit(candidate)
        return profile_id
