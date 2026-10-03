"""Hardware-free tooling validation keeps physical camera checks opt-in for smoke tests."""

from unittest.mock import Mock

import pytest

from app.services.tooling.worker_main import _handle_validate_environment
import startup_validator


@pytest.mark.parametrize("camera_check", [True, False, None])
def test_tooling_camera_check_mode_is_explicit(monkeypatch, camera_check):
    monkeypatch.setattr(startup_validator, "validate_python_version", lambda: (True, None))
    monkeypatch.setattr(startup_validator, "validate_dependencies", lambda: (True, None))
    monkeypatch.setattr(startup_validator, "check_configuration", lambda: ([], []))
    cameras = Mock(return_value=(["camera warning"], []))
    monkeypatch.setattr(startup_validator, "check_cameras", cameras)
    payload = {} if camera_check is None else {"check_cameras": camera_check}
    result = _handle_validate_environment(payload)
    assert result["errors"] == []
    if camera_check is False:
        cameras.assert_not_called()
        assert result["warnings"] == []
    else:
        cameras.assert_called_once_with()
        assert result["warnings"] == ["camera warning"]


@pytest.mark.parametrize("value", ["false", 0, None])
def test_tooling_camera_check_rejects_non_boolean(monkeypatch, value):
    cameras = Mock()
    monkeypatch.setattr(startup_validator, "check_cameras", cameras)
    with pytest.raises(ValueError, match="must be a boolean"):
        _handle_validate_environment({"check_cameras": value})
    cameras.assert_not_called()
