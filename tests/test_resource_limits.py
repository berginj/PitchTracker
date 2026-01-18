"""Unit tests for resource limits configuration (Phase 3 Fix #12)."""

import unittest

from app.config import ResourceLimits, get_resource_limits, set_resource_limits


class TestResourceLimits(unittest.TestCase):
    """Test ResourceLimits dataclass."""

    def test_default_values(self):
        """Test that default values are reasonable."""
        limits = ResourceLimits()

        # Memory
        self.assertEqual(limits.max_memory_mb, 4096.0)
        self.assertEqual(limits.warning_memory_mb, 2048.0)

        # CPU
        self.assertEqual(limits.max_cpu_percent, 95.0)
        self.assertEqual(limits.warning_cpu_percent, 80.0)

        # Disk
        self.assertEqual(limits.critical_disk_gb, 5.0)
        self.assertEqual(limits.warning_disk_gb, 20.0)
        self.assertEqual(limits.recommended_disk_gb, 50.0)

        # Queues
        self.assertEqual(limits.max_queue_size, 10)
        self.assertEqual(limits.detection_queue_size, 6)

        # Timeouts
        self.assertEqual(limits.camera_open_timeout, 10.0)
        self.assertEqual(limits.cleanup_timeout, 10.0)

    def test_validate_valid_limits(self):
        """Test validation of valid limits."""
        limits = ResourceLimits()
        errors = limits.validate()
        self.assertEqual(len(errors), 0)

    def test_validate_negative_memory(self):
        """Test that negative memory is invalid."""
        limits = ResourceLimits(max_memory_mb=-1000)
        errors = limits.validate()
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("max_memory_mb" in e for e in errors))

    def test_validate_invalid_cpu_percent(self):
        """Test that CPU percent must be 0-100."""
        limits1 = ResourceLimits(max_cpu_percent=-10)
        errors1 = limits1.validate()
        self.assertTrue(any("max_cpu_percent" in e for e in errors1))

        limits2 = ResourceLimits(max_cpu_percent=150)
        errors2 = limits2.validate()
        self.assertTrue(any("max_cpu_percent" in e for e in errors2))

    def test_validate_warning_less_than_max(self):
        """Test that warning thresholds must be less than max."""
        limits = ResourceLimits(warning_memory_mb=5000, max_memory_mb=4000)
        errors = limits.validate()
        self.assertTrue(any("warning_memory_mb must be less than max_memory_mb" in e for e in errors))

    def test_validate_disk_thresholds_ordered(self):
        """Test that disk thresholds must be properly ordered."""
        limits = ResourceLimits(
            critical_disk_gb=30.0, warning_disk_gb=20.0, recommended_disk_gb=50.0
        )
        errors = limits.validate()
        self.assertTrue(any("critical_disk_gb must be less than warning_disk_gb" in e for e in errors))

    def test_validate_positive_queue_sizes(self):
        """Test that queue sizes must be positive."""
        limits = ResourceLimits(max_queue_size=0)
        errors = limits.validate()
        self.assertTrue(any("max_queue_size must be positive" in e for e in errors))

    def test_validate_positive_timeouts(self):
        """Test that timeouts must be positive."""
        limits = ResourceLimits(camera_open_timeout=-1.0)
        errors = limits.validate()
        self.assertTrue(any("camera_open_timeout must be positive" in e for e in errors))

    def test_is_memory_critical(self):
        """Test memory critical check."""
        limits = ResourceLimits(max_memory_mb=4000)

        self.assertFalse(limits.is_memory_critical(3000))
        self.assertTrue(limits.is_memory_critical(4000))
        self.assertTrue(limits.is_memory_critical(5000))

    def test_is_memory_warning(self):
        """Test memory warning check."""
        limits = ResourceLimits(warning_memory_mb=2000, max_memory_mb=4000)

        self.assertFalse(limits.is_memory_warning(1500))
        self.assertTrue(limits.is_memory_warning(2000))
        self.assertTrue(limits.is_memory_warning(3000))

    def test_is_cpu_critical(self):
        """Test CPU critical check."""
        limits = ResourceLimits(max_cpu_percent=95.0)

        self.assertFalse(limits.is_cpu_critical(80.0))
        self.assertTrue(limits.is_cpu_critical(95.0))
        self.assertTrue(limits.is_cpu_critical(100.0))

    def test_is_cpu_warning(self):
        """Test CPU warning check."""
        limits = ResourceLimits(warning_cpu_percent=80.0, max_cpu_percent=95.0)

        self.assertFalse(limits.is_cpu_warning(70.0))
        self.assertTrue(limits.is_cpu_warning(80.0))
        self.assertTrue(limits.is_cpu_warning(90.0))

    def test_is_disk_critical(self):
        """Test disk space critical check."""
        limits = ResourceLimits(critical_disk_gb=5.0)

        self.assertTrue(limits.is_disk_critical(3.0))
        self.assertTrue(limits.is_disk_critical(4.9))
        self.assertFalse(limits.is_disk_critical(5.0))
        self.assertFalse(limits.is_disk_critical(10.0))

    def test_is_disk_warning(self):
        """Test disk space warning check."""
        limits = ResourceLimits(warning_disk_gb=20.0, critical_disk_gb=5.0)

        self.assertTrue(limits.is_disk_warning(15.0))
        self.assertTrue(limits.is_disk_warning(19.9))
        self.assertFalse(limits.is_disk_warning(20.0))
        self.assertFalse(limits.is_disk_warning(30.0))


class TestGlobalResourceLimits(unittest.TestCase):
    """Test global resource limits functions."""

    def test_get_resource_limits_singleton(self):
        """Test that get_resource_limits returns singleton."""
        limits1 = get_resource_limits()
        limits2 = get_resource_limits()
        self.assertIs(limits1, limits2)

    def test_set_resource_limits(self):
        """Test setting global resource limits."""
        new_limits = ResourceLimits(max_memory_mb=8000)

        set_resource_limits(new_limits)

        retrieved = get_resource_limits()
        self.assertEqual(retrieved.max_memory_mb, 8000)

    def test_set_invalid_resource_limits(self):
        """Test that setting invalid limits raises ValueError."""
        invalid_limits = ResourceLimits(max_memory_mb=-1000)

        with self.assertRaises(ValueError):
            set_resource_limits(invalid_limits)


if __name__ == "__main__":
    unittest.main()
