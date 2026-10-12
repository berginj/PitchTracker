"""Fresh setup, atomic edits, geometry checks, and recording admission."""

import hashlib
from pathlib import Path

import numpy as np
import pytest
import yaml

from app.services.setup_workflow import SetupWorkflowService
from app.services.setup_workflow.runtime_access import reserve_recording, release_recording
from app.services.setup_workflow.storage import recording_blockers
from contracts.setup_capture import SetupCapturePurpose, SetupCaptureResult, SetupFrameRecord


def _new_workflow(tmp_path):
    payload = yaml.safe_load((Path(__file__).parents[1] / "configs/default.yaml").read_text())
    payload["camera"]["color_mode"] = False
    config = tmp_path / "configs/default.yaml"
    config.parent.mkdir()
    config.write_text(yaml.safe_dump(payload))
    return SetupWorkflowService(config, tmp_path / "calibration/rigs", backend="sim")


@pytest.fixture
def workflow(tmp_path):
    return _new_workflow(tmp_path)


def _calibration(workflow, tmp_path):
    path = tmp_path / "metric.npz"
    matrix = np.array([[1000., 0, 640], [0, 1000, 360], [0, 0, 1]])
    np.savez(
        path, mtx_left=matrix, mtx_right=matrix, dist_left=np.zeros(5), dist_right=np.zeros(5),
        R=np.eye(3), T=np.array([[-304.8], [0], [0]]), img_size=np.array([1280, 720]),
        calibration_mode="FULL", production_ready=True, rms_error_px=0.4, quality_rating="GOOD",
        baseline_ft=1.0, num_images_used=12,
    )
    return path


def _capture(workflow, tmp_path, purpose=SetupCapturePurpose.CHECKS):
    config = workflow.config
    random = np.random.default_rng(42)
    image = random.integers(0, 255, (config.camera.height, config.camera.width), dtype=np.uint8)
    left_path, right_path = tmp_path / "left.npy", tmp_path / "right.npy"
    np.save(left_path, image)
    np.save(right_path, np.roll(image, 10, axis=1))
    count = 60 if purpose == SetupCapturePurpose.CHECKS else 1
    streams = {}
    for side, path in (("left", left_path), ("right", right_path)):
        streams[side] = tuple(SetupFrameRecord(
            workflow.state["camera_ids"][side], index, 1_000_000_000 + index * 16_666_667,
            config.camera.width, config.camera.height, "GRAY8", path if index == count - 1 else None,
        ) for index in range(count))
    mode = {"width": config.camera.width, "height": config.camera.height, "fps": config.camera.fps, "pixfmt": "GRAY8"}
    control = {"readback_verified": True, "autofocus_disabled": True,
               "auto_exposure_disabled": True, "auto_white_balance_disabled": True}
    return SetupCaptureResult(
        "synthetic-capture", purpose, workflow.generation, 1, 2, count,
        streams["left"], streams["right"], {"left": mode, "right": mode}, {"left": control, "right": control},
        errors_by_side={"left": 0, "right": 0},
        config_sha256=hashlib.sha256(workflow.config_path.read_bytes()).hexdigest(),
    )


def _targets(workflow, *, bad_holdout=False):
    points = [(0, 0, 10), (1, 0, 10), (0, 1, 10), (1, 1, 12)]
    targets = []
    pair = workflow.state["latest_pair"]
    for index, (x, y, z) in enumerate(points):
        targets.append({
            "target_id": str(index), "left_pixel": [640 + 1000 * x / z, 360 + 1000 * y / z],
            "right_pixel": [640 + 1000 * (x - 1) / z, 360 + 1000 * y / z],
            "field_xyz_ft": [x + 2 + (1 if bad_holdout and index == 3 else 0), y + 3, z - 10],
            "holdout": index == 3, "source_pair": pair,
            "calibration_sha256": workflow.artifact("calibration").stem,
        })
    return targets


def _complete(workflow, tmp_path):
    workflow.assign("left", "right")
    diagnostics = workflow.apply_capture_result(_capture(workflow, tmp_path))
    assert workflow.state["checks"]["images"]["passed"], diagnostics
    workflow.accept_calibration(_calibration(workflow, tmp_path), generated=True)
    workflow.apply_capture_result(_capture(workflow, tmp_path, SetupCapturePurpose.FIELD_PAIR))
    workflow.update_targets(_targets(workflow))
    workflow.fit_field()
    for side in ("left", "right"):
        for kind in ("lane", "plate"):
            workflow.save_region(side, kind, [[10, 10], [300, 10], [300, 200], [10, 200]])
    workflow.validate_regions()
    assert workflow.readiness().permits_recording


