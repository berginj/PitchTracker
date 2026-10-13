"""Research workspaces preserve source evidence and never activate approvals."""

from dataclasses import replace
import hashlib
import json
from pathlib import Path
from threading import Event

import pytest

from app.services.tooling import SubprocessToolingService
from app.services.tooling.research import evaluate_workspace, inspect_session, save_research_document
from contracts.research import MeasurementWorkspaceRequest, SessionInspectionRequest
from tests.test_physical_validation_v2 import _case, _dataset, _protocol


def _session(root: Path, records: list | None = None) -> Path:
    root.mkdir()
    journal = root / "evidence_journal"
    journal.mkdir()
    records = (
        records
        if records is not None
        else [
            {"sequence": 1, "stream": "FrameProcessingOpportunityEvent", "payload": {"opportunity_id": "one"}},
            {
                "sequence": 2,
                "stream": "FrameProcessingOutcomeEvent",
                "payload": {
                    "opportunity_id": "one",
                    "status": "QUEUE_DROPPED",
                    "frame_id": "left-1",
                },
            },
        ]
    )
    text = "".join(json.dumps(record) + "\n" for record in records)
    (journal / "records.jsonl").write_text(text)
    (journal / "manifest.json").write_text(
        json.dumps(
            {
                "complete": True,
                "file": "records.jsonl",
                "sha256": hashlib.sha256((journal / "records.jsonl").read_bytes()).hexdigest(),
                "records": len(records),
            }
        )
    )
    (root / "manifest.json").write_text(
        json.dumps(
            {
                "session_id": "research",
                "decision_evidence_complete": True,
                "decision_evidence_manifest": "evidence_journal/manifest.json",
            }
        )
    )
    return root


def test_inspection_reconciles_terminal_conservation_and_is_reproducible(tmp_path):
    root = _session(tmp_path / "session")
    request = SessionInspectionRequest(root)
    first = inspect_session(request)
    assert first.report == inspect_session(request).report
    assert first.correlation_id == request.correlation_id
    assert first.report["reconciliation"]["valid"]
    assert first.report["blockers"] == ["SETUP_SNAPSHOT_MISSING"]
    assert first.report["physical_claim_eligible"] is False


@pytest.mark.parametrize("kind", ["empty", "missing", "corrupt", "escape"])
def test_bad_or_absent_journals_are_not_successful_research_evidence(tmp_path, kind):
    root = _session(tmp_path / "session", [] if kind == "empty" else None)
    manifest = root / "evidence_journal" / "manifest.json"
    if kind == "missing":
        manifest.unlink()
    elif kind == "corrupt":
        (manifest.parent / "records.jsonl").write_text("tampered")
    elif kind == "escape":
        payload = json.loads(manifest.read_text())
        payload["file"] = "../../outside.jsonl"
        manifest.write_text(json.dumps(payload))
    result = inspect_session(SessionInspectionRequest(root))
    assert result.report["blockers"]
    assert result.report["physical_claim_eligible"] is False


def test_legacy_session_remains_inspectable_without_media(tmp_path):
    root = tmp_path / "legacy"
    root.mkdir()
    (root / "session_manifest.json").write_text('{"session_id":"old"}')
    report = inspect_session(SessionInspectionRequest(root)).report
    assert report["session_id"] == "old"
    assert "DECISION_JOURNAL_MISSING" in report["blockers"]


def test_journal_bindings_must_match_recorded_setup_inventory(tmp_path):
    from contracts.setup_snapshot import SetupSystemSnapshot

    root = _session(tmp_path / "session")
    path = root / "manifest.json"
    manifest = json.loads(path.read_text())
    snapshot = SetupSystemSnapshot.create(
        snapshot_id="snapshot",
        created_utc="2026-10-10T12:00:00Z",
        rig_profile_id="rig",
        rig_profile_revision=1,
        sections={},
        artifact_inventory={"config": "a" * 64},
    )
    manifest["calibration_report"] = {"setup_snapshot": snapshot.to_payload()}
    path.write_text(json.dumps(manifest))
    report = inspect_session(SessionInspectionRequest(root)).report
    assert not report["reconciliation"]["valid"]
    assert "required artifact binding missing: config_sha256" in report["reconciliation"]["errors"]


def test_recording_context_retains_independent_snapshot_copy(tmp_path, monkeypatch):
    from types import SimpleNamespace
    from app.services.orchestrator import service_startup

    snapshot = {"artifact_inventory": {"config": "a" * 64}}
    profile = SimpleNamespace(
        profile_id="research",
        profile_revision=3,
        setup_snapshot=snapshot,
        artifact_hashes={"config": "a" * 64},
    )
    service = SimpleNamespace(
        config_path=tmp_path / "config.yaml",
        load_active_or_legacy=lambda *_args, **_kwargs: profile,
        validate_for_runtime=lambda *_args, **_kwargs: SimpleNamespace(state="PASS", warnings=[]),
        apply_profile_to_config=lambda config, *_args, **_kwargs: config,
        calibration_path=lambda *_args: tmp_path / "calibration.npz",
        roi_path=lambda *_args: tmp_path / "roi.json",
    )
    monkeypatch.setattr(service_startup, "build_calibration_report", lambda *_args: {})
    from configs.settings import load_config
    result = service_startup.load_and_validate_rig(service, load_config(Path("configs/default.yaml")), "sim", "left", "right")
    snapshot["artifact_inventory"]["config"] = "b" * 64
    assert result.calibration_report["setup_snapshot"]["artifact_inventory"]["config"] == "a" * 64
    assert result.calibration_report["rig_profile_revision"] == 3


