"""Test that camera backends handle both string and integer serial inputs.

This test ensures that the recurring issue of AttributeError: 'int' object
has no attribute 'isdigit' doesn't regress. All camera backend open() methods
should defensively handle both str and int inputs.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock


class TestCameraSerialTypes:
    """Test camera backends accept both string and integer serials."""

    @pytest.mark.parametrize("serial_input", [
        "0",      # String
        0,        # Integer
        "1",      # String
        1,        # Integer
    ])
    def test_opencv_backend_accepts_both_types(self, serial_input):
        """OpenCV backend should accept both string and integer serials."""
        from capture.opencv_backend import OpenCVCamera

        camera = OpenCVCamera()

        # Mock cv2.VideoCapture to prevent actual camera access
        with patch('capture.opencv_backend.cv2.VideoCapture') as mock_capture:
            mock_cap_instance = MagicMock()
            mock_cap_instance.isOpened.return_value = True
            mock_capture.return_value = mock_cap_instance

            # Should not raise AttributeError or TypeError
            try:
                camera.open(serial_input)
                # If it succeeds, great
            except Exception as e:
                # Allow camera not found or connection errors, but not type errors
                assert not isinstance(e, (AttributeError, TypeError)), \
                    f"Got type error with serial {serial_input} ({type(serial_input).__name__}): {e}"

    @pytest.mark.parametrize("serial_input", [
        "ABC123",  # String serial
        "0",       # String index
        0,         # Integer index
    ])
    def test_uvc_backend_accepts_both_types(self, serial_input):
        """UVC backend should accept both string and integer serials."""
        from capture.uvc_backend import UvcCamera

        camera = UvcCamera()

        # Mock list_uvc_devices and cv2.VideoCapture
        with patch('capture.uvc_backend._list_camera_devices') as mock_list, \
             patch('capture.uvc_backend.cv2.VideoCapture') as mock_capture:

            # Setup mock devices
            mock_list.return_value = [
                {"serial": "ABC123", "friendly_name": "Test Camera"}
            ]

            mock_cap_instance = MagicMock()
            mock_cap_instance.isOpened.return_value = True
            mock_capture.return_value = mock_cap_instance

            # Should not raise AttributeError or TypeError
            try:
                camera.open(serial_input)
                # If it succeeds, great
            except Exception as e:
                # Allow camera not found or connection errors, but not type errors
                assert not isinstance(e, (AttributeError, TypeError)), \
                    f"Got type error with serial {serial_input} ({type(serial_input).__name__}): {e}"

    # NOTE: GUI tests disabled - CalibrationStep and RoiStep require Qt application
    # The actual protection is tested via backend tests above
    # GUI integration is tested manually during development


class TestSerialConversionUtils:
    """Test utility functions that handle serial conversion."""

    def test_str_conversion_preserves_string(self):
        """str() on string should return identical string."""
        assert str("0") == "0"
        assert str("ABC123") == "ABC123"

    def test_str_conversion_handles_int(self):
        """str() on int should return string representation."""
        assert str(0) == "0"
        assert str(1) == "1"
        assert str(42) == "42"

    def test_isdigit_works_on_string(self):
        """isdigit() should work on string representations."""
        assert "0".isdigit()
        assert "123".isdigit()
        assert not "ABC".isdigit()
        assert not "Camera 0".isdigit()

    def test_int_conversion_from_string(self):
        """int() should convert string digits to integers."""
        assert int("0") == 0
        assert int("42") == 42

    def test_split_extracts_last_element(self):
        """split()[-1] should extract camera index from 'Camera N' format."""
        assert "Camera 0".split()[-1] == "0"
        assert "Camera 42".split()[-1] == "42"
        assert "0".split()[-1] == "0"  # Single element returns itself