def test_fresh_setup_creates_all_artifacts_and_consistent_runtime_config(workflow, tmp_path):
    assert not (tmp_path / "calibration/stereo_calibration.npz").exists()
    _complete(workflow, tmp_path)
    profile_id = workflow.finish()
    profile = workflow.rigs.load_active()
    assert profile.profile_id == profile_id
    assert profile.stereo_profile.production_ready
    assert profile.field_transform["holdout_passed"]
    assert not profile.trajectory_mode_approvals
    assert workflow.rigs.effective_config_path(profile).exists()
    validation = workflow.rigs.validate_for_runtime(profile, config=workflow.config, backend="sim")
    assert not validation.is_critical, validation.issues
    assert not validation.diagnostics["trajectory_accuracy_claim_eligible"]
    from app.services.orchestrator.service_startup import load_and_validate_rig
    runtime = load_and_validate_rig(workflow.rigs, workflow.config, "sim", "left", "right")
    assert runtime.config.camera == workflow.config.camera
    assert runtime.config.stereo.baseline_ft == 1.0
    assert not recording_blockers(workflow.rigs.base_dir, profile_id)
    published_bytes = workflow.rigs.profile_path(profile_id).read_bytes()
    reopened = SetupWorkflowService(workflow.rigs.config_path, workflow.rigs.base_dir)
    assert not reopened.readiness().permits_recording  # fresh visit checks
    reopened.update_settings("camera", {"exposure_us": 3000})
    assert recording_blockers(workflow.rigs.base_dir, profile_id)
    assert published_bytes == workflow.rigs.profile_path(profile_id).read_bytes()


def test_valid_edits_save_immediately_and_survive_reopen(workflow):
    original = workflow.rigs.config_path.read_bytes()
    workflow.assign("left", "right")
    workflow.update_settings("camera", {"exposure_us": 3500})
    reopened = SetupWorkflowService(workflow.rigs.config_path, workflow.rigs.base_dir, backend="sim")
    assert reopened.config.camera.exposure_us == 3500
    assert reopened.state["camera_ids"] == {"left": "left", "right": "right"}
    assert workflow.rigs.config_path.read_bytes() == original
    assert recording_blockers(workflow.rigs.base_dir, None)


def test_failed_state_write_keeps_previous_durable_settings(workflow, monkeypatch):
    before = workflow.state
    before_file = (workflow.root / "state.json").read_bytes()
    monkeypatch.setattr("app.services.setup_workflow.service.save_state",
                        lambda *_args: (_ for _ in ()).throw(OSError("disk full")))
    with pytest.raises(OSError, match="disk full"):
        workflow.update_settings("camera", {"gain": 2.0})
    assert workflow.state == before
    assert (workflow.root / "state.json").read_bytes() == before_file
    assert not workflow.readiness().permits_recording


@pytest.mark.parametrize("change,invalid", [
    ({"exposure_us": 5000}, {"images"}), ({"width": 640}, {"images", "calibration", "field", "regions"}),
    ({"flip_right": True}, {"images", "calibration", "field", "regions"}),
])
def test_changes_invalidate_their_dependent_checks(workflow, change, invalid):
    for name in ("images", "calibration", "field", "regions"):
        workflow.record_check(name, True, {}, workflow.generation)
    workflow.update_settings("camera", change)
    assert invalid.isdisjoint(workflow.state["checks"])
    for check in workflow.state["checks"].values():
        assert check["generation"] == workflow.generation


def test_stale_capture_cannot_restore_readiness(workflow, tmp_path):
    workflow.assign("left", "right")
    result = _capture(workflow, tmp_path)
    workflow.update_settings("camera", {"gain": 1.0})
    with pytest.raises(ValueError, match="earlier"):
        workflow.apply_capture_result(result)
    assert "images" not in workflow.state["checks"]


def test_recording_admission_and_edit_ownership(workflow):
    owner = id(workflow)
    reserve_recording(owner, workflow.rigs.base_dir, None)
    try:
        with pytest.raises(RuntimeError, match="End the recording"):
            workflow.update_settings("camera", {"gain": 3.0})
    finally:
        release_recording(owner)
    workflow.update_settings("camera", {"gain": 3.0})
    with pytest.raises(RuntimeError, match="Finish Setup"):
        reserve_recording(owner, workflow.rigs.base_dir, None)


def test_bad_holdout_blocks_publication(workflow, tmp_path):
    workflow.assign("left", "right")
    workflow.accept_calibration(_calibration(workflow, tmp_path), generated=True)
    workflow.apply_capture_result(_capture(workflow, tmp_path, SetupCapturePurpose.FIELD_PAIR))
    workflow.update_targets(_targets(workflow, bad_holdout=True))
    with pytest.raises(ValueError, match="holdout"):
        workflow.fit_field()
    assert not workflow.state["checks"]["field"]["passed"]
    assert not workflow.rigs.active_marker.exists()


