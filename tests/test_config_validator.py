"""Unit tests for configuration validation (Phase 4 Fix #4)."""

import unittest
from pathlib import Path
from unittest.mock import Mock

from app.validation import ConfigValidator, ValidationError


class TestConfigValidator(unittest.TestCase):
    """Test configuration validator."""

    def setUp(self):
        """Set up test fixtures."""
        self.validator = ConfigValidator()

        # Create mock config with valid defaults (spec to prevent auto-attributes)
        self.mock_config = Mock(spec=["camera"])
        self.mock_config.camera = Mock(spec=["width", "height", "fps", "exposure"])
        self.mock_config.camera.width = 1280
        self.mock_config.camera.height = 720
        self.mock_config.camera.fps = 30
        self.mock_config.camera.exposure = 100

    def test_valid_config_passes(self):
        """Test that valid configuration passes validation."""
        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertTrue(is_valid)
        self.assertEqual(len([i for i in issues if i.severity == "error"]), 0)

    def test_invalid_camera_width(self):
        """Test that invalid camera width is caught."""
        self.mock_config.camera.width = -640
        is_valid, issues = self.validator.validate(self.mock_config)

        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertGreater(len(errors), 0)
        self.assertTrue(any("width" in e.field for e in errors))

    def test_invalid_camera_height(self):
        """Test that invalid camera height is caught."""
        self.mock_config.camera.height = 0
        is_valid, issues = self.validator.validate(self.mock_config)

        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(any("height" in e.field for e in errors))

    def test_invalid_fps(self):
        """Test that invalid FPS is caught."""
        self.mock_config.camera.fps = -30
        is_valid, issues = self.validator.validate(self.mock_config)

        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(any("fps" in e.field for e in errors))

    def test_unusual_resolution_warns(self):
        """Test that unusual resolution generates warning."""
        self.mock_config.camera.width = 123
        self.mock_config.camera.height = 456
        is_valid, issues = self.validator.validate(self.mock_config)

        # Should pass but with warning
        self.assertTrue(is_valid)
        warnings = [i for i in issues if i.severity == "warning"]
        self.assertGreater(len(warnings), 0)
        self.assertTrue(any("resolution" in i.field for i in warnings))

    def test_high_fps_warns(self):
        """Test that very high FPS generates warning."""
        self.mock_config.camera.fps = 150
        is_valid, issues = self.validator.validate(self.mock_config)

        self.assertTrue(is_valid)
        warnings = [i for i in issues if i.severity == "warning"]
        self.assertTrue(any("fps" in i.field for i in warnings))

    def test_invalid_recording_quality(self):
        """Test that invalid recording quality is caught."""
        self.mock_config.recording = Mock(spec=["quality"])
        self.mock_config.recording.quality = 150  # Should be 0-100

        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(any("quality" in e.field for e in errors))

    def test_large_buffer_size_warns(self):
        """Test that large buffer size generates warning."""
        self.mock_config.recording = Mock(spec=["buffer_size"])
        self.mock_config.recording.buffer_size = 150

        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertTrue(is_valid)
        warnings = [i for i in issues if i.severity == "warning"]
        self.assertTrue(any("buffer_size" in i.field for i in warnings))

    def test_invalid_confidence_threshold(self):
        """Test that invalid confidence threshold is caught."""
        self.mock_config.detection = Mock(spec=["confidence_threshold"])
        self.mock_config.detection.confidence_threshold = 1.5  # Should be 0.0-1.0

        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(any("confidence" in e.field for e in errors))

    def test_low_confidence_warns(self):
        """Test that very low confidence threshold warns."""
        self.mock_config.detection = Mock(spec=["confidence_threshold"])
        self.mock_config.detection.confidence_threshold = 0.2

        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertTrue(is_valid)
        warnings = [i for i in issues if i.severity == "warning"]
        self.assertTrue(any("confidence" in i.field for i in warnings))

    def test_invalid_focal_length(self):
        """Test that invalid focal length is caught."""
        self.mock_config.calibration = Mock(spec=["focal_length"])
        self.mock_config.calibration.focal_length = -500

        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(any("focal_length" in e.field for e in errors))

    def test_low_focal_length_warns(self):
        """Test that very low focal length warns."""
        self.mock_config.calibration = Mock(spec=["focal_length"])
        self.mock_config.calibration.focal_length = 50

        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertTrue(is_valid)
        warnings = [i for i in issues if i.severity == "warning"]
        self.assertTrue(any("focal_length" in i.field for i in warnings))

    def test_invalid_baseline(self):
        """Test that invalid baseline is caught."""
        self.mock_config.calibration = Mock(spec=["baseline"])
        self.mock_config.calibration.baseline = 0

        is_valid, issues = self.validator.validate(self.mock_config)
        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(any("baseline" in e.field for e in errors))

    def test_missing_camera_config(self):
        """Test that missing camera config is caught."""
        config_no_camera = Mock(spec=[])  # No attributes

        is_valid, issues = self.validator.validate(config_no_camera)
        self.assertFalse(is_valid)
        errors = [i for i in issues if i.severity == "error"]
        self.assertTrue(any("camera" in e.field for e in errors))


class TestValidationError(unittest.TestCase):
    """Test ValidationError dataclass."""

    def test_validation_error_creation(self):
        """Test creating ValidationError."""
        error = ValidationError(
            field="test.field",
            message="Test error message",
            severity="error"
        )

        self.assertEqual(error.field, "test.field")
        self.assertEqual(error.message, "Test error message")
        self.assertEqual(error.severity, "error")

    def test_validation_error_default_severity(self):
        """Test that default severity is 'error'."""
        error = ValidationError(
            field="test",
            message="Test"
        )

        self.assertEqual(error.severity, "error")


if __name__ == "__main__":
    unittest.main()
