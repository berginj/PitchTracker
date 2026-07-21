"""Focused adversarial tests for runtime loss/error accounting."""

from types import SimpleNamespace
from unittest.mock import Mock
from pathlib import Path

import pytest

from app.events.event_bus import EventBus
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.services.detection.implementation import DetectionServiceImpl
from app.services.orchestrator.pipeline_orchestrator import PipelineOrchestrator
from configs.settings import load_config


def _config():
    return load_config(Path("configs/default.yaml"))


def test_pool_failure_is_cumulative_and_not_an_empty_result() -> None:
    pool = DetectionThreadPool()
    calls = iter((RuntimeError("boom"), []))

    def detect(_label, _frame):
        result = next(calls)
        if isinstance(result, Exception):
            raise result
        return result

    pool.set_detect_callback(detect)
    assert pool._detect_frame("left", Mock()) is None
    assert pool._detect_frame("left", Mock()) == []

    stats = pool.get_runtime_stats()["left"]
    assert stats["attempts"] == 2
    assert stats["failures"] == 1
    assert stats["failure_rate"] == {"numerator": 1, "denominator": 2, "value": 0.5}
    assert pool.get_error_stats()["left"] == 0  # consecutive counter recovered


def test_pool_zero_opportunity_and_queue_drop_rates_are_explicit() -> None:
    pool = DetectionThreadPool()
    initial = pool.get_runtime_stats()
    assert initial["left"]["failure_rate"] == {"numerator": 0, "denominator": 0, "value": None}
    assert initial["results"]["queue_drop_rate"]["value"] is None

    target = __import__("queue").Queue(maxsize=1)
    pool._queue_put_drop_oldest(target, object(), queue_name="left")
    pool._queue_put_drop_oldest(target, object(), queue_name="left")
    queued = pool.get_runtime_stats()["left"]
    assert queued["queue_drops"] == 1
    assert queued["queue_drop_rate"] == {"numerator": 1, "denominator": 2, "value": 0.5}


def test_service_detector_exception_reaches_pool_boundary() -> None:
    service = DetectionServiceImpl(EventBus(), _config())
    service._left_detector = SimpleNamespace(detect=Mock(side_effect=RuntimeError("detector failed")))

    with pytest.raises(RuntimeError, match="detector failed"):
        service._detect_frame("left", Mock())


def test_detection_rates_do_not_claim_zero_error_without_opportunity() -> None:
    service = DetectionServiceImpl(EventBus(), _config())
    diagnostics = service.get_quality_diagnostics()

    assert diagnostics["detection"]["stereo_detection_utilization"] is None
    assert diagnostics["detection"]["tracklet_start_rate"] is None
    assert diagnostics["detection_loss"] == {"numerator": 0, "denominator": 0, "value": None}
    assert all(rate is None for rate in diagnostics["pair_outcomes"]["rejection_rates"].values())


def test_stereo_detection_utilization_uses_two_detections_and_is_bounded() -> None:
    service = DetectionServiceImpl(EventBus(), _config())
    service._running = True
    service._detection_start_time = __import__("time").time() - 1.0
    service._detection_count = 4
    service._observation_count = 1
    assert service.get_detection_stats()["stereo_detection_utilization"] == 0.5

    service._observation_count = 3
    assert service.get_detection_stats()["stereo_detection_utilization"] == 1.0


def test_orchestrator_budget_includes_processing_failures() -> None:
    orchestrator = PipelineOrchestrator()
    orchestrator._detection_service = SimpleNamespace(
        get_quality_diagnostics=lambda: {
            "detection": {"tracklet_start_rate": 0.0},
            "detection_loss": {"numerator": 2, "denominator": 10, "value": 0.2},
            "pair_outcomes": {
                "rejection_rates": {
                    "PAIR_SKEW_OUT_OF_TOLERANCE": 0.0,
                    "NO_VALID_STEREO_ASSOCIATION": 0.0,
                }
            },
            "sync": {"p95_delta_ms": 0.0, "sync_quality": "GOOD"},
            "drift": {"state": "PASS"},
        }
    )
    orchestrator._recording_service = SimpleNamespace(
        get_frame_writer_stats=lambda: {"submitted": 10, "written": 9, "dropped": 0, "failed": 1}
    )
    orchestrator._analysis_service = SimpleNamespace(
        get_worker_stats=lambda: {"submitted": 4, "completed": 3, "dropped": 0, "failed": 1}
    )

    diagnostics = orchestrator.get_quality_diagnostics()
    metrics = diagnostics["quality"]["metrics"]
    assert metrics["detection_loss_rate"] == 0.2
    assert metrics["recording_failure_rate"] == 0.1
    assert metrics["analysis_failure_rate"] == 0.25
    assert diagnostics["recording"]["failure_rate_evidence"] == {
        "numerator": 1,
        "denominator": 10,
        "value": 0.1,
    }
    assert "DETECTION_LOSS_RATE_EXCEEDS_REJECT_LIMIT" in diagnostics["quality"]["reason_codes"]
