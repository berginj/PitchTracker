import json
from pathlib import Path

from jsonschema import Draft202012Validator, validate

from contracts import Detection, Frame, PitchMetrics, StereoObservation, TrackSample
from contracts.versioning import SCHEMA_VERSION


ROOT = Path(__file__).resolve().parents[1]
SHARED_CONTRACTS = ROOT / "contracts-shared"


def _load_json(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def test_contracts_instantiation() -> None:
    frame = Frame(
        camera_id="left",
        frame_index=1,
        t_capture_monotonic_ns=123,
        image=None,
        width=1920,
        height=1080,
        pixfmt="GRAY8",
    )
    detection = Detection(
        camera_id="left",
        frame_index=1,
        t_capture_monotonic_ns=123,
        u=100.0,
        v=200.0,
        radius_px=5.0,
        confidence=0.9,
    )
    stereo = StereoObservation(
        t_ns=123,
        left=(100.0, 200.0),
        right=(95.0, 200.0),
        X=1.0,
        Y=2.0,
        Z=50.0,
        quality=0.9,
        confidence=0.9,
    )
    track = TrackSample(
        t_ns=123,
        X=1.0,
        Y=2.0,
        Z=50.0,
        Vx=0.1,
        Vy=0.2,
        Vz=-30.0,
    )
    metrics = PitchMetrics(
        pitch_id="test",
        t_start_ns=0,
        t_end_ns=1,
        velo_mph=90.0,
        HB_in=5.0,
        iVB_in=10.0,
        release_xyz_ft=(0.0, 6.0, 50.0),
        approach_angles_deg=(1.0, -5.0),
        confidence=0.8,
    )

    assert frame.camera_id == "left"
    assert detection.camera_id == "left"
    assert stereo.Z == 50.0
    assert track.Vz == -30.0
    assert metrics.pitch_id == "test"


def test_schema_version_files_match_runtime_constant() -> None:
    shared_version = _load_json(SHARED_CONTRACTS / "schema" / "version.json")
    root_version = _load_json(ROOT / "schema" / "version.json")

    assert shared_version["schema_version"] == SCHEMA_VERSION
    assert root_version["schema_version"] == SCHEMA_VERSION


def test_root_and_shared_session_summary_schemas_match() -> None:
    shared_schema = _load_json(SHARED_CONTRACTS / "schema" / "session_summary.schema.json")
    root_schema = _load_json(ROOT / "schema" / "session_summary.schema.json")

    assert root_schema == shared_schema


def test_published_schemas_are_valid_json_schema() -> None:
    schema_paths = [
        SHARED_CONTRACTS / "schema" / "session_summary.schema.json",
        SHARED_CONTRACTS / "schema" / "session_upload.schema.json",
        SHARED_CONTRACTS / "schema" / "training_report.schema.json",
        SHARED_CONTRACTS / "schema" / "marker_spec.schema.json",
        ROOT / "schema" / "session_summary.schema.json",
    ]

    for schema_path in schema_paths:
        Draft202012Validator.check_schema(_load_json(schema_path))


def test_published_contract_examples_validate_against_schemas() -> None:
    session_summary_schema = _load_json(SHARED_CONTRACTS / "schema" / "session_summary.schema.json")
    training_report_schema = _load_json(SHARED_CONTRACTS / "schema" / "training_report.schema.json")
    session_upload_schema = _load_json(SHARED_CONTRACTS / "schema" / "session_upload.schema.json")
    marker_spec_schema = _load_json(SHARED_CONTRACTS / "schema" / "marker_spec.schema.json")

    session_summary = _load_json(SHARED_CONTRACTS / "examples" / "session_summary.sample.json")
    training_report = _load_json(SHARED_CONTRACTS / "examples" / "training_report.sample.json")
    marker_spec = _load_json(SHARED_CONTRACTS / "examples" / "marker_spec.json")

    validate(instance=session_summary, schema=session_summary_schema)
    validate(instance=training_report, schema=training_report_schema)
    validate(instance=marker_spec, schema=marker_spec_schema)

    session_upload = {
        "schema_version": SCHEMA_VERSION,
        "app_version": "1.5.0",
        "session": {
            "session_id": session_summary["session_id"],
            "pitch_count": session_summary["pitch_count"],
            "strikes": session_summary["strikes"],
            "balls": session_summary["balls"],
            "heatmap": session_summary["heatmap"],
            "pitches": session_summary["pitches"],
        },
        "metadata": {
            "uploaded_utc": "2026-03-06T00:00:00Z",
            "pitcher": "sample pitcher",
            "location_profile": "lane-1",
            "rig_id": None,
            "source": "PitchTracker",
        },
        "marker_spec": marker_spec,
    }

    validate(instance=session_upload, schema=session_upload_schema)
