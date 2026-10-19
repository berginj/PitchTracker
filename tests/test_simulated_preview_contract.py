"""The normal capture gate admits both supported simulator image formats."""

import numpy as np
import pytest

from app.pipeline.camera_frame_router import _validate_frame
from capture.simulated_camera import SimulatedCamera


@pytest.mark.parametrize("pixfmt,shape", [("GRAY8", (48, 64)), ("YUYV", (48, 64, 3)), ("MJPG", (48, 64, 3))])
def test_simulator_frame_is_usable_by_capture(pixfmt, shape):
    camera = SimulatedCamera()
    camera.open("synthetic-left")
    camera.set_mode(64, 48, 30, pixfmt)
    try:
        frame = camera.read_frame(100)
        assert frame.camera_id == "synthetic-left"
        assert frame.image.shape == shape and frame.image.dtype == np.uint8
        assert _validate_frame("left", frame)
    finally:
        camera.close()
