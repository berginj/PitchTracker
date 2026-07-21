"""Canonical setup-system snapshot and fail-closed completeness assessment."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Mapping


SETUP_SNAPSHOT_SCHEMA = "setup_system_snapshot.v2"


def canonical_payload_sha256(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


@dataclass(frozen=True)
class SetupSnapshotAssessment:
    """Completeness and eligibility result for one immutable setup snapshot."""

    structurally_complete: bool
    configuration_evidence_complete: bool
    operationally_eligible: bool
    missing_fields: tuple[str, ...] = ()
    invalid_fields: tuple[str, ...] = ()
    unavailable_fields: tuple[str, ...] = ()
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()

    def to_payload(self) -> dict[str, Any]:
        return {
            "structurally_complete": self.structurally_complete,
            "configuration_evidence_complete": self.configuration_evidence_complete,
            "operationally_eligible": self.operationally_eligible,
            "missing_fields": list(self.missing_fields),
            "invalid_fields": list(self.invalid_fields),
            "unavailable_fields": list(self.unavailable_fields),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SetupSnapshotAssessment":
        return cls(
            structurally_complete=bool(payload.get("structurally_complete")),
            configuration_evidence_complete=bool(payload.get("configuration_evidence_complete")),
            operationally_eligible=bool(payload.get("operationally_eligible")),
            missing_fields=tuple(str(item) for item in payload.get("missing_fields", ())),
            invalid_fields=tuple(str(item) for item in payload.get("invalid_fields", ())),
            unavailable_fields=tuple(str(item) for item in payload.get("unavailable_fields", ())),
            blockers=tuple(str(item) for item in payload.get("blockers", ())),
            warnings=tuple(str(item) for item in payload.get("warnings", ())),
        )


@dataclass(frozen=True)
class SetupSystemSnapshot:
    """Content-addressed inventory of the exact system configured by setup."""

    snapshot_id: str
    created_utc: str
    rig_profile_id: str
    rig_profile_revision: int
    sections: dict[str, Any]
    artifact_inventory: dict[str, str]
    assessment: SetupSnapshotAssessment
    fingerprint_sha256: str
    schema_version: str = SETUP_SNAPSHOT_SCHEMA

    def unsigned_payload(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "snapshot_id": self.snapshot_id,
            "created_utc": self.created_utc,
            "rig_profile_id": self.rig_profile_id,
            "rig_profile_revision": self.rig_profile_revision,
            "sections": self.sections,
            "artifact_inventory": self.artifact_inventory,
            "assessment": self.assessment.to_payload(),
        }

    def to_payload(self) -> dict[str, Any]:
        return {**self.unsigned_payload(), "fingerprint_sha256": self.fingerprint_sha256}

    def verify_fingerprint(self) -> bool:
        return canonical_payload_sha256(self.unsigned_payload()) == self.fingerprint_sha256

    @classmethod
    def create(
        cls,
        *,
        snapshot_id: str,
        created_utc: str,
        rig_profile_id: str,
        rig_profile_revision: int,
        sections: Mapping[str, Any],
        artifact_inventory: Mapping[str, str],
    ) -> "SetupSystemSnapshot":
        section_payload = dict(sections)
        artifact_payload = {str(key): str(value) for key, value in artifact_inventory.items()}
        assessment = assess_setup_snapshot_sections(section_payload, artifact_payload)
        provisional = cls(
            snapshot_id=snapshot_id,
            created_utc=created_utc,
            rig_profile_id=rig_profile_id,
            rig_profile_revision=rig_profile_revision,
            sections=section_payload,
            artifact_inventory=artifact_payload,
            assessment=assessment,
            fingerprint_sha256="",
        )
        return cls(**{**provisional.__dict__, "fingerprint_sha256": canonical_payload_sha256(provisional.unsigned_payload())})

    @classmethod
    def from_payload(cls, payload: Mapping[str, Any]) -> "SetupSystemSnapshot":
        if str(payload.get("schema_version")) != SETUP_SNAPSHOT_SCHEMA:
            raise ValueError(f"unsupported setup snapshot schema: {payload.get('schema_version')!r}")
        result = cls(
            snapshot_id=str(payload.get("snapshot_id") or ""),
            created_utc=str(payload.get("created_utc") or ""),
            rig_profile_id=str(payload.get("rig_profile_id") or ""),
            rig_profile_revision=int(payload.get("rig_profile_revision") or 0),
            sections=dict(payload.get("sections") or {}),
            artifact_inventory={str(key): str(value) for key, value in dict(payload.get("artifact_inventory") or {}).items()},
            assessment=SetupSnapshotAssessment.from_payload(dict(payload.get("assessment") or {})),
            fingerprint_sha256=str(payload.get("fingerprint_sha256") or ""),
            schema_version=str(payload.get("schema_version")),
        )
        if not result.snapshot_id or not result.rig_profile_id or result.rig_profile_revision < 1:
            raise ValueError("setup snapshot identity is incomplete")
        return result


_REQUIRED_SECTIONS = (
    "rig",
    "software",
    "host",
    "cameras",
    "capture_qualification",
    "geometry",
    "detection_tracking",
    "trajectory_corrections",
    "validation",
)

_REQUIRED_VALUES = (
    "rig.backend",
    "rig.camera_serials.left",
    "rig.camera_serials.right",
    "software.app_version",
    "software.source_revision",
    "host.os",
    "host.python_version",
    "cameras.left.hardware_id",
    "cameras.left.friendly_name",
    "cameras.right.hardware_id",
    "cameras.right.friendly_name",
    "cameras.left.negotiated_mode.width",
    "cameras.left.negotiated_mode.height",
    "cameras.left.negotiated_mode.fps",
    "cameras.right.negotiated_mode.width",
    "cameras.right.negotiated_mode.height",
    "cameras.right.negotiated_mode.fps",
    "capture_qualification.assessment.status",
    "geometry.calibration.sha256",
    "geometry.roi.sha256",
    "geometry.field_transform.sha256",
    "detection_tracking.config_sha256",
    "detection_tracking.association.algorithm",
    "trajectory_corrections.primary_mode",
    "trajectory_corrections.correction_policy_sha256",
)

_REQUIRED_TRUE = (
    "cameras.left.recognized",
    "cameras.left.global_shutter",
    "cameras.left.controls_readback.readback_verified",
    "cameras.right.recognized",
    "cameras.right.global_shutter",
    "cameras.right.controls_readback.readback_verified",
    "geometry.calibration.production_ready",
    "geometry.field_transform.passed",
)


def assess_setup_snapshot_sections(
    sections: Mapping[str, Any], artifact_inventory: Mapping[str, str]
) -> SetupSnapshotAssessment:
    missing: list[str] = [name for name in _REQUIRED_SECTIONS if name not in sections]
    invalid: list[str] = []
    blockers: list[str] = []
    unavailable = tuple(sorted(str(item) for item in sections.get("inventory_unavailable", ())))

    for path in _REQUIRED_VALUES:
        found, value = _lookup(sections, path)
        if not found or value is None or value == "":
            missing.append(path)
    for path in _REQUIRED_TRUE:
        found, value = _lookup(sections, path)
        if not found:
            missing.append(path)
        elif value is not True:
            invalid.append(path)

    capture = sections.get("capture_qualification") or {}
    if int(capture.get("frame_count_left") or 0) < 1:
        invalid.append("capture_qualification.frame_count_left")
    if int(capture.get("frame_count_right") or 0) < 1:
        invalid.append("capture_qualification.frame_count_right")
    if int(capture.get("paired_count") or 0) < 1:
        invalid.append("capture_qualification.paired_count")
    status = str(((capture.get("assessment") or {}).get("status") or "")).upper()
    if status not in {"PASS", "ESTIMATED", "VALIDATED"}:
        invalid.append("capture_qualification.assessment.status")

    for label in ("calibration", "roi", "field_transform", "config"):
        digest = artifact_inventory.get(label)
        if not _is_sha256(digest):
            invalid.append(f"artifact_inventory.{label}")

    if missing:
        blockers.append("SETUP_SNAPSHOT_REQUIRED_FIELDS_MISSING")
    if invalid:
        blockers.append("SETUP_SNAPSHOT_REQUIRED_FIELDS_INVALID")
    if sections.get("software", {}).get("working_tree_dirty") is True:
        blockers.append("SOFTWARE_WORKTREE_DIRTY")
    source_revision = str(sections.get("software", {}).get("source_revision") or "")
    if not (
        len(source_revision) in {40, 64}
        and all(char.lower() in "0123456789abcdef" for char in source_revision)
    ):
        invalid.append("software.source_revision")
        blockers.append("SOFTWARE_SOURCE_REVISION_UNVERIFIED")

    structurally_complete = not missing
    configuration_complete = structurally_complete and not invalid and not blockers
    return SetupSnapshotAssessment(
        structurally_complete=structurally_complete,
        configuration_evidence_complete=configuration_complete,
        operationally_eligible=configuration_complete,
        missing_fields=tuple(sorted(set(missing))),
        invalid_fields=tuple(sorted(set(invalid))),
        unavailable_fields=unavailable,
        blockers=tuple(dict.fromkeys(blockers)),
        warnings=tuple(f"INVENTORY_UNAVAILABLE:{item}" for item in unavailable),
    )


def assess_setup_snapshot_payload(payload: Mapping[str, Any]) -> SetupSnapshotAssessment:
    try:
        snapshot = SetupSystemSnapshot.from_payload(payload)
    except (TypeError, ValueError) as exc:
        return SetupSnapshotAssessment(
            False,
            False,
            False,
            blockers=("SETUP_SNAPSHOT_INVALID",),
            invalid_fields=(str(exc),),
        )
    assessment = assess_setup_snapshot_sections(snapshot.sections, snapshot.artifact_inventory)
    if not snapshot.verify_fingerprint():
        return SetupSnapshotAssessment(
            assessment.structurally_complete,
            False,
            False,
            assessment.missing_fields,
            tuple((*assessment.invalid_fields, "fingerprint_sha256")),
            assessment.unavailable_fields,
            tuple((*assessment.blockers, "SETUP_SNAPSHOT_FINGERPRINT_MISMATCH")),
            assessment.warnings,
        )
    return assessment


def _lookup(payload: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    current: Any = payload
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return False, None
        current = current[part]
    return True, current


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(char in "0123456789abcdef" for char in value)


__all__ = [
    "SETUP_SNAPSHOT_SCHEMA",
    "SetupSnapshotAssessment",
    "SetupSystemSnapshot",
    "assess_setup_snapshot_payload",
    "assess_setup_snapshot_sections",
    "canonical_payload_sha256",
]
