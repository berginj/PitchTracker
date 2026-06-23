"""Packaging guardrails for release artifacts."""

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_launcher_spec_does_not_bundle_runtime_local_config_state():
    spec_text = (ROOT / "launcher.spec").read_text(encoding="utf-8")

    assert "('configs', 'configs')" not in spec_text
    assert '("configs", "configs")' not in spec_text
    assert "configs/default.yaml" in spec_text
    assert "configs/snapdragon.yaml" in spec_text


def test_installer_only_adds_checked_in_config_yaml_directly():
    installer_text = (ROOT / "installer.iss").read_text(encoding="utf-8")

    assert 'Source: "configs\\*.yaml"' in installer_text
    assert 'Source: "configs\\*"' not in installer_text