def test_import_with_missing_provenance_is_diagnostic_and_preserves_source(workflow, tmp_path):
    workflow.assign("left", "right")
    source = _calibration(workflow, tmp_path)
    original = source.read_bytes()
    with pytest.raises(ValueError, match="provenance"):
        workflow.accept_calibration(source)
    assert source.read_bytes() == original
    assert not workflow.state["checks"]["calibration"]["passed"]


def test_bad_dimensions_and_regions_block_checks(workflow, tmp_path):
    workflow.assign("left", "right")
    workflow.accept_calibration(_calibration(workflow, tmp_path), generated=True)
    workflow.update_settings("camera", {"width": 640})
    with pytest.raises(ValueError, match="dimensions"):
        workflow.validate_calibration()
    with pytest.raises(ValueError, match="inside"):
        workflow.save_region("left", "lane", [[0, 0], [1000, 0], [1000, 100]])


def test_duplicate_holdout_cannot_be_counted_as_independent(workflow, tmp_path):
    workflow.assign("left", "right")
    workflow.accept_calibration(_calibration(workflow, tmp_path), generated=True)
    workflow.apply_capture_result(_capture(workflow, tmp_path, SetupCapturePurpose.FIELD_PAIR))
    targets = _targets(workflow)
    targets[-1].update(left_pixel=targets[0]["left_pixel"], right_pixel=targets[0]["right_pixel"])
    workflow.update_targets(targets)
    with pytest.raises(ValueError, match="distinct"):
        workflow.fit_field()


def test_completed_setup_starts_and_stops_a_simulator_recording(workflow, tmp_path, monkeypatch):
    _complete(workflow, tmp_path)
    workflow.finish()
    from app.services.orchestrator.pipeline_orchestrator import PipelineOrchestrator

    class Writer:
        def __init__(self, path, *_args):
            self.path = Path(path)

        def isOpened(self):
            return True

        def write(self, _frame):
            pass

        def release(self):
            self.path.write_bytes(b"fake encoded video")

    monkeypatch.setattr("cv2.VideoWriter", Writer)
    monkeypatch.setattr("app.services.orchestrator.pipeline_orchestrator.RigProfileService",
                        lambda **_kwargs: workflow.rigs)
    pipeline = PipelineOrchestrator(backend="sim")
    (tmp_path / "recordings").mkdir()
    pipeline.set_record_directory(tmp_path / "recordings")
    try:
        pipeline.start_capture(workflow.config, "left", "right", workflow.config_path)
        pipeline.start_recording(session_name="setup-regression")
        bundle = pipeline.stop_recording()
        assert (bundle.session_dir / "manifest.json").is_file()
        assert pipeline._config_path.name == "effective_config.yaml"
    finally:
        pipeline.shutdown()


def test_setup_capture_prevents_recording_and_releases_on_completion(workflow, tmp_path):
    workflow.assign("left", "right")
    request = workflow.build_capture_request(SetupCapturePurpose.FIELD_PAIR)
    with pytest.raises(RuntimeError, match="Setup cameras"):
        reserve_recording(id(workflow), workflow.rigs.base_dir, None)
    result = _capture(workflow, tmp_path, SetupCapturePurpose.FIELD_PAIR)
    workflow.apply_capture_result(result)
    assert request.assignment_generation <= workflow.generation
    # Pending edits still block recording after camera ownership has been released.
    with pytest.raises(RuntimeError, match="Finish Setup"):
        reserve_recording(id(workflow), workflow.rigs.base_dir, None)


def test_lens_adjustment_cannot_reuse_the_previous_calibration(workflow, tmp_path):
    workflow.assign("left", "right")
    workflow.accept_calibration(_calibration(workflow, tmp_path), generated=True)
    workflow.mark_focus_adjusted()
    with pytest.raises(ValueError, match="provenance"):
        workflow.validate_calibration()
    assert not workflow.state["checks"]["calibration"]["passed"]


def test_edit_failure_can_be_corrected_by_reverting_to_saved_value(workflow):
    workflow.note_unsaved_failure("an invalid edit")
    workflow.update_settings("camera", {"gain": workflow.config.camera.gain})
    assert not workflow.unsaved_error


def test_saved_rig_preserves_session_compute_selection(workflow, tmp_path):
    from dataclasses import replace
    _complete(workflow, tmp_path)
    workflow.finish()
    profile = workflow.rigs.load_active()
    session_config = replace(
        workflow.config,
        camera=replace(workflow.config.camera, fps=30),
        trajectory=replace(workflow.config.trajectory, compute_backend="auto"),
    )
    applied = workflow.rigs.apply_profile_to_config(session_config, profile, preserve_camera_mode=False)
    assert applied.trajectory.compute_backend == "auto"
    assert applied.camera.fps == workflow.config.camera.fps
