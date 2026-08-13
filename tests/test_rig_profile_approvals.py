from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import numpy as np
import pytest

from app.services.rig_profile import (
    CRITICAL,
    RigProfile,
    RigProfileService,
    TrajectoryModeApproval,
    _measurement_bindings,
)
from calib.physical_validation import evaluate_physical_validation
from configs.settings import load_config
from contracts.physical_validation import (
    ApprovalSignatureV2,
    PhysicalValidationCaseV2,
    PhysicalValidationDatasetV2,
    PhysicalValidationProtocolV2,
    ReferenceChannelV2,
    TailErrorPolicyV2,
    TrajectoryModeApprovalV2,
    approval_signature_hex,
)
from contracts.setup_snapshot import SetupSystemSnapshot
from contracts.versioning import APP_VERSION


def _config():
    return load_config(Path(__file__).parent.parent / "configs" / "default.yaml")


def _valid_setup_snapshot(profile: RigProfile) -> dict:
    digest = "a" * 64
    mode = {"width": 1280, "height": 720, "fps": 60, "pixfmt": "GRAY8"}
    camera = lambda hardware_id: {  # noqa: E731 - compact symmetric fixture
        "hardware_id": hardware_id,
        "friendly_name": hardware_id,
        "recognized": True,
        "global_shutter": True,
        "negotiated_mode": mode,
        "controls_readback": {"readback_verified": True},
    }
    snapshot = SetupSystemSnapshot.create(
        snapshot_id="setup-test",
        created_utc="2026-01-01T00:00:00Z",
        rig_profile_id=profile.profile_id,
        rig_profile_revision=profile.profile_revision,
        sections={
            "rig": {
                "backend": profile.backend,
                "camera_serials": dict(profile.camera_serials),
            },
            "software": {
                "app_version": APP_VERSION,
                "source_revision": "b" * 40,
                "working_tree_dirty": False,
            },
            "host": {"os": "test", "python_version": "3.13"},
            "cameras": {
                "left": camera(profile.camera_serials["left"]),
                "right": camera(profile.camera_serials["right"]),
            },
            "capture_qualification": {
                "frame_count_left": 60,
                "frame_count_right": 60,
                "paired_count": 60,
                "assessment": {"status": "PASS"},
            },
            "geometry": {
                "calibration": {"sha256": digest, "production_ready": True},
                "roi": {"sha256": digest},
                "field_transform": {"sha256": digest, "passed": True},
            },
            "detection_tracking": {
                "config_sha256": digest,
                "association": {"algorithm": "greedy_v1"},
            },
            "trajectory_corrections": {
                "primary_mode": "stereo_3d",
                "correction_policy_sha256": digest,
            },
            "validation": {},
        },
        artifact_inventory={
            "calibration": digest,
            "roi": digest,
            "field_transform": digest,
            "config": digest,
        },
    )
    assert snapshot.assessment.configuration_evidence_complete is True
    return snapshot.to_payload()


def _write_calibration(
    path: Path,
    *,
    mode: str = "FULL",
    quality: str = "GOOD",
    rms_error_px: float = 0.42,
    include_production_metadata: bool = True,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = dict(
        mtx_left=np.eye(3),
        mtx_right=np.eye(3),
        dist_left=np.zeros(5),
        dist_right=np.zeros(5),
        R=np.eye(3),
        T=np.array([[304.8], [0.0], [0.0]]),
        F=np.eye(3),
        img_size=np.array([1280, 720]),
        quality_rating=quality,
        rms_error_px=rms_error_px,
        num_images_used=12,
        per_image_errors=np.asarray(
            [
                {
                    "left_rms": rms_error_px,
                    "right_rms": rms_error_px,
                    "combined_rms": rms_error_px,
                }
                for _ in range(12)
            ],
            dtype=object,
        ),
    )
    if include_production_metadata:
        payload["calibration_mode"] = mode
        payload["production_ready"] = mode != "QUICK"
    np.savez(path, **payload)


def _write_roi(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "lane": [[10, 10], [100, 10], [100, 100], [10, 100]],
                "plate": [[20, 20], [80, 20], [80, 60], [20, 60]],
                "lane_by_camera": {
                    "left_cam": [[10, 10], [100, 10], [100, 100], [10, 100]],
                    "right_cam": [[12, 10], [102, 10], [102, 100], [12, 100]],
                },
            }
        ),
        encoding="utf-8",
    )


