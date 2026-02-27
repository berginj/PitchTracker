"""Unit tests for DeviceManager.

Tests the extracted DeviceManager class from MainWindow refactoring.
Covers device enumeration and camera selection.
"""

from __future__ import annotations

from unittest.mock import Mock, patch, MagicMock

import pytest

from ui.controllers.device_manager import DeviceManager


class TestDeviceManagerInit:
    """Tests for DeviceManager initialization."""

    def test_initialization(self):
        """DeviceManager should initialize with provided widgets."""
        left_input = Mock()
        right_input = Mock()
        status_label = Mock()

        dm = DeviceManager(
            left_input=left_input,
            right_input=right_input,
            status_label=status_label,
            get_backend=Mock(return_value="uvc"),
        )

        # Should not raise


class TestGetSerials:
    """Tests for serial number retrieval."""

    @pytest.fixture
    def device_manager(self):
        """Create DeviceManager with mock widgets."""
        return DeviceManager(
            left_input=Mock(),
            right_input=Mock(),
            status_label=Mock(),
            get_backend=Mock(return_value="uvc"),
        )

    @patch("ui.controllers.device_manager.current_serial")
    def test_get_left_serial(self, mock_current, device_manager):
        """get_left_serial should return current left serial."""
        mock_current.return_value = "LEFT123"

        result = device_manager.get_left_serial()

        assert result == "LEFT123"
        mock_current.assert_called_once()

    @patch("ui.controllers.device_manager.current_serial")
    def test_get_right_serial(self, mock_current, device_manager):
        """get_right_serial should return current right serial."""
        mock_current.return_value = "RIGHT456"

        result = device_manager.get_right_serial()

        assert result == "RIGHT456"
        mock_current.assert_called_once()


class TestRefreshUvcDevices:
    """Tests for UVC device refresh."""

    @pytest.fixture
    def device_manager(self):
        """Create DeviceManager for UVC backend."""
        left = Mock()
        right = Mock()
        status = Mock()
        return DeviceManager(
            left_input=left,
            right_input=right,
            status_label=status,
            get_backend=Mock(return_value="uvc"),
        )

    @patch("ui.controllers.device_manager.probe_uvc_devices")
    @patch("ui.controllers.device_manager.is_arducam_device")
    def test_refresh_uvc_devices_found(
        self, mock_is_arducam, mock_probe, device_manager
    ):
        """refresh_devices should populate dropdowns for UVC devices."""
        mock_probe.return_value = [
            {"serial": "SN001", "friendly_name": "ArduCam B0299"},
            {"serial": "SN002", "friendly_name": "ArduCam B0299"},
        ]
        mock_is_arducam.return_value = True

        count = device_manager.refresh_devices()

        assert count == 2
        assert device_manager._left_input.addItem.call_count == 2
        assert device_manager._right_input.addItem.call_count == 2
        device_manager._status_label.setText.assert_called_once()

    @patch("ui.controllers.device_manager.probe_uvc_devices")
    def test_refresh_uvc_devices_none(self, mock_probe, device_manager):
        """refresh_devices should show message when no UVC devices found."""
        mock_probe.return_value = []

        count = device_manager.refresh_devices()

        assert count == 0
        device_manager._status_label.setText.assert_called_with(
            "No UVC devices found."
        )

    @patch("ui.controllers.device_manager.probe_uvc_devices")
    @patch("ui.controllers.device_manager.is_arducam_device")
    def test_refresh_uvc_auto_select(self, mock_is_arducam, mock_probe, device_manager):
        """refresh_devices should auto-select first two cameras."""
        mock_probe.return_value = [
            {"serial": "SN001", "friendly_name": "Camera 1"},
            {"serial": "SN002", "friendly_name": "Camera 2"},
        ]
        mock_is_arducam.return_value = False

        device_manager.refresh_devices()

        device_manager._left_input.setCurrentIndex.assert_called_with(0)
        device_manager._right_input.setCurrentIndex.assert_called_with(1)


class TestRefreshOpencvDevices:
    """Tests for OpenCV device refresh."""

    @pytest.fixture
    def device_manager(self):
        """Create DeviceManager for OpenCV backend."""
        left = Mock()
        right = Mock()
        status = Mock()
        return DeviceManager(
            left_input=left,
            right_input=right,
            status_label=status,
            get_backend=Mock(return_value="opencv"),
        )

    @patch("ui.controllers.device_manager.probe_opencv_indices")
    @patch("ui.controllers.device_manager.probe_uvc_devices")
    @patch("ui.controllers.device_manager.is_arducam_device")
    def test_refresh_opencv_devices_found(
        self, mock_is_arducam, mock_probe_uvc, mock_probe_cv, device_manager
    ):
        """refresh_devices should populate dropdowns for OpenCV indices."""
        mock_probe_cv.return_value = [0, 1]
        mock_probe_uvc.return_value = [
            {"friendly_name": "ArduCam B0299"},
            {"friendly_name": "ArduCam B0299"},
        ]
        mock_is_arducam.return_value = True

        count = device_manager.refresh_devices()

        assert count == 2
        assert device_manager._left_input.addItem.call_count == 2
        assert device_manager._right_input.addItem.call_count == 2

    @patch("ui.controllers.device_manager.probe_opencv_indices")
    @patch("ui.controllers.device_manager.probe_uvc_devices")
    def test_refresh_opencv_devices_none(
        self, mock_probe_uvc, mock_probe_cv, device_manager
    ):
        """refresh_devices should show message when no OpenCV indices found."""
        mock_probe_cv.return_value = []
        mock_probe_uvc.return_value = []

        count = device_manager.refresh_devices()

        assert count == 0
        device_manager._status_label.setText.assert_called_with(
            "No OpenCV camera indices available."
        )

    @patch("ui.controllers.device_manager.probe_opencv_indices")
    @patch("ui.controllers.device_manager.probe_uvc_devices")
    @patch("ui.controllers.device_manager.is_arducam_device")
    def test_refresh_opencv_with_unknown_device(
        self, mock_is_arducam, mock_probe_uvc, mock_probe_cv, device_manager
    ):
        """refresh_devices should handle indices without UVC info."""
        mock_probe_cv.return_value = [0, 1, 2]
        mock_probe_uvc.return_value = [
            {"friendly_name": "Camera 1"},
        ]  # Only one UVC device
        mock_is_arducam.return_value = False

        count = device_manager.refresh_devices()

        assert count == 3
        # Should have called addItem 3 times for each input
        assert device_manager._left_input.addItem.call_count == 3


class TestArducamCounting:
    """Tests for ArduCam device counting."""

    @pytest.fixture
    def device_manager(self):
        """Create DeviceManager."""
        return DeviceManager(
            left_input=Mock(),
            right_input=Mock(),
            status_label=Mock(),
            get_backend=Mock(return_value="uvc"),
        )

    @patch("ui.controllers.device_manager.probe_uvc_devices")
    @patch("ui.controllers.device_manager.is_arducam_device")
    def test_arducam_count_in_status(self, mock_is_arducam, mock_probe, device_manager):
        """Status should show ArduCam count when detected."""
        mock_probe.return_value = [
            {"serial": "SN001", "friendly_name": "ArduCam B0299"},
            {"serial": "SN002", "friendly_name": "Generic Camera"},
        ]
        # First call returns True (ArduCam), second returns False
        mock_is_arducam.side_effect = [True, False]

        device_manager.refresh_devices()

        status_text = device_manager._status_label.setText.call_args[0][0]
        assert "1 ArduCam" in status_text


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
