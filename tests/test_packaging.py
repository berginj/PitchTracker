"""Packaging guardrails for release artifacts."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PROPOSALS = ROOT / "docs" / "review" / "workflow-proposals"


def test_launcher_spec_does_not_bundle_runtime_local_config_state():
    spec_text = (ROOT / "launcher.spec").read_text(encoding="utf-8")

    assert "('configs', 'configs')" not in spec_text
    assert '("configs", "configs")' not in spec_text
    assert "configs/default.yaml" in spec_text
    assert "configs/snapdragon.yaml" in spec_text


def test_launcher_spec_keeps_pyside_runtime_dependencies():
    spec_text = (ROOT / "launcher.spec").read_text(encoding="utf-8")
    excludes_text = spec_text.split("excludes = [", 1)[1].split("]", 1)[0]

    assert "'inspect'" not in excludes_text


def test_all_packaged_entry_points_enable_multiprocessing_freeze_support():
    for entry_point in ("launcher.py", "ui/qt_app.py"):
        source = (ROOT / entry_point).read_text(encoding="utf-8")
        assert "multiprocessing.freeze_support()" in source


def test_installer_only_adds_checked_in_config_yaml_directly():
    installer_text = (ROOT / "installer.iss").read_text(encoding="utf-8")

    assert 'Source: "configs\\*.yaml"' in installer_text
    assert 'Source: "configs\\*"' not in installer_text


def test_proposed_github_actions_are_pinned_to_commit_shas():
    workflows = list(WORKFLOW_PROPOSALS.glob("*.yml"))
    assert workflows
    uses_pattern = re.compile(r"uses:\s+[^@\s]+@([^\s#]+)")

    for workflow in workflows:
        for action_ref in uses_pattern.findall(workflow.read_text(encoding="utf-8")):
            assert re.fullmatch(
                r"[0-9a-f]{40}", action_ref
            ), f"{workflow.name} uses a mutable action reference: {action_ref}"


def test_proposed_release_workflow_builds_checksum_without_publishing():
    workflow_text = (WORKFLOW_PROPOSALS / "package-installer.yml").read_text(encoding="utf-8")

    assert "workflow_dispatch:" in workflow_text
    assert "build_installer.ps1 -Clean" in workflow_text
    assert "Get-FileHash" in workflow_text
    assert "gh release create" not in workflow_text


def test_local_installer_build_generates_checksum():
    script_text = (ROOT / "build_installer.ps1").read_text(encoding="utf-8")

    assert "Get-FileHash" in script_text
    assert '".sha256"' in script_text or ".sha256" in script_text
