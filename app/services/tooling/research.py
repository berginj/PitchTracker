"""Read-only session inspection and independent measurement evaluation."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
from typing import Any

from app.pipeline.recording.evidence_journal import load_session_evidence_journal
from app.pipeline.replay.decision_replay import reconcile_decision_journal
from calib.physical_validation import evaluate_physical_validation
from contracts.physical_validation import PhysicalValidationDatasetV2, PhysicalValidationProtocolV2, payload_sha256
from contracts.research import MeasurementWorkspaceRequest, ResearchToolResult, SessionInspectionRequest
from contracts.setup_snapshot import SetupSystemSnapshot, assess_setup_snapshot_payload


def contained_path(root: Path, relative: str) -> Path:
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Artifact path escapes the selected session")
    return path


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Expected a JSON object")
    return value


def inspect_session(request: SessionInspectionRequest) -> ResearchToolResult:
    root = request.session_dir.resolve(strict=True)
    if not root.is_dir():
        raise ValueError("Select a session directory")
    blockers: list[str] = []
    manifest_path = next(
        (root / name for name in ("manifest.json", "session_manifest.json") if (root / name).is_file()), None
    )
    manifest = load_object(manifest_path) if manifest_path else {}
    if not manifest:
        blockers.append("SESSION_MANIFEST_MISSING")
    context = manifest.get("calibration_report") or {}
    snapshot = context.get("setup_snapshot") if isinstance(context, dict) else None
    inventory_hashes = (snapshot.get("artifact_inventory") or {}) if isinstance(snapshot, dict) else {}
    expected_bindings = {
        binding: str(inventory_hashes[artifact])
        for artifact, binding in (
            ("config", "config_sha256"),
            ("calibration", "calibration_sha256"),
            ("roi", "roi_sha256"),
            ("detector_model", "model_sha256"),
        )
        if inventory_hashes.get(artifact)
    }
    inventory = []
    pitches = []
    # Deliberately inspect metadata only; videos remain local and are not loaded.
    for path in sorted(root.rglob("*.json")):
        contained_path(root, str(path.relative_to(root)))
        inventory.append(
            {"file": path.relative_to(root).as_posix(), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        )
        if path.name in {"manifest.json", "pitch_manifest.json"} and path.parent.name.startswith("pitch_"):
            pitch = load_object(path)
            pitches.append(
                {
                    key: pitch.get(key)
                    for key in (
                        "pitch_id",
                        "measurement_status",
                        "vision_speed",
                        "external_speed",
                        "trajectory",
                        "quality_diagnostics",
                    )
                }
            )
    journal_name = manifest.get("decision_evidence_manifest") or "evidence_journal/manifest.json"
    journal_path = contained_path(root, str(journal_name))
    replay: dict[str, Any] | None = None
    if not journal_path.is_file():
        blockers.append("DECISION_JOURNAL_MISSING")
    else:
        try:
            records = load_session_evidence_journal(journal_path)
            replay = asdict(reconcile_decision_journal(records, expected_bindings=expected_bindings))
            replay["errors"] = list(replay["errors"])
            if not records or not replay["metrics"]["frame_conservation"]["offered"]:
                blockers.append("DECISION_JOURNAL_HAS_NO_OPPORTUNITIES")
            if not replay["valid"]:
                blockers.append("DECISION_RECONCILIATION_FAILED")
        except (ValueError, KeyError, OSError) as exc:
            blockers.append(f"DECISION_JOURNAL_INVALID: {exc}")
    if manifest.get("decision_evidence_complete") is not True:
        blockers.append("SESSION_DECISION_EVIDENCE_NOT_COMPLETE")
    snapshot_assessment = None
    if not snapshot:
        blockers.append("SETUP_SNAPSHOT_MISSING")
    else:
        snapshot_assessment = assess_setup_snapshot_payload(snapshot).to_payload()
        if not SetupSystemSnapshot.from_payload(snapshot).verify_fingerprint():
            blockers.append("SETUP_SNAPSHOT_FINGERPRINT_INVALID")
        if not snapshot_assessment["configuration_evidence_complete"]:
            blockers.append("SETUP_SNAPSHOT_INCOMPLETE")
    report = {
        "schema_version": "measurement_session_inspection.v1",
        "session_id": manifest.get("session_id"),
        "inventory": inventory,
        "pitches": pitches,
        "calibration_report": manifest.get("calibration_report"),
        "setup_snapshot_assessment": snapshot_assessment,
        "reconciliation": replay,
        "blockers": blockers,
        "physical_claim_eligible": False,
    }
    report["content_sha256"] = payload_sha256(report)
    return ResearchToolResult(report, request.correlation_id)


def evaluate_workspace(request: MeasurementWorkspaceRequest) -> ResearchToolResult:
    protocol = PhysicalValidationProtocolV2.from_payload(request.protocol)
    dataset_payload = dict(request.dataset)
    if dataset_payload.get("phase") == "shadow" and not dataset_payload.get("protocol_sha256"):
        dataset_payload["protocol_sha256"] = protocol.protocol_sha256
    dataset = PhysicalValidationDatasetV2.from_payload(dataset_payload)
    inspection = inspect_session(SessionInspectionRequest(request.session_dir, request.correlation_id)).report
    report = evaluate_physical_validation(protocol, dataset)
    workspace_blockers = list(inspection["blockers"])
    known_hashes = {item["sha256"] for item in inspection["inventory"]}
    for case in dataset.cases:
        if case.evidence_package_sha256 not in known_hashes:
            workspace_blockers.append(f"CASE_EVIDENCE_NOT_IN_SELECTED_SESSION:{case.case_id}")
    # Evaluation is diagnostic. It never creates an approval or substitutes for
    # independent review of raw references and exact rig/software bindings.
    return ResearchToolResult(
        {
            "schema_version": "measurement_workspace.v1",
            "protocol": protocol.to_payload(),
            "dataset": dataset.to_payload(),
            "evaluation": report,
            "session_inspection": inspection,
            "workspace_blockers": workspace_blockers,
            "physical_claim_eligible": False,
        },
        request.correlation_id,
    )


def save_research_document(
    path: Path, payload: dict[str, Any], session_dir: Path, *, source_paths: tuple[Path, ...] = ()
) -> None:
    """Create a new research artifact without overwriting captured evidence."""
    target = path.resolve()
    if target.is_relative_to(session_dir.resolve()) or target in {item.resolve() for item in source_paths}:
        raise ValueError("Save research artifacts outside the source session and imported files")
    if target.suffix.lower() != ".json":
        raise ValueError("Research artifacts must be JSON files")
    text = json.dumps(payload, sort_keys=True, indent=2, allow_nan=False) + "\n"
    with target.open("x", encoding="utf-8") as handle:
        handle.write(text)
