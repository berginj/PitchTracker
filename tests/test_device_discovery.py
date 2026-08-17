"""Tests for camera device discovery.

Validates that camera enumeration is fast, reliable, and properly cached.
"""

from __future__ import annotations

import threading
from unittest.mock import MagicMock, patch

import pytest

from ui.device_utils import (
    _probe_single_index,
    clear_device_cache,
    probe_all_devices,
    probe_opencv_indices,
    probe_uvc_devices,
)


@pytest.fixture(autouse=True)
def clear_cache_before_each_test():
    """Clear device cache before each test to ensure isolation."""
    clear_device_cache()
    yield
    clear_device_cache()


class TestUVCDeviceProbing:
    """Test UVC device enumeration."""

    def test_pnp_query_drains_output_while_process_runs(self):
        """Large PowerShell output cannot block process completion."""
        from capture.device_discovery import _query_pnp_devices

        process = MagicMock()
        process.communicate.return_value = (
            '[{"FriendlyName":"Camera","InstanceId":"USB\\\\CAM","Serial":"CAM1"}]',
            "",
        )
        process.returncode = 0

        with patch("capture.device_discovery.subprocess.Popen", return_value=process):
            devices = _query_pnp_devices("Camera")

        assert devices[0]["FriendlyName"] == "Camera"
        process.communicate.assert_called_once()

    def test_probe_uvc_devices_filters_virtual_cameras(self):
        """Should filter out virtual/software cameras."""
        with patch("ui.device_utils.list_uvc_devices") as mock_list:
            mock_list.return_value = [
                {"serial": "REAL1", "friendly_name": "HD Camera"},
                {"serial": "OBS1", "friendly_name": "OBS Virtual Camera"},
                {"serial": "REAL2", "friendly_name": "Logitech Camera"},
                {"serial": "SNAP1", "friendly_name": "Snap Camera"},
                {"serial": "REAL3", "friendly_name": "USB Camera"},
            ]

            devices = probe_uvc_devices(use_cache=False)

            # Should only return physical cameras
            assert len(devices) == 3
            serials = [d["serial"] for d in devices]
            assert "REAL1" in serials
            assert "REAL2" in serials
            assert "REAL3" in serials
            assert "OBS1" not in serials
            assert "SNAP1" not in serials

    def test_probe_uvc_devices_caching(self):
        """Should cache results to avoid repeated PowerShell calls."""
        with patch("ui.device_utils.list_uvc_devices") as mock_list:
            mock_list.return_value = [{"serial": "TEST1", "friendly_name": "Test Camera"}]

            # First call should query
            devices1 = probe_uvc_devices(use_cache=True)
            assert mock_list.call_count == 1

            # Second call should use cache
            devices2 = probe_uvc_devices(use_cache=True)
            assert mock_list.call_count == 1  # Still 1, not 2

            # Results should be identical
            assert devices1 == devices2

    def test_probe_uvc_devices_bypass_cache(self):
        """Should bypass cache when use_cache=False."""
        with patch("ui.device_utils.list_uvc_devices") as mock_list:
            mock_list.return_value = [{"serial": "TEST1", "friendly_name": "Test Camera"}]

            # First call with cache
            probe_uvc_devices(use_cache=True)
            assert mock_list.call_count == 1

            # Second call without cache should query again
            probe_uvc_devices(use_cache=False)
            assert mock_list.call_count == 2

    def test_clear_device_cache(self):
        """Cache should be cleared when clear_device_cache() is called."""
        with patch("ui.device_utils.list_uvc_devices") as mock_list:
            mock_list.return_value = [{"serial": "TEST1", "friendly_name": "Test Camera"}]

            # Prime cache
            probe_uvc_devices(use_cache=True)
            assert mock_list.call_count == 1

            # Use cached value
            probe_uvc_devices(use_cache=True)
            assert mock_list.call_count == 1

            # Clear cache
            clear_device_cache()

            # Should query again
            probe_uvc_devices(use_cache=True)
            assert mock_list.call_count == 2


