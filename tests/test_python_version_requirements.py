"""Regression coverage for the supported Python runtime floor."""

from types import SimpleNamespace

import setup_validator
import startup_validator


def _version(major: int, minor: int, micro: int = 0) -> SimpleNamespace:
    return SimpleNamespace(major=major, minor=minor, micro=micro)


def test_startup_validator_requires_python_313(monkeypatch) -> None:
    monkeypatch.setattr(startup_validator.sys, "version_info", _version(3, 12))
    valid, message = startup_validator.validate_python_version()
    assert not valid
    assert message is not None
    assert "3.13+" in message


def test_startup_validator_accepts_python_313_and_newer(monkeypatch) -> None:
    for version in ((3, 13), (3, 14), (4, 0)):
        monkeypatch.setattr(startup_validator.sys, "version_info", _version(*version))
        valid, message = startup_validator.validate_python_version()
        assert valid
        assert message is None


def test_setup_validator_requires_python_313(monkeypatch) -> None:
    monkeypatch.setattr(setup_validator.sys, "version_info", _version(3, 12))
    result = setup_validator.check_python_version()
    assert not result.passed
    assert "minimum 3.13" in result.message


def test_setup_validator_accepts_python_313_and_newer(monkeypatch) -> None:
    for version in ((3, 13), (3, 14), (4, 0)):
        monkeypatch.setattr(setup_validator.sys, "version_info", _version(*version))
        assert setup_validator.check_python_version().passed