def _profile(service: RigProfileService, *, mode: str = "FULL", backend: str = "sim") -> RigProfile:
    cfg = _config()
    profile = RigProfile.from_config(
        "rig_a",
        cfg,
        backend=backend,
        left_serial="left_cam",
        right_serial="right_cam",
        quality_metrics={"calibration_mode": mode},
    )
    profile_dir = service.profile_dir(profile.profile_id)
    _write_calibration(profile_dir / profile.calibration_file, mode=mode)
    _write_roi(profile_dir / profile.roi_file)
    return service.save(profile, activate=True)


def _field_transform() -> dict[str, object]:
    return {
        "matrix_4x4": [[1, 0, 0, 0], [0, 1, 0, 0], [0, 0, 1, 0], [0, 0, 0, 1]],
        "rms_residual_ft": 0.01,
        "fixture_id": "plate-fixture",
        "max_rms_residual_ft": 0.1,
    }


def _ray_primary_config(mode: str = "ray_graph"):
    config = _config()
    return replace(config, trajectory=replace(config.trajectory, primary_mode=mode))


def _approval(profile: RigProfile, *, mode: str = "ray_graph", **changes) -> TrajectoryModeApproval:
    values = {
        "mode": mode,
        "rig_profile_id": profile.profile_id,
        "rig_profile_revision": profile.profile_revision,
        "software_version": APP_VERSION,
        "dataset_id": "field-ground-truth-2026-07",
        "ground_truth_report_sha256": "a" * 64,
        "claim_ready": True,
    }
    values.update(changes)
    return TrajectoryModeApproval(**values)


def test_trajectory_mode_approval_round_trips_as_typed_profile_record() -> None:
    profile = RigProfile.from_dict(
        {
            "profile_id": "rig-approval",
            "profile_revision": 7,
            "trajectory_mode_approvals": [
                {
                    "schema_version": "trajectory_mode_approval.v1",
                    "mode": "ray_graph",
                    "rig_profile_id": "rig-approval",
                    "rig_profile_revision": 7,
                    "software_version": APP_VERSION,
                    "dataset_id": "dataset-7",
                    "ground_truth_report_sha256": "b" * 64,
                    "claim_ready": True,
                }
            ],
        }
    )

    restored = RigProfile.from_dict(json.loads(json.dumps(profile.to_dict())))

    assert restored.trajectory_mode_approvals == profile.trajectory_mode_approvals
    assert isinstance(restored.trajectory_mode_approvals[0], TrajectoryModeApproval)
    assert restored.trajectory_mode_approvals[0].dataset_id == "dataset-7"


def test_trajectory_mode_approval_requires_dataset_and_report_digest() -> None:
    profile = RigProfile.from_dict({"profile_id": "rig-approval"})
    with pytest.raises(ValueError, match="dataset_id is required"):
        _approval(profile, dataset_id="  ")
    with pytest.raises(ValueError, match="lowercase SHA-256"):
        _approval(profile, ground_truth_report_sha256="not-a-digest")