class TestOpenCVIndexProbing:
    """Test OpenCV camera index enumeration."""

    def test_probe_opencv_indices_parallel(self):
        """Parallel probing should check all indices simultaneously."""
        with patch(
            "ui.device_utils._probe_single_index",
            side_effect=lambda index, *_args: index if index in {0, 2} else None,
        ):
            indices = probe_opencv_indices(max_index=4, parallel=True, use_cache=False)

            # Should find cameras at 0 and 2
            assert 0 in indices
            assert 2 in indices
            assert 1 not in indices
            assert 3 not in indices

    def test_probe_opencv_indices_sequential(self):
        """Sequential probing should check indices one by one."""
        with patch(
            "ui.device_utils._probe_single_index",
            side_effect=lambda index, *_args: index if index == 1 else None,
        ):
            indices = probe_opencv_indices(max_index=4, parallel=False, use_cache=False)

            assert 1 in indices
            assert len(indices) == 1

    def test_probe_opencv_indices_caching(self):
        """Should cache OpenCV probe results."""
        with patch("ui.device_utils._probe_single_index", return_value=0) as mock_probe:
            # First call should probe
            indices1 = probe_opencv_indices(max_index=2, use_cache=True)
            call_count_1 = mock_probe.call_count

            # Second call should use cache (no new VideoCapture calls)
            indices2 = probe_opencv_indices(max_index=2, use_cache=True)
            call_count_2 = mock_probe.call_count

            assert call_count_1 == call_count_2  # No additional calls
            assert indices1 == indices2

    def test_probe_opencv_default_max_index_covers_four_camera_rigs(self):
        """Default max_index should scan enough indices for four-camera rigs."""
        import inspect

        signature = inspect.signature(probe_opencv_indices)
        assert signature.parameters["max_index"].default == 16

    def test_probe_opencv_timeout_protection(self):
        """A timed-out native probe process is terminated and reaped."""

        class HangingProcess:
            def __init__(self):
                self.alive = True
                self.terminated = False
                self.joined = False

            def is_alive(self):
                return self.alive

            def join(self, timeout=None):
                self.joined = True

            def terminate(self):
                self.terminated = True
                self.alive = False

        process = HangingProcess()
        result_connection = MagicMock()
        with patch(
            "ui.device_utils._start_probe_process",
            return_value=(process, result_connection),
        ):
            assert _probe_single_index(3, timeout_seconds=0.0) is None

        assert process.terminated
        assert process.joined
        result_connection.close.assert_called_once()

    def test_cancelled_probe_does_not_start_process(self):
        """Cancellation before a probe avoids starting native camera work."""
        cancel_event = threading.Event()
        cancel_event.set()

        with patch("ui.device_utils._start_probe_process") as start_probe:
            assert _probe_single_index(2, cancel_event=cancel_event) is None

        start_probe.assert_not_called()

    def test_crashed_probe_process_is_treated_as_unavailable(self):
        """A child that exits without sending cannot abort discovery."""
        process = MagicMock()
        process.is_alive.return_value = False
        result_connection = MagicMock()
        result_connection.poll.side_effect = EOFError

        with patch(
            "ui.device_utils._start_probe_process",
            return_value=(process, result_connection),
        ):
            assert _probe_single_index(4) is None

        result_connection.close.assert_called_once()

    def test_probe_worker_releases_capture_on_owner_thread(self):
        """The child worker opens, inspects, and releases on one thread."""
        from capture.opencv_probe_process import probe_camera_index

        owner_thread = threading.get_ident()
        capture = MagicMock()
        capture.isOpened.side_effect = lambda: threading.get_ident() == owner_thread

        def release_capture():
            assert threading.get_ident() == owner_thread

        capture.release.side_effect = release_capture
        result_connection = MagicMock()

        with patch("capture.opencv_probe_process.cv2.VideoCapture", return_value=capture):
            probe_camera_index(1, result_connection)

        result_connection.send.assert_called_once_with(True)
        result_connection.close.assert_called_once()


class TestUnifiedProbing:
    """Test probe_all_devices unified interface."""

    def test_prefers_uvc_when_available(self):
        """Should use UVC devices when available, skip OpenCV."""
        with patch("ui.device_utils.list_uvc_devices") as mock_uvc:
            mock_uvc.return_value = [{"serial": "UVC1", "friendly_name": "UVC Camera"}]

            with patch("cv2.VideoCapture") as mock_cv:
                uvc_devices, opencv_indices = probe_all_devices(use_cache=False)

                # Should return UVC devices
                assert len(uvc_devices) == 1
                assert opencv_indices == []

                # Should not have called OpenCV probing
                assert mock_cv.call_count == 0

    def test_fallback_to_opencv_when_no_uvc(self):
        """Should fall back to OpenCV when no UVC devices found."""
        with patch("ui.device_utils.list_uvc_devices") as mock_uvc:
            mock_uvc.return_value = []

            with patch("ui.device_utils._probe_single_index", side_effect=lambda index, *_args: index) as mock_probe:
                uvc_devices, opencv_indices = probe_all_devices(use_cache=False)

                # Should return OpenCV indices
                assert len(uvc_devices) == 0
                assert len(opencv_indices) > 0

                # Should have called OpenCV probing
                assert mock_probe.call_count > 0

    def test_caching_applies_to_unified_probe(self):
        """Caching should work for unified probe."""
        with patch("ui.device_utils.list_uvc_devices") as mock_uvc:
            mock_uvc.return_value = [{"serial": "TEST1", "friendly_name": "Test Camera"}]

            # First call
            probe_all_devices(use_cache=True)
            assert mock_uvc.call_count == 1

            # Second call should use cache
            probe_all_devices(use_cache=True)
            assert mock_uvc.call_count == 1  # Still 1


class TestDeviceDiscoveryPerformance:
    """Test that device discovery is fast enough."""

    def test_uvc_probe_is_fast(self):
        """UVC probing should be fast (no camera open)."""
        import time

        with patch("ui.device_utils.list_uvc_devices") as mock_list:
            # Simulate fast PowerShell query
            mock_list.return_value = [{"serial": f"CAM{i}", "friendly_name": f"Camera {i}"} for i in range(10)]

            start = time.monotonic()
            devices = probe_uvc_devices(use_cache=False)
            elapsed = time.monotonic() - start

            # Should complete in under 100ms (PowerShell + filtering)
            assert elapsed < 0.1
            assert len(devices) == 10

    def test_cached_probe_is_instant(self):
        """Cached probes should be near-instantaneous."""
        import time

        with patch("ui.device_utils.list_uvc_devices") as mock_list:
            mock_list.return_value = [{"serial": "TEST1", "friendly_name": "Test Camera"}]

            # Prime cache
            probe_uvc_devices(use_cache=True)

            # Time cached access
            start = time.monotonic()
            devices = probe_uvc_devices(use_cache=True)
            elapsed = time.monotonic() - start

            # Should be near-instant (<1ms)
            assert elapsed < 0.001
            assert len(devices) == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
