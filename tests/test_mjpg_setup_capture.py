"""The backend's MJPEG mode survives saved setup and supervised frame capture."""

import numpy as np

from app.services.capture.setup_capture import SupervisedSetupCaptureService
from app.services.setup_workflow import SetupWorkflowService
from configs.settings import load_config
from contracts.setup_capture import SetupCapturePurpose
from tests.test_guided_setup_workflow import _new_workflow


def test_saved_mjpg_settings_reopen_and_capture_color_frames(tmp_path):
    workflow = _new_workflow(tmp_path)
    workflow.update_settings("camera", {"width": 640, "height": 480, "fps": 30,
                                        "pixfmt": "MJPG", "color_mode": True})
    workflow.assign("synthetic-left", "synthetic-right")
    reopened = SetupWorkflowService(workflow.config_path, tmp_path / "calibration/rigs", backend="sim")
    assert load_config(reopened.config_path).camera.pixfmt == "MJPG"
    service = SupervisedSetupCaptureService(artifact_root=tmp_path / "capture")
    job = service.submit(reopened.build_capture_request(SetupCapturePurpose.PREVIEW))
    try:
        assert job.wait(30), "Supervised MJPEG preview did not finish"
        assert job.result is not None, job.terminal
        reopened.apply_capture_result(job.result)
        for records in (job.result.left_frames, job.result.right_frames):
            assert records[-1].pixfmt == "MJPG"
            image = np.load(records[-1].image_path, allow_pickle=False)
            assert image.shape == (480, 640, 3)
        assert not job.process_alive
    finally:
        if not job.done:
            job.cancel()
            assert job.wait(5), "Cancelled preview worker did not stop"
        reopened.release_capture()