def test_physical_ray_primary_is_critical_when_approval_is_missing(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, backend="uvc")
    profile = service.save(replace(profile, field_transform=_field_transform()))

    validation = service.validate_for_runtime(profile, config=_ray_primary_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert validation.diagnostics["trajectory_primary_approval_rejections"] == ["MISSING_MODE_APPROVAL"]
    assert any("not approved for physical runtime" in item for item in validation.issues)


def test_physical_ray_primary_rejects_approval_bound_to_other_revision(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, backend="uvc")
    stale = _approval(profile, rig_profile_revision=profile.profile_revision + 1)
    profile = service.save(
        replace(profile, field_transform=_field_transform(), trajectory_mode_approvals=(stale,))
    )

    validation = service.validate_for_runtime(profile, config=_ray_primary_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert "RIG_PROFILE_REVISION_MISMATCH" in validation.diagnostics["trajectory_primary_approval_rejections"]


@pytest.mark.parametrize(
    ("approval_changes", "expected_reason"),
    [
        ({"rig_profile_id": "other-rig"}, "RIG_PROFILE_ID_MISMATCH"),
        ({"software_version": "older-build"}, "SOFTWARE_VERSION_MISMATCH"),
        ({"claim_ready": False}, "GROUND_TRUTH_NOT_CLAIM_READY"),
        ({"mode": "ray_reprojection"}, "MISSING_MODE_APPROVAL"),
    ],
)
def test_physical_ray_primary_rejects_mismatched_approval_binding(
    tmp_path: Path,
    approval_changes: dict[str, object],
    expected_reason: str,
) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, backend="uvc")
    mismatched = _approval(profile, **approval_changes)
    profile = service.save(
        replace(profile, field_transform=_field_transform(), trajectory_mode_approvals=(mismatched,))
    )

    validation = service.validate_for_runtime(profile, config=_ray_primary_config(), backend="uvc")

    assert validation.state == CRITICAL
    assert expected_reason in validation.diagnostics["trajectory_primary_approval_rejections"]


def test_physical_ray_primary_accepts_exact_claim_ready_approval(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, backend="uvc")
    approval = _approval(profile)
    profile = service.save(
        replace(profile, field_transform=_field_transform(), trajectory_mode_approvals=(approval,))
    )

    validation = service.validate_for_runtime(profile, config=_ray_primary_config(), backend="uvc")

    assert validation.state != CRITICAL
    assert validation.issues == []
    assert validation.diagnostics["trajectory_primary_approved"] is True
    assert validation.diagnostics["trajectory_primary_approval"]["dataset_id"] == approval.dataset_id
    assert validation.diagnostics["trajectory_accuracy_claim_eligible"] is False
    assert validation.diagnostics["trajectory_accuracy_claim_blockers"] == [
        "LEGACY_V1_APPROVAL_NOT_ACCURACY_CLAIM_ELIGIBLE"
    ]


def test_unapproved_ray_mode_may_remain_comparison_only_on_physical_runtime(tmp_path: Path) -> None:
    service = RigProfileService(base_dir=tmp_path / "rigs")
    profile = _profile(service, backend="uvc")
    profile = service.save(replace(profile, field_transform=_field_transform()))
    config = _config()
    config = replace(
        config,
        trajectory=replace(config.trajectory, primary_mode="stereo_3d", compare_modes=("ray_graph",)),
    )

    validation = service.validate_for_runtime(profile, config=config, backend="uvc")

    assert validation.state != CRITICAL
    assert validation.issues == []
    assert validation.diagnostics["trajectory_primary_approval_required"] is False


def test_v2_accuracy_claim_requires_exact_artifacts_fingerprints_and_two_signatures(tmp_path: Path) -> None:
    keys = {"collector-key": b"collector-secret", "reviewer-key": b"reviewer-secret"}
    service = RigProfileService(base_dir=tmp_path / "rigs", approval_trust_keys=keys)
    profile = _profile(service, backend="uvc")
    profile = replace(profile, field_transform=_field_transform())
    profile = service.save(replace(profile, setup_snapshot=_valid_setup_snapshot(profile)))
    config = _config()
    bindings = _measurement_bindings(service, profile, config)

    thresholds = {
        "max_rejected_rate": 0.0,
        "max_abs_speed_bias_mph": 1.0,
        "max_speed_mae_mph": 1.0,
        "max_speed_tail_error_mph": 1.0,
        "max_plate_mae_ft": 0.1,
        "max_plate_tail_error_ft": 0.1,
        "max_reference_speed_uncertainty_mph": 0.2,
        "max_reference_plate_uncertainty_ft": 0.02,
    }
    protocol = PhysicalValidationProtocolV2(
        protocol_id="protocol-v2",
        trajectory_mode="stereo_3d",
        locked_utc="2026-01-01T00:00:00Z",
        claim_scope=("speed", "plate_location"),
        planned_strata={"middle": 1},
        thresholds=thresholds,
        tail_policy=TailErrorPolicyV2(0.95, 1),
        exclusion_policy={},
        environment_scope={"site": "fixture"},
        correction_policy_sha256=bindings["correction_policy_sha256"],
    )
    reference = ReferenceChannelV2(
        "reference", "speed_and_plate", "reference-device", "a" * 64,
        "2025-01-01T00:00:00Z", "2027-01-01T00:00:00Z", 0.1, "declared",
        "expanded uncertainty", 0.1, True,
    )
    case = PhysicalValidationCaseV2(
        case_id="case-1",
        stratum="middle",
        captured_utc="2026-02-01T00:00:00Z",
        mode="stereo_3d",
        reference_channel_id="reference",
        reference_record_sha256="b" * 64,
        evidence_package_sha256="c" * 64,
        reference_status="VALID",
        system_outcome="ACCEPTED",
        reference_speed_mph=90.0,
        measured_speed_mph=90.25,
        reference_speed_uncertainty_mph=0.1,
        reference_plate_xy_ft=(0.0, 2.5),
        measured_plate_xy_ft=(0.02, 2.5),
        reference_plate_uncertainty_ft=0.01,
    )
    dataset = PhysicalValidationDatasetV2(
        dataset_id="dataset-v2",
        phase="confirmation",
        protocol_sha256=protocol.protocol_sha256,
        rig_profile_id=profile.profile_id,
        rig_profile_revision=profile.profile_revision,
        pipeline_fingerprint=bindings["pipeline_fingerprint"],
        hardware_fingerprint_sha256=bindings["hardware_fingerprint_sha256"],
        config_sha256=bindings["config_sha256"],
        calibration_sha256=bindings["calibration_sha256"],
        field_transform_sha256=bindings["field_transform_sha256"],
        environment={"site": "fixture"},
        reference_channels=(reference,),
        cases=(case,),
    )
    report = evaluate_physical_validation(protocol, dataset)
    assert report["claim_ready"] is True

    profile_dir = service.profile_dir(profile.profile_id)
    protocol_path = profile_dir / "physical_protocol.json"
    dataset_path = profile_dir / "physical_dataset.json"
    report_path = profile_dir / "physical_report.json"
    protocol_path.write_text(json.dumps(protocol.to_payload(), sort_keys=True), encoding="utf-8")
    dataset_path.write_text(json.dumps(dataset.to_payload(), sort_keys=True), encoding="utf-8")
    report_path.write_text(json.dumps(report, sort_keys=True), encoding="utf-8")
    report_digest = hashlib.sha256(report_path.read_bytes()).hexdigest()

    unsigned = TrajectoryModeApprovalV2(
        approval_id="approval-v2",
        mode="stereo_3d",
        claim_scope=("speed", "plate_location"),
        rig_profile_id=profile.profile_id,
        rig_profile_revision=profile.profile_revision,
        software_version=APP_VERSION,
        pipeline_fingerprint=bindings["pipeline_fingerprint"],
        hardware_fingerprint_sha256=bindings["hardware_fingerprint_sha256"],
        config_sha256=bindings["config_sha256"],
        calibration_sha256=bindings["calibration_sha256"],
        field_transform_sha256=bindings["field_transform_sha256"],
        correction_policy_sha256=bindings["correction_policy_sha256"],
        protocol_sha256=protocol.protocol_sha256,
        dataset_id=dataset.dataset_id,
        dataset_manifest_sha256=dataset.dataset_sha256,
        ground_truth_report_sha256=report_digest,
        protocol_file=protocol_path.name,
        dataset_manifest_file=dataset_path.name,
        ground_truth_report_file=report_path.name,
        environment_scope={"site": "fixture"},
        issued_utc="2026-03-01T00:00:00Z",
        expires_utc="2099-03-01T00:00:00Z",
        lifecycle_state="ACTIVE",
        claim_ready=True,
    )
    approval = replace(
        unsigned,
        signatures=(
            ApprovalSignatureV2(
                "collector-key", "collector", approval_signature_hex(unsigned, keys["collector-key"])
            ),
            ApprovalSignatureV2(
                "reviewer-key", "reviewer", approval_signature_hex(unsigned, keys["reviewer-key"])
            ),
        ),
    )
    profile = service.save(replace(profile, trajectory_mode_approvals=(approval,)))

    validation = service.validate_for_runtime(profile, config=config, backend="uvc")
    assert validation.diagnostics["trajectory_operationally_eligible"] is True
    assert validation.diagnostics["trajectory_accuracy_claim_eligible"] is True
    assert validation.diagnostics["validated_configuration_ready"] is True, (
        validation.state,
        validation.warnings,
        validation.diagnostics["setup_snapshot_blockers"],
    )
    recommended_pairs = service.previously_validated_camera_pairs()
    assert recommended_pairs[0]["left_id"] == profile.camera_serials["left"]
    assert recommended_pairs[0]["right_id"] == profile.camera_serials["right"]
    assert recommended_pairs[0]["profile_id"] == profile.profile_id

    report_path.write_text(json.dumps({**report, "claim_ready": False}), encoding="utf-8")
    tampered = service.validate_for_runtime(profile, config=config, backend="uvc")
    assert tampered.diagnostics["trajectory_accuracy_claim_eligible"] is False
    assert any(
        "REPORT_HASH_MISMATCH" in reason
        for reason in tampered.diagnostics["trajectory_accuracy_claim_blockers"]
    )
