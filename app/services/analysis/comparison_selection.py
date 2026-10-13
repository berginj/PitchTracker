"""Explicit detector selection through the saved setup owner, never a live switch."""

from dataclasses import replace
import json
from pathlib import Path

from app.services.analysis.comparison_qualification import admit_live_profile
from contracts.model_bundle import ModelBundle


def select_qualified_profile(workflow, bundle_path, qualification_path):
    bundle_path, qualification_path = Path(bundle_path).resolve(), Path(qualification_path).resolve()
    receipt = json.loads(qualification_path.read_text(encoding="utf-8"))
    bundle = ModelBundle.load(bundle_path)
    detector_updates = {
        "type": "ml",
        "model_path": str(bundle_path),
        "model_format": "yolo_v11",
        "model_input_size": list(bundle.input_size),
        "model_conf_threshold": bundle.confidence_threshold,
        "model_class_id": bundle.ball_class_id,
        "qualification_path": str(qualification_path),
    }
    stereo_mode = receipt["variant"].split(":")[1]
    config = replace(
        workflow.config,
        detector=replace(workflow.config.detector, **detector_updates),
        stereo=replace(workflow.config.stereo, association_mode=stereo_mode),
    )
    admit_live_profile(config)
    from app.services.analysis.comparison_rig import admit_live_rig

    state = workflow.state
    admit_live_rig(
        config, workflow.artifact("calibration"), state["regions"], state["field_transform"], state["camera_ids"]
    )
    workflow.update_detector_profile(detector_updates, stereo_mode)
    return workflow.state


def select_classical_profile(workflow):
    workflow.update_detector_profile(
        {
            "type": "classical",
            "model_path": None,
            "qualification_path": None,
            "model_format": "yolo_v5",
            "mode": "MODE_A",
        },
        "greedy_v1",
    )
    return workflow.state
