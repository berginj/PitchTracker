import inspect

from app.services.analysis import AnalysisService, AnalysisServiceImpl
from app.services.capture import CaptureService, CaptureServiceImpl
from app.services.detection import DetectionService, DetectionServiceImpl
from app.services.recording import RecordingService, RecordingServiceImpl
from app.services.tooling import ToolingService, SubprocessToolingService
from app.pipeline.service_contracts import PipelineService
from app.services.orchestrator import PipelineOrchestrator


def test_service_contracts_are_abstract() -> None:
    assert inspect.isabstract(CaptureService)
    assert inspect.isabstract(DetectionService)
    assert inspect.isabstract(RecordingService)
    assert inspect.isabstract(AnalysisService)
    assert inspect.isabstract(ToolingService)
    assert inspect.isabstract(PipelineService)


def test_service_implementations_match_declared_contracts() -> None:
    assert issubclass(CaptureServiceImpl, CaptureService)
    assert issubclass(DetectionServiceImpl, DetectionService)
    assert issubclass(RecordingServiceImpl, RecordingService)
    assert issubclass(AnalysisServiceImpl, AnalysisService)
    assert issubclass(SubprocessToolingService, ToolingService)
    assert issubclass(PipelineOrchestrator, PipelineService)


def test_pipeline_orchestrator_exposes_public_event_subscription_hooks() -> None:
    assert hasattr(PipelineOrchestrator, "subscribe_event")
    assert hasattr(PipelineOrchestrator, "unsubscribe_event")
