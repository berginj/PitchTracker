"""Tests for camera setup and video rendering workflow.

These tests validate that cameras can be initialized correctly and
video frames can be read, preventing runtime errors in the setup wizard.
"""

from __future__ import annotations

import pytest
import numpy as np
from unittest.mock import Mock, MagicMock, patch

from capture.opencv_backend import OpenCVCamera
from capture.uvc_backend import UvcCamera
from contracts import Frame


class TestOpenCVCameraInitialization:
    """Test OpenCV camera initialization sequence."""

    def test_opencv_camera_no_init_args(self):
        """OpenCVCamera() should not accept any constructor arguments."""
        camera = OpenCVCamera()
        assert camera is not None

    def test_opencv_camera_requires_numeric_index(self):
        """OpenCVCamera.open() should only accept numeric strings."""
        camera = OpenCVCamera()

        # Should accept numeric string
        with patch('cv2.VideoCapture') as mock_cap:
            mock_cap.return_value.isOpened.return_value = True
            camera.open("0")  # Should work

        # Should reject non-numeric
        camera2 = OpenCVCamera()
        with pytest.raises(ValueError, match="only supports index-based"):
            camera2.open("Camera 0")  # Should fail

    def test_opencv_camera_api_sequence(self):
        """Test correct API call sequence: create -> open -> set_mode -> read_frame."""
        with patch('cv2.VideoCapture') as mock_cap:
            mock_instance = MagicMock()
            mock_cap.return_value = mock_instance
            mock_instance.isOpened.return_value = True

            # Mock frame reading
            mock_frame = np.zeros((480, 640), dtype=np.uint8)
            mock_instance.read.return_value = (True, mock_frame)

            # 1. Create camera
            camera = OpenCVCamera()

            # 2. Open camera
            camera.open("0")
            mock_cap.assert_called_with(0, 2)  # cv2.CAP_DSHOW = 2

            # 3. Set mode
            camera.set_mode(640, 480, 30, "GRAY8")

            # 4. Read frame
            frame = camera.read_frame(timeout_ms=1000)
            assert frame is not None
            assert isinstance(frame, Frame)


class TestUVCCameraInitialization:
    """Test UVC camera initialization sequence."""

    def test_uvc_camera_no_init_args(self):
        """UvcCamera() should not accept any constructor arguments."""
        camera = UvcCamera()
        assert camera is not None

    def test_uvc_camera_api_sequence(self):
        """Test correct API call sequence: create -> open -> set_mode -> read_frame."""
        with patch('capture.uvc_backend._list_camera_devices') as mock_list:
            # Mock device list
            mock_list.return_value = [{
                'serial': 'TEST123',
                'friendly_name': 'Test Camera',
                'instance_id': 'USB\\VID_1234&PID_5678\\TEST123'
            }]

            with patch('cv2.VideoCapture') as mock_cap:
                mock_instance = MagicMock()
                mock_cap.return_value = mock_instance
                mock_instance.isOpened.return_value = True

                # Mock frame reading
                mock_frame = np.zeros((480, 640), dtype=np.uint8)
                mock_instance.read.return_value = (True, mock_frame)

                # 1. Create camera
                camera = UvcCamera()

                # 2. Open camera
                camera.open("TEST123")

                # 3. Set mode
                camera.set_mode(640, 480, 30, "GRAY8")

                # 4. Read frame
                frame = camera.read_frame(timeout_ms=1000)
                assert frame is not None
                assert isinstance(frame, Frame)


