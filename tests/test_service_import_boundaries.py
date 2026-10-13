"""Fresh processes expose import cycles and numerical-worker dependencies."""

from pathlib import Path
import subprocess
import sys


def _run(source: str) -> None:
    result = subprocess.run(
        [sys.executable, "-c", source], cwd=Path(__file__).parents[1],
        capture_output=True, text=True, timeout=30,
    )
    assert result.returncode == 0, result.stderr


def test_pitch_analyzer_can_be_imported_first():
    _run("from app.pipeline.analysis.pitch_summary import PitchAnalyzer; assert PitchAnalyzer")


def test_numerical_worker_import_does_not_load_concrete_services():
    _run("""
import sys
from app.services.analysis.fit_worker import FitWorkerPool
assert FitWorkerPool
for module in ('app.services.capture.implementation', 'app.services.analysis.implementation',
               'app.services.recording.implementation', 'PySide6'):
    assert module not in sys.modules, module
""")


def test_service_public_exports_remain_compatible():
    _run("""
import app.services as services
from app.services.capture import CaptureService
from app.services.analysis import AnalysisService, AnalysisServiceImpl
from app.services.rig_profile import RigProfileService
assert services.CaptureService is CaptureService
assert services.AnalysisService is AnalysisService
assert services.RigProfileService is RigProfileService
assert AnalysisServiceImpl
try:
    services.not_a_service
except AttributeError:
    pass
else:
    raise AssertionError('unknown public export was accepted')
""")
