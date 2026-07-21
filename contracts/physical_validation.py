"""Versioned contracts for independent physical validation evidence.

The v2 contracts deliberately separate operational readiness from permission to
make an accuracy claim.  They do not contain reference-instrument secrets and
cannot themselves establish that a physical test was performed.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Any, Mapping, Optional


PROTOCOL_SCHEMA = "physical_validation_protocol.v2"
DATASET_SCHEMA = "physical_validation_dataset.v2"
REPORT_SCHEMA = "physical_ground_truth_report.v2"
APPROVAL_SCHEMA = "trajectory_mode_approval.v2"

VALIDATION_PHASES = frozenset({"shadow", "confirmation"})
SYSTEM_OUTCOMES = frozenset({"ACCEPTED", "REJECTED", "UNAVAILABLE"})
REFERENCE_STATUSES = frozenset({"VALID", "INVALID"})
APPROVAL_STATES = frozenset({"DRAFT", "REVIEWED", "ACTIVE", "SUSPENDED", "EXPIRED", "REVOKED", "SUPERSEDED"})
CLAIM_SCOPES = frozenset({"speed", "plate_location", "strike_classification"})


def canonical_json_bytes(value: Mapping[str, Any]) -> bytes:
    return json.dumps(dict(value), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def payload_sha256(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_json_bytes(value)).hexdigest()


def _require_text(label: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} is required")
    return value.strip()


def _require_digest(label: str, value: Any) -> str:
    digest = _require_text(label, value)
    if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
        raise ValueError(f"{label} must be a lowercase SHA-256 digest")
    return digest


def _parse_utc(label: str, value: str) -> datetime:
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError(f"{label} must be an ISO-8601 timestamp") from exc
    if parsed.tzinfo is None:
        raise ValueError(f"{label} must include a timezone")
    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class ReferenceChannelV2:
    channel_id: str
    measurement_kind: str
    device_identity: str
    calibration_certificate_sha256: str
    calibration_valid_from_utc: str
    calibration_valid_until_utc: str
    uncertainty: float
    uncertainty_units: str
    confidence_basis: str
    time_uncertainty_ms: float
    independent_from_pitchtracker: bool

    def __post_init__(self) -> None:
        for label in ("channel_id", "measurement_kind", "device_identity", "uncertainty_units", "confidence_basis"):
            _require_text(label, getattr(self, label))
        _require_digest("calibration_certificate_sha256", self.calibration_certificate_sha256)
        start = _parse_utc("calibration_valid_from_utc", self.calibration_valid_from_utc)
        end = _parse_utc("calibration_valid_until_utc", self.calibration_valid_until_utc)
        if end <= start:
            raise ValueError("reference calibration validity interval is empty")
        if self.uncertainty < 0 or self.time_uncertainty_ms < 0:
            raise ValueError("reference uncertainty must be non-negative")
        if self.independent_from_pitchtracker is not True:
            raise ValueError("physical validation requires an independent reference channel")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "ReferenceChannelV2":
        return cls(**dict(payload))

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TailErrorPolicyV2:
    percentile: float
    minimum_evaluated_samples: int
    insufficient_samples_result: str = "BLOCK"

    def __post_init__(self) -> None:
        if not 0.5 < float(self.percentile) < 1.0:
            raise ValueError("tail percentile must be between 0.5 and 1.0")
        if self.minimum_evaluated_samples <= 0:
            raise ValueError("tail minimum_evaluated_samples must be positive")
        if self.insufficient_samples_result != "BLOCK":
            raise ValueError("insufficient tail samples must block a physical claim")


@dataclass(frozen=True)
class PhysicalValidationProtocolV2:
    protocol_id: str
    trajectory_mode: str
    locked_utc: str
    claim_scope: tuple[str, ...]
    planned_strata: dict[str, int]
    thresholds: dict[str, float]
    tail_policy: TailErrorPolicyV2
    exclusion_policy: dict[str, Any]
    environment_scope: dict[str, Any]
    correction_policy_sha256: str
    schema_version: str = PROTOCOL_SCHEMA

    def __post_init__(self) -> None:
        _require_text("protocol_id", self.protocol_id)
        if self.trajectory_mode not in {"stereo_3d", "ray_reprojection", "ray_graph"}:
            raise ValueError("physical validation protocol trajectory_mode is unsupported")
        _parse_utc("locked_utc", self.locked_utc)
        if self.schema_version != PROTOCOL_SCHEMA:
            raise ValueError(f"unsupported physical validation protocol schema: {self.schema_version!r}")
        if not self.claim_scope or any(scope not in CLAIM_SCOPES for scope in self.claim_scope):
            raise ValueError("claim_scope contains no supported physical claim")
        if not self.planned_strata or any(not name.strip() or count <= 0 for name, count in self.planned_strata.items()):
            raise ValueError("planned_strata must contain positive predeclared counts")
        _require_digest("correction_policy_sha256", self.correction_policy_sha256)

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PhysicalValidationProtocolV2":
        data = dict(payload)
        data["claim_scope"] = tuple(data.get("claim_scope") or ())
        tail = data.get("tail_policy") or {}
        data["tail_policy"] = tail if isinstance(tail, TailErrorPolicyV2) else TailErrorPolicyV2(**dict(tail))
        return cls(**data)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def protocol_sha256(self) -> str:
        return payload_sha256(self.to_payload())


@dataclass(frozen=True)
class PhysicalValidationCaseV2:
    case_id: str
    stratum: str
    captured_utc: str
    mode: str
    reference_channel_id: str
    reference_record_sha256: str
    evidence_package_sha256: str
    reference_status: str
    system_outcome: str
    reference_speed_mph: Optional[float] = None
    measured_speed_mph: Optional[float] = None
    reference_speed_uncertainty_mph: Optional[float] = None
    reference_plate_xy_ft: Optional[tuple[float, float]] = None
    measured_plate_xy_ft: Optional[tuple[float, float]] = None
    reference_plate_uncertainty_ft: Optional[float] = None
    raw_measurements: dict[str, Any] = field(default_factory=dict)
    corrected_measurements: dict[str, Any] = field(default_factory=dict)
    reason_codes: tuple[str, ...] = ()
    used_for_tuning: bool = False

    def __post_init__(self) -> None:
        for label in ("case_id", "stratum", "mode", "reference_channel_id"):
            _require_text(label, getattr(self, label))
        _parse_utc("captured_utc", self.captured_utc)
        _require_digest("reference_record_sha256", self.reference_record_sha256)
        _require_digest("evidence_package_sha256", self.evidence_package_sha256)
        if self.reference_record_sha256 == self.evidence_package_sha256:
            raise ValueError("independent reference and system evidence cannot be the same artifact")
        if self.reference_status not in REFERENCE_STATUSES:
            raise ValueError(f"invalid reference_status: {self.reference_status!r}")
        if self.system_outcome not in SYSTEM_OUTCOMES:
            raise ValueError(f"invalid system_outcome: {self.system_outcome!r}")
        for label in ("reference_speed_uncertainty_mph", "reference_plate_uncertainty_ft"):
            value = getattr(self, label)
            if value is not None and value < 0:
                raise ValueError(f"{label} must be non-negative")
        if self.reference_status == "VALID" and self.reference_speed_mph is None and self.reference_plate_xy_ft is None:
            raise ValueError("a valid reference case must contain speed or plate truth")
        if self.system_outcome != "ACCEPTED" and (self.measured_speed_mph is not None or self.measured_plate_xy_ft is not None):
            raise ValueError("rejected/unavailable cases must not invent accepted measurements")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PhysicalValidationCaseV2":
        data = dict(payload)
        data["reason_codes"] = tuple(data.get("reason_codes") or ())
        for key in ("reference_plate_xy_ft", "measured_plate_xy_ft"):
            if data.get(key) is not None:
                data[key] = tuple(data[key])
        return cls(**data)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PhysicalValidationDatasetV2:
    dataset_id: str
    phase: str
    protocol_sha256: str
    rig_profile_id: str
    rig_profile_revision: int
    pipeline_fingerprint: str
    hardware_fingerprint_sha256: str
    config_sha256: str
    calibration_sha256: str
    field_transform_sha256: str
    environment: dict[str, Any]
    reference_channels: tuple[ReferenceChannelV2, ...]
    cases: tuple[PhysicalValidationCaseV2, ...]
    schema_version: str = DATASET_SCHEMA

    def __post_init__(self) -> None:
        for label in ("dataset_id", "rig_profile_id"):
            _require_text(label, getattr(self, label))
        if self.phase not in VALIDATION_PHASES:
            raise ValueError(f"invalid validation phase: {self.phase!r}")
        for label in (
            "protocol_sha256", "pipeline_fingerprint", "hardware_fingerprint_sha256",
            "config_sha256", "calibration_sha256", "field_transform_sha256",
        ):
            _require_digest(label, getattr(self, label))
        if self.rig_profile_revision <= 0:
            raise ValueError("rig_profile_revision must be positive")
        if self.schema_version != DATASET_SCHEMA:
            raise ValueError(f"unsupported physical validation dataset schema: {self.schema_version!r}")
        if not self.reference_channels or not self.cases:
            raise ValueError("physical validation dataset requires reference channels and cases")
        channel_ids = [channel.channel_id for channel in self.reference_channels]
        if len(channel_ids) != len(set(channel_ids)):
            raise ValueError("reference channel IDs must be unique")
        case_ids = [case.case_id.strip() for case in self.cases]
        if len(case_ids) != len(set(case_ids)):
            raise ValueError("physical validation case IDs must be unique")
        known = set(channel_ids)
        if any(case.reference_channel_id not in known for case in self.cases):
            raise ValueError("case references an unknown independent reference channel")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "PhysicalValidationDatasetV2":
        data = dict(payload)
        data["reference_channels"] = tuple(
            item if isinstance(item, ReferenceChannelV2) else ReferenceChannelV2.from_payload(item)
            for item in data.get("reference_channels") or ()
        )
        data["cases"] = tuple(
            item if isinstance(item, PhysicalValidationCaseV2) else PhysicalValidationCaseV2.from_payload(item)
            for item in data.get("cases") or ()
        )
        return cls(**data)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    @property
    def dataset_sha256(self) -> str:
        return payload_sha256(self.to_payload())


@dataclass(frozen=True)
class ApprovalSignatureV2:
    signer_id: str
    role: str
    signature_hex: str
    algorithm: str = "hmac-sha256"

    def __post_init__(self) -> None:
        _require_text("signer_id", self.signer_id)
        if self.role not in {"collector", "reviewer"}:
            raise ValueError("approval signature role must be collector or reviewer")
        if self.algorithm != "hmac-sha256":
            raise ValueError("unsupported approval signature algorithm")
        _require_digest("signature_hex", self.signature_hex)


@dataclass(frozen=True)
class TrajectoryModeApprovalV2:
    approval_id: str
    mode: str
    claim_scope: tuple[str, ...]
    rig_profile_id: str
    rig_profile_revision: int
    software_version: str
    pipeline_fingerprint: str
    hardware_fingerprint_sha256: str
    config_sha256: str
    calibration_sha256: str
    field_transform_sha256: str
    correction_policy_sha256: str
    protocol_sha256: str
    dataset_id: str
    dataset_manifest_sha256: str
    ground_truth_report_sha256: str
    protocol_file: str
    dataset_manifest_file: str
    ground_truth_report_file: str
    environment_scope: dict[str, Any]
    issued_utc: str
    expires_utc: str
    lifecycle_state: str
    claim_ready: bool
    signatures: tuple[ApprovalSignatureV2, ...] = ()
    schema_version: str = APPROVAL_SCHEMA

    def __post_init__(self) -> None:
        for label in (
            "approval_id", "mode", "rig_profile_id", "software_version", "dataset_id",
            "protocol_file", "dataset_manifest_file", "ground_truth_report_file",
        ):
            _require_text(label, getattr(self, label))
        if not self.claim_scope or any(scope not in CLAIM_SCOPES for scope in self.claim_scope):
            raise ValueError("approval claim_scope contains no supported claim")
        if self.rig_profile_revision <= 0:
            raise ValueError("approval rig_profile_revision must be positive")
        for label in (
            "pipeline_fingerprint", "hardware_fingerprint_sha256", "config_sha256", "calibration_sha256",
            "field_transform_sha256", "correction_policy_sha256", "protocol_sha256",
            "dataset_manifest_sha256", "ground_truth_report_sha256",
        ):
            _require_digest(label, getattr(self, label))
        if self.schema_version != APPROVAL_SCHEMA:
            raise ValueError(f"unsupported trajectory approval schema: {self.schema_version!r}")
        if self.lifecycle_state not in APPROVAL_STATES:
            raise ValueError(f"invalid approval lifecycle state: {self.lifecycle_state!r}")
        if not isinstance(self.claim_ready, bool):
            raise ValueError("approval claim_ready must be boolean")
        if _parse_utc("expires_utc", self.expires_utc) <= _parse_utc("issued_utc", self.issued_utc):
            raise ValueError("approval expiry must be after issue time")

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "TrajectoryModeApprovalV2":
        data = dict(payload)
        data["claim_scope"] = tuple(data.get("claim_scope") or ())
        data["signatures"] = tuple(
            item if isinstance(item, ApprovalSignatureV2) else ApprovalSignatureV2(**dict(item))
            for item in data.get("signatures") or ()
        )
        return cls(**data)

    def to_payload(self) -> dict[str, Any]:
        return asdict(self)

    def unsigned_payload(self) -> dict[str, Any]:
        payload = self.to_payload()
        payload.pop("signatures", None)
        return payload


def approval_signature_hex(approval: TrajectoryModeApprovalV2, key: bytes) -> str:
    if not key:
        raise ValueError("approval signing key is required")
    return hmac.new(key, canonical_json_bytes(approval.unsigned_payload()), hashlib.sha256).hexdigest()


def verify_approval_signatures(
    approval: TrajectoryModeApprovalV2,
    trusted_keys: Mapping[str, bytes],
) -> tuple[bool, tuple[str, ...]]:
    blockers: list[str] = []
    valid_by_role: dict[str, set[str]] = {"collector": set(), "reviewer": set()}
    for signature in approval.signatures:
        key = trusted_keys.get(signature.signer_id)
        if not key:
            blockers.append(f"UNTRUSTED_SIGNER:{signature.signer_id}")
            continue
        expected = approval_signature_hex(approval, key)
        if not hmac.compare_digest(expected, signature.signature_hex):
            blockers.append(f"INVALID_SIGNATURE:{signature.signer_id}")
            continue
        valid_by_role[signature.role].add(signature.signer_id)
    if not valid_by_role["collector"]:
        blockers.append("MISSING_COLLECTOR_SIGNATURE")
    if not valid_by_role["reviewer"]:
        blockers.append("MISSING_REVIEWER_SIGNATURE")
    if valid_by_role["collector"] & valid_by_role["reviewer"]:
        blockers.append("COLLECTOR_AND_REVIEWER_MUST_BE_DISTINCT")
    return not blockers, tuple(blockers)


__all__ = [
    "APPROVAL_SCHEMA", "DATASET_SCHEMA", "PROTOCOL_SCHEMA", "REPORT_SCHEMA",
    "ApprovalSignatureV2", "PhysicalValidationCaseV2", "PhysicalValidationDatasetV2",
    "PhysicalValidationProtocolV2", "ReferenceChannelV2", "TailErrorPolicyV2",
    "TrajectoryModeApprovalV2", "approval_signature_hex", "canonical_json_bytes",
    "payload_sha256", "verify_approval_signatures",
]
