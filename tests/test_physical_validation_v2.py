from __future__ import annotations

import json
from pathlib import Path

import pytest

from calib.physical_validation import evaluate_physical_validation
from contracts.physical_validation import (
    PhysicalValidationCaseV2,
    PhysicalValidationDatasetV2,
    PhysicalValidationProtocolV2,
    ReferenceChannelV2,
    TailErrorPolicyV2,
)
from contracts.tooling import PhysicalValidationRequest
from app.services.tooling import SubprocessToolingService


DIGEST_A = "a" * 64
DIGEST_B = "b" * 64


def _protocol() -> PhysicalValidationProtocolV2:
    return PhysicalValidationProtocolV2(
        protocol_id="locked-protocol",
        trajectory_mode="stereo_3d",
        locked_utc="2026-01-01T00:00:00Z",
        claim_scope=("speed", "plate_location"),
        planned_strata={"middle": 1},
        thresholds={
            "max_rejected_rate": 0.1,
            "max_abs_speed_bias_mph": 1.0,
            "max_speed_mae_mph": 1.0,
            "max_speed_tail_error_mph": 1.0,
            "max_plate_mae_ft": 0.1,
            "max_plate_tail_error_ft": 0.1,
            "max_reference_speed_uncertainty_mph": 0.2,
            "max_reference_plate_uncertainty_ft": 0.02,
        },
        tail_policy=TailErrorPolicyV2(0.95, 1),
        exclusion_policy={"allowed_reference_codes": ["REFERENCE_DEVICE_INVALID"]},
        environment_scope={"site": "test-fixture"},
        correction_policy_sha256=DIGEST_A,
    )


def _reference() -> ReferenceChannelV2:
    return ReferenceChannelV2(
        channel_id="independent-reference",
        measurement_kind="speed_and_plate",
        device_identity="fixture-reference-serial",
        calibration_certificate_sha256=DIGEST_B,
        calibration_valid_from_utc="2025-01-01T00:00:00Z",
        calibration_valid_until_utc="2027-01-01T00:00:00Z",
        uncertainty=0.1,
        uncertainty_units="mixed_by_measurement",
        confidence_basis="expanded uncertainty recorded by channel",
        time_uncertainty_ms=0.1,
        independent_from_pitchtracker=True,
    )


def _case(**changes) -> PhysicalValidationCaseV2:
    values = {
        "case_id": "case-1",
        "stratum": "middle",
        "captured_utc": "2026-02-01T00:00:00Z",
        "mode": "stereo_3d",
        "reference_channel_id": "independent-reference",
        "reference_record_sha256": "c" * 64,
        "evidence_package_sha256": "d" * 64,
        "reference_status": "VALID",
        "system_outcome": "ACCEPTED",
        "reference_speed_mph": 90.0,
        "measured_speed_mph": 90.5,
        "reference_speed_uncertainty_mph": 0.1,
        "reference_plate_xy_ft": (0.0, 2.5),
        "measured_plate_xy_ft": (0.02, 2.51),
        "reference_plate_uncertainty_ft": 0.01,
    }
    values.update(changes)
    return PhysicalValidationCaseV2(**values)


def _dataset(protocol: PhysicalValidationProtocolV2, *, phase: str = "confirmation", cases=None):
    return PhysicalValidationDatasetV2(
        dataset_id="dataset-v2",
        phase=phase,
        protocol_sha256=protocol.protocol_sha256,
        rig_profile_id="rig-1",
        rig_profile_revision=2,
        pipeline_fingerprint="1" * 64,
        hardware_fingerprint_sha256="2" * 64,
        config_sha256="3" * 64,
        calibration_sha256="4" * 64,
        field_transform_sha256="5" * 64,
        environment={"site": "test-fixture"},
        reference_channels=(_reference(),),
        cases=tuple(cases or (_case(),)),
    )


def test_confirmation_report_can_pass_only_with_locked_independent_v2_evidence() -> None:
    protocol = _protocol()
    report = evaluate_physical_validation(protocol, _dataset(protocol))

    assert report["schema_version"] == "physical_ground_truth_report.v2"
    assert report["claim_ready"] is True
    assert report["metrics"]["reference_valid_count"] == 1
    assert report["metrics"]["accepted_count"] == 1


def test_shadow_and_tuning_cases_are_never_claim_ready() -> None:
    protocol = _protocol()
    shadow = evaluate_physical_validation(protocol, _dataset(protocol, phase="shadow"))
    tuned = evaluate_physical_validation(protocol, _dataset(protocol, cases=(_case(used_for_tuning=True),)))

    assert "SHADOW_DATASET_NOT_CLAIM_ELIGIBLE" in shadow["claim_blockers"]
    assert "CONFIRMATION_CASE_USED_FOR_TUNING" in tuned["claim_blockers"]


def test_reference_and_system_evidence_cannot_be_same_artifact() -> None:
    with pytest.raises(ValueError, match="cannot be the same"):
        _case(evidence_package_sha256="c" * 64)


def test_rejections_remain_in_reference_valid_denominator() -> None:
    protocol = _protocol()
    rejected = _case(
        system_outcome="REJECTED",
        measured_speed_mph=None,
        measured_plate_xy_ft=None,
        reason_codes=("NO_TRAJECTORY",),
    )
    report = evaluate_physical_validation(protocol, _dataset(protocol, cases=(rejected,)))

    assert report["metrics"]["reference_valid_count"] == 1
    assert report["metrics"]["rejected_count"] == 1
    assert report["metrics"]["rejected_or_unavailable_rate"] == 1.0
    assert report["claim_ready"] is False


def test_physical_validation_runs_through_tooling_worker(tmp_path: Path) -> None:
    protocol = _protocol()
    dataset = _dataset(protocol)
    protocol_path = tmp_path / "protocol.json"
    dataset_path = tmp_path / "dataset.json"
    output_path = tmp_path / "report.json"
    protocol_path.write_text(json.dumps(protocol.to_payload()), encoding="utf-8")
    dataset_path.write_text(json.dumps(dataset.to_payload()), encoding="utf-8")

    service = SubprocessToolingService(project_root=Path(__file__).resolve().parents[1])
    result = service.validate_physical_dataset(
        PhysicalValidationRequest(protocol_path, dataset_path, output_path)
    )

    assert result.report["claim_ready"] is True
    assert output_path.exists()
