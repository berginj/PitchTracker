"""Authoritative ownership map for persisted PitchTracker contracts.

This registry is intentionally metadata-only. Producers still own their
serialization details, while this table gives contributors and automated
checks one place to discover the durable artifact name, schema identifier, and
owning module.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from .setup_capture import SETUP_CAPTURE_SCHEMA_VERSION
from .setup_snapshot import SETUP_SNAPSHOT_SCHEMA


@dataclass(frozen=True)
class DurableContractSpec:
    artifact: str
    schema_version: str
    owner: str
    schema_path: str | None = None


DURABLE_CONTRACTS: Mapping[str, DurableContractSpec] = {
    "session_summary": DurableContractSpec(
        artifact="session_summary",
        schema_version="session_summary.v1",
        owner="app.contracts.SessionSummary",
        schema_path="contracts-shared/schema/session_summary.schema.json",
    ),
    "setup_capture": DurableContractSpec(
        artifact="setup_capture",
        schema_version=SETUP_CAPTURE_SCHEMA_VERSION,
        owner="contracts.setup_capture.SetupCaptureResult",
    ),
    "setup_snapshot": DurableContractSpec(
        artifact="setup_snapshot",
        schema_version=SETUP_SNAPSHOT_SCHEMA,
        owner="contracts.setup_snapshot.SetupSystemSnapshot",
    ),
    "evidence_package": DurableContractSpec(
        artifact="evidence_package",
        schema_version="evidence_package.v2",
        owner="app.pipeline.recording.evidence_package.EvidencePackageWriter",
    ),
    "decision_journal": DurableContractSpec(
        artifact="decision_journal",
        schema_version="decision_journal.v1",
        owner="app.pipeline.recording.evidence_journal.SessionEvidenceJournal",
    ),
}


def validate_durable_contracts(root: Path | None = None) -> tuple[str, ...]:
    """Return registry violations without importing producer implementations."""
    errors: list[str] = []
    keys = list(DURABLE_CONTRACTS)
    if len(keys) != len(set(keys)):
        errors.append("durable contract keys must be unique")
    for key, spec in DURABLE_CONTRACTS.items():
        if key != spec.artifact:
            errors.append(f"registry key {key!r} does not match artifact {spec.artifact!r}")
        if not spec.schema_version:
            errors.append(f"{key} has no schema version")
        if not spec.owner:
            errors.append(f"{key} has no owner")
        if spec.schema_path is not None:
            schema_root = Path.cwd() if root is None else root
            if not (schema_root / spec.schema_path).is_file():
                errors.append(f"{key} schema path is missing: {spec.schema_path}")
    return tuple(errors)


__all__ = ["DURABLE_CONTRACTS", "DurableContractSpec", "validate_durable_contracts"]
