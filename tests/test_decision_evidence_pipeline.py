from __future__ import annotations

import threading
import time
from pathlib import Path

from app.events.event_types import (
    FrameProcessingOpportunityEvent,
    FrameProcessingOutcomeEvent,
    PairingOutcomeEvent,
)
from app.pipeline.detection.decision_ids import canonicalize_detection_ids, frame_decision_id
from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.detection.threading_pool import DetectionThreadPool
from app.pipeline.recording.evidence_journal import SessionEvidenceJournal, load_session_evidence_journal
from app.pipeline.replay.decision_replay import reconcile_decision_journal
from configs.settings import load_config
from contracts import Detection, Frame
from contracts.evidence import PairingOutcomeEvidence
from stereo.association import StereoMatch, StereoMatcher
from stereo.global_assignment import evaluate_stereo_assignment
from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry


def _frame(camera: str, index: int, timestamp_ns: int | None = None) -> Frame:
    return Frame(camera, index, index if timestamp_ns is None else timestamp_ns, None, 640, 480, "GRAY8")


def _detection(camera: str, candidate_id: str, u: float, v: float = 100.0) -> Detection:
    return Detection(camera, 1, 1, u, v, 3.0, 0.9, candidate_id=candidate_id)


def _processor() -> DetectionProcessor:
    config = load_config(Path("configs/default.yaml"))
    matcher = SimpleStereoMatcher(
        StereoGeometry(
            baseline_ft=1.0,
            focal_length_px=1000.0,
            cx=320.0,
            cy=240.0,
            epipolar_epsilon_px=3.0,
        )
    )
    return DetectionProcessor(config, matcher, None, None, None, None, lambda: 1.45)


def test_candidate_ids_are_stable_without_changing_detector_order() -> None:
    frame = _frame("left", 4, 100)
    low = Detection("left", 4, 100, 10.0, 20.0, 3.0, 0.8)
    high = Detection("left", 4, 100, 30.0, 20.0, 3.0, 0.9)
    forward = canonicalize_detection_ids(frame, [low, high])
    reverse = canonicalize_detection_ids(frame, [high, low])

    assert [item.u for item in forward] == [10.0, 30.0]
    assert [item.u for item in reverse] == [30.0, 10.0]
    assert {item.u: item.candidate_id for item in forward} == {
        item.u: item.candidate_id for item in reverse
    }


def test_frame_conservation_covers_queue_eviction_and_stop_cancellation() -> None:
    entered = threading.Event()
    release = threading.Event()
    opportunities: list[FrameProcessingOpportunityEvent] = []
    outcomes: list[FrameProcessingOutcomeEvent] = []
    pool = DetectionThreadPool()
    pool.set_frame_decision_callbacks(opportunities.append, outcomes.append)

    def detect(_label, _frame):
        entered.set()
        release.wait(timeout=5.0)
        return []

    pool.set_detect_callback(detect)
    pool.set_stereo_callback(lambda *_args: None)
    pool.start(queue_size=1)
    pool.enqueue_frame("left", _frame("left", 1))
    assert entered.wait(timeout=1.0)
    pool.enqueue_frame("left", _frame("left", 2))
    pool.enqueue_frame("left", _frame("left", 3))
    pool.stop()
    release.set()
    time.sleep(0.05)

    stats = pool.get_runtime_stats()["frame_conservation"]
    assert len(opportunities) == 3
    assert len(outcomes) == 3
    assert len({event.opportunity_id for event in outcomes}) == 3
    assert "INPUT_QUEUE_DROPPED" in {event.status for event in outcomes}
    assert stats == {
        "offered": 3,
        "terminal": 3,
        "outstanding": 0,
        "balanced": True,
        "terminal_outcomes": stats["terminal_outcomes"],
    }


def test_pairing_conservation_covers_deque_eviction_and_stop_flush() -> None:
    processor = _processor()
    outcomes: list[PairingOutcomeEvidence] = []
    processor.set_pairing_outcome_callback(outcomes.append)

    frames = [_frame("left", index, index * 1_000_000) for index in range(7)]
    for frame in frames:
        processor.process_detection_result("left", frame, [])
    processor.flush_pairing_buffers()

    assert len(outcomes) == 7
    assert len({outcome.left_frame_id for outcome in outcomes}) == 7
    assert outcomes[0].reason_codes == ("BUFFER_EVICTED",)
    assert all(outcome.status == "UNMATCHED" for outcome in outcomes)
    assert sum(outcome.frame_count for outcome in outcomes) == len(frames)


class _GraphMatcher(StereoMatcher):
    _costs = {
        ("L1", "R1"): 0.0,
        ("L1", "R2"): 1.0,
        ("L2", "R1"): 1.0,
    }

    def match(self, left, right):
        cost = self._costs.get((left.candidate_id, right.candidate_id))
        if cost is None:
            return None
        return StereoMatch(left, right, cost, 1.0)

    def triangulate(self, match):  # pragma: no cover - assignment-only test
        raise NotImplementedError

    def pair_timestamp(self, left_ns, right_ns):
        return (left_ns + right_ns) // 2, False


def test_global_shadow_finds_cardinality_lost_by_greedy() -> None:
    decision = evaluate_stereo_assignment(
        "pair-1",
        [_detection("left", "L1", 10), _detection("left", "L2", 20)],
        [_detection("right", "R1", 9), _detection("right", "R2", 19)],
        epipolar_tolerance=3.0,
        matcher=_GraphMatcher(),
        mode="shadow_v2",
    )

    assert decision.primary_algorithm == "greedy_v1"
    assert len(decision.assigned_edge_ids) == 1
    assert len(decision.shadow_assigned_edge_ids) == 2


def test_session_journal_reconciles_exact_denominators(tmp_path: Path) -> None:
    frame = _frame("left", 1, 100)
    frame_id = frame_decision_id(frame)
    opportunity = FrameProcessingOpportunityEvent("opp-1", frame_id, "left", 1, 100)
    outcome = FrameProcessingOutcomeEvent("opp-1", frame_id, "left", 1, 100, "PROCESSING_COMPLETE")
    pairing = PairingOutcomeEvent(
        PairingOutcomeEvidence(
            outcome_id="pairing-1",
            status="UNMATCHED",
            left_frame_id=frame_id,
            left_timestamp_ns=100,
            reason_codes=("FLUSHED_ON_STOP",),
        )
    )
    journal = SessionEvidenceJournal(tmp_path)
    assert journal.submit_event(opportunity).accepted
    assert journal.submit_event(outcome).accepted
    assert journal.submit_event(pairing).accepted
    manifest = journal.close()

    records = load_session_evidence_journal(manifest)
    report = reconcile_decision_journal(records)
    assert report.valid, report.errors
    assert report.metrics["frame_conservation"]["balanced"] is True
    assert report.metrics["pairing"]["unmatched_rate"] == {
        "numerator": 1,
        "denominator": 1,
        "value": 1.0,
    }
