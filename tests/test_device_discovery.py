"""Tests for camera device discovery.

Validates that camera enumeration is fast, reliable, and properly cached.
"""

from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from ui.device_utils import (
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
            mock_list.return_value = [
                {"serial": "TEST1", "friendly_name": "Test Camera"}
            ]

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
            mock_list.return_value = [
                {"serial": "TEST1", "friendly_name": "Test Camera"}
            ]

            # First call with cache
            probe_uvc_devices(use_cache=True)
            assert mock_list.call_count == 1

            # Second call without cache should query again
            probe_uvc_devices(use_cache=False)
            assert mock_list.call_count == 2

    def test_clear_device_cache(self):
        """Cache should be cleared when clear_device_cache() is called."""
        with patch("ui.device_utils.list_uvc_devices") as mock_list:
            mock_list.return_value = [
                {"serial": "TEST1", "friendly_name": "Test Camera"}
            ]

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
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_cap.return_value = mock_instance

            # Cameras at indices 0 and 2
            def is_opened_side_effect(*args, **kwargs):
                # Check which index was opened
                if mock_cap.call_count in (1, 3):  # Indices 0 and 2
                    return True
                return False

            mock_instance.isOpened.side_effect = is_opened_side_effect

            indices = probe_opencv_indices(max_index=4, parallel=True, use_cache=False)

            # Should find cameras at 0 and 2
            assert 0 in indices
            assert 2 in indices
            assert 1 not in indices
            assert 3 not in indices

    def test_probe_opencv_indices_sequential(self):
        """Sequential probing should check indices one by one."""
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_cap.return_value = mock_instance

            # Camera only at index 1
            call_count = {"count": 0}

            def is_opened_side_effect():
                call_count["count"] += 1
                return call_count["count"] == 2  # Second call (index 1)

            mock_instance.isOpened.side_effect = is_opened_side_effect

            indices = probe_opencv_indices(
                max_index=4, parallel=False, use_cache=False
            )

            assert 1 in indices
            assert len(indices) == 1

    def test_probe_opencv_indices_caching(self):
        """Should cache OpenCV probe results."""
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_cap.return_value = mock_instance
            mock_instance.isOpened.return_value = True

            # First call should probe
            indices1 = probe_opencv_indices(max_index=2, use_cache=True)
            call_count_1 = mock_cap.call_count

            # Second call should use cache (no new VideoCapture calls)
            indices2 = probe_opencv_indices(max_index=2, use_cache=True)
            call_count_2 = mock_cap.call_count

            assert call_count_1 == call_count_2  # No additional calls
            assert indices1 == indices2

    def test_probe_opencv_reduced_max_index(self):
        """Default max_index should be 4 (reduced from 8)."""
        with patch("cv2.VideoCapture") as mock_cap:
            mock_instance = MagicMock()
            mock_cap.return_value = mock_instance
            mock_instance.isOpened.return_value = False

            # Call with defaults
            probe_opencv_indices(parallel=False, use_cache=False)

            # Should only check indices 0-3 (4 total)
            assert mock_cap.call_count == 4

    def test_probe_opencv_timeout_protection(self):
        """Should timeout on stuck cameras (tested via integration)."""
        # This is harder to test directly without actually hanging,
        # but we can verify the timeout wrapper is applied
        import inspect
        from ui.device_utils import _probe_single_index

        # Check that function has timeout logic
        source = inspect.getsource(_probe_single_index)
        assert "threading.Thread" in source
        assert "join(timeout" in source


class TestUnifiedProbing:
    """Test probe_all_devices unified interface."""

    def test_prefers_uvc_when_available(self):
        """Should use UVC devices when available, skip OpenCV."""
        with patch("ui.device_utils.list_uvc_devices") as mock_uvc:
            mock_uvc.return_value = [
                {"serial": "UVC1", "friendly_name": "UVC Camera"}
            ]

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

            with patch("cv2.VideoCapture") as mock_cv:
                mock_instance = MagicMock()
                mock_cv.return_value = mock_instance
                mock_instance.isOpened.return_value = True

                uvc_devices, opencv_indices = probe_all_devices(use_cache=False)

                # Should return OpenCV indices
                assert len(uvc_devices) == 0
                assert len(opencv_indices) > 0

                # Should have called OpenCV probing
                assert mock_cv.call_count > 0

    def test_caching_applies_to_unified_probe(self):
        """Caching should work for unified probe."""
        with patch("ui.device_utils.list_uvc_devices") as mock_uvc:
            mock_uvc.return_value = [
                {"serial": "TEST1", "friendly_name": "Test Camera"}
            ]

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
            mock_list.return_value = [
                {"serial": f"CAM{i}", "friendly_name": f"Camera {i}"}
                for i in range(10)
            ]

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
            mock_list.return_value = [
                {"serial": "TEST1", "friendly_name": "Test Camera"}
            ]

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