def test_workspace_keeps_overrides_and_shadow_data_ineligible(tmp_path):
    root = _session(tmp_path / "session")
    protocol = _protocol()
    dataset = _dataset(protocol, phase="shadow", cases=(_case(measured_speed_source="manual"),))
    request = MeasurementWorkspaceRequest(protocol.to_payload(), dataset.to_payload(), root)
    before = {path: path.read_bytes() for path in root.rglob("*") if path.is_file()}
    result = evaluate_workspace(request)
    blockers = result.report["evaluation"]["claim_blockers"]
    assert "SHADOW_DATASET_NOT_CLAIM_ELIGIBLE" in blockers
    assert any(item.startswith("SPEED_NOT_INDEPENDENT_VISION") for item in blockers)
    assert result.report["physical_claim_eligible"] is False
    assert before == {path: path.read_bytes() for path in before}


def test_research_save_preserves_session_and_existing_files(tmp_path):
    root = _session(tmp_path / "session")
    with pytest.raises(ValueError, match="outside"):
        save_research_document(root / "new.json", {}, root)
    output = tmp_path / "study.json"
    save_research_document(output, {"phase": "shadow"}, root)
    with pytest.raises(FileExistsError):
        save_research_document(output, {}, root)
    assert json.loads(output.read_text()) == {"phase": "shadow"}


def test_subprocess_session_inspection_contract(tmp_path):
    root = _session(tmp_path / "session")
    request = SessionInspectionRequest(root)
    result = SubprocessToolingService().inspect_measurement_session(request, Event())
    assert result.correlation_id == request.correlation_id
    assert result.report == inspect_session(request).report


def test_workspace_rejects_invalid_reference_values(tmp_path):
    protocol = _protocol()
    dataset = _dataset(protocol, phase="shadow").to_payload()
    dataset["cases"][0]["reference_speed_uncertainty_mph"] = -1
    with pytest.raises(ValueError, match="non-negative"):
        evaluate_workspace(MeasurementWorkspaceRequest(protocol.to_payload(), dataset, tmp_path))


def test_missing_reference_attempts_remain_in_denominators(tmp_path):
    protocol = _protocol()
    case = replace(_case(), system_outcome="UNAVAILABLE", measured_speed_mph=None, measured_plate_xy_ft=None)
    dataset = _dataset(protocol, phase="shadow", cases=(case,))
    result = evaluate_workspace(
        MeasurementWorkspaceRequest(protocol.to_payload(), dataset.to_payload(), _session(tmp_path / "session"))
    )
    metrics = result.report["evaluation"]["metrics"]
    assert metrics["reference_valid_count"] == 1
    assert metrics["unavailable_count"] == 1


def test_shadow_protocol_hash_can_be_bound_without_rewriting_confirmation(tmp_path):
    root = _session(tmp_path / "session")
    protocol = _protocol()
    dataset = _dataset(protocol, phase="shadow").to_payload()
    dataset["protocol_sha256"] = ""
    request = MeasurementWorkspaceRequest(protocol.to_payload(), dataset, root)
    result = evaluate_workspace(request)
    assert result.report["dataset"]["protocol_sha256"] == protocol.protocol_sha256
    assert request.dataset["protocol_sha256"] == ""
    dataset["phase"] = "confirmation"
    with pytest.raises(ValueError, match="protocol_sha256"):
        evaluate_workspace(MeasurementWorkspaceRequest(protocol.to_payload(), dataset, root))


def test_passing_conditional_confirmation_is_not_a_workspace_accuracy_approval(tmp_path):
    root = _session(tmp_path / "session")
    protocol = _protocol()
    dataset = _dataset(protocol)
    report = evaluate_workspace(MeasurementWorkspaceRequest(protocol.to_payload(), dataset.to_payload(), root)).report
    assert report["evaluation"]["claim_ready"] is True
    assert report["physical_claim_eligible"] is False
    assert any(item.startswith("CASE_EVIDENCE_NOT_IN_SELECTED_SESSION") for item in report["workspace_blockers"])


@pytest.mark.parametrize("field", ["uncertainty", "time_uncertainty_ms"])
def test_nonfinite_reference_uncertainty_is_rejected(field):
    from tests.test_physical_validation_v2 import _reference

    with pytest.raises(ValueError, match="finite"):
        replace(_reference(), **{field: float("nan")})
