from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_ui_uses_canonical_contracts_instead_of_legacy_pipeline_service() -> None:
    offenders = [
        path
        for path in (ROOT / "ui").rglob("*.py")
        if "from app.pipeline_service import" in path.read_text(encoding="utf-8")
    ]
    assert offenders == []


def test_compatibility_qt_entrypoint_delegates_to_launcher() -> None:
    source = (ROOT / "ui" / "qt_app.py").read_text(encoding="utf-8")
    assert "from launcher import main as launcher_main" in source
    assert "launcher_main()" in source


def test_legacy_path_documentation_names_the_canonical_runtime() -> None:
    documentation = (
        ROOT / "docs" / "architecture" / "legacy-paths.md"
    ).read_text(encoding="utf-8")
    assert "PipelineOrchestrator" in documentation
    assert "InProcessPipelineService" in documentation