class TestCameraSetupWorkflow:
    """Test complete camera setup workflow from setup wizard."""

    def test_opencv_backend_workflow(self):
        """Test setup wizard workflow with OpenCV backend."""
        with patch('cv2.VideoCapture') as mock_cap:
            mock_instance = MagicMock()
            mock_cap.return_value = mock_instance
            mock_instance.isOpened.return_value = True
            mock_frame = np.zeros((480, 640), dtype=np.uint8)
            mock_instance.read.return_value = (True, mock_frame)

            # Simulate setup wizard selecting "Camera 0" and "Camera 1"
            left_serial = "0"  # Extracted from "Camera 0"
            right_serial = "1"  # Extracted from "Camera 1"

            # Create and open cameras like calibration step does
            left_camera = OpenCVCamera()
            right_camera = OpenCVCamera()

            left_camera.open(left_serial)
            right_camera.open(right_serial)

            left_camera.set_mode(640, 480, 30, "GRAY8")
            right_camera.set_mode(640, 480, 30, "GRAY8")

            # Read frames for video preview
            left_frame = left_camera.read_frame(timeout_ms=1000)
            right_frame = right_camera.read_frame(timeout_ms=1000)

            assert left_frame is not None
            assert right_frame is not None
            assert left_frame.width == 640
            assert left_frame.height == 480

    def test_uvc_backend_workflow(self):
        """Test setup wizard workflow with UVC backend."""
        with patch('capture.uvc_backend._list_camera_devices') as mock_list:
            mock_list.return_value = [
                {
                    'serial': 'LEFT123',
                    'friendly_name': 'Left Camera',
                    'instance_id': 'USB\\VID_1234&PID_5678\\LEFT123'
                },
                {
                    'serial': 'RIGHT456',
                    'friendly_name': 'Right Camera',
                    'instance_id': 'USB\\VID_1234&PID_5678\\RIGHT456'
                }
            ]

            with patch('cv2.VideoCapture') as mock_cap:
                mock_instance = MagicMock()
                mock_cap.return_value = mock_instance
                mock_instance.isOpened.return_value = True
                mock_frame = np.zeros((480, 640), dtype=np.uint8)
                mock_instance.read.return_value = (True, mock_frame)

                # Simulate setup wizard selecting cameras by serial
                left_serial = "LEFT123"
                right_serial = "RIGHT456"

                # Create and open cameras like calibration step does
                left_camera = UvcCamera()
                right_camera = UvcCamera()

                left_camera.open(left_serial)
                right_camera.open(right_serial)

                left_camera.set_mode(640, 480, 30, "GRAY8")
                right_camera.set_mode(640, 480, 30, "GRAY8")

                # Read frames for video preview
                left_frame = left_camera.read_frame(timeout_ms=1000)
                right_frame = right_camera.read_frame(timeout_ms=1000)

                assert left_frame is not None
                assert right_frame is not None


class TestIndexExtraction:
    """Test camera index extraction logic from setup wizard."""

    def test_extract_index_from_camera_string(self):
        """Test extracting numeric index from 'Camera N' format."""
        # This is what camera_step.py does
        test_cases = [
            ("Camera 0", "0"),
            ("Camera 1", "1"),
            ("Camera 2", "2"),
            ("0", "0"),  # Already numeric
            ("1", "1"),
        ]

        for input_str, expected in test_cases:
            if input_str.isdigit():
                result = input_str
            else:
                result = input_str.split()[-1]
            assert result == expected, f"Failed for input: {input_str}"


class TestVideoFrameReading:
    """Test that frames can be read and rendered."""

    def test_frame_has_required_attributes(self):
        """Test that Frame objects have required attributes for rendering."""
        mock_image = np.zeros((480, 640), dtype=np.uint8)

        frame = Frame(
            camera_id="test",
            frame_index=0,
            t_capture_monotonic_ns=0,
            image=mock_image,
            width=640,
            height=480,
            pixfmt="GRAY8"
        )

        # These attributes are required by UI rendering code
        assert hasattr(frame, 'image')
        assert hasattr(frame, 'width')
        assert hasattr(frame, 'height')
        assert frame.image.shape == (480, 640)
        assert frame.width == 640
        assert frame.height == 480

    def test_grayscale_to_bgr_conversion(self):
        """Test that grayscale images can be converted to BGR for rendering."""
        import cv2

        gray_image = np.zeros((480, 640), dtype=np.uint8)

        # This is what calibration_step does for checkerboard drawing
        if len(gray_image.shape) == 2:
            bgr_image = cv2.cvtColor(gray_image, cv2.COLOR_GRAY2BGR)
        else:
            bgr_image = gray_image

        assert bgr_image.shape == (480, 640, 3)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
