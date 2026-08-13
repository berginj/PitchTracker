"""Characterization tests for the PairBuffer module."""

from __future__ import annotations

from unittest.mock import MagicMock

from contracts import Detection, Frame

from app.pipeline.detection.pair_buffer import PairBuffer


def _make_frame(camera_id: str, frame_index: int, t_ns: int) -> Frame:
    return Frame(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=t_ns,
        image=None,
        width=640,
        height=480,
        pixfmt="gray8",
        capture_epoch="test",
    )


def _make_detection(camera_id: str, frame_index: int, t_ns: int) -> Detection:
    return Detection(
        camera_id=camera_id,
        frame_index=frame_index,
        t_capture_monotonic_ns=t_ns,
        u=320.0,
        v=240.0,
        radius_px=5.0,
        confidence=0.9,
    )


def _make_config(pairing_tolerance_ms=10.0, use_frame_index=False, offset_ns=0):
    cfg = MagicMock()
    cfg.stereo.pairing_tolerance_ms = pairing_tolerance_ms
    cfg.stereo.use_frame_index_pairing = use_frame_index
    cfg.stereo.frame_index_tolerance = 1
    cfg.stereo.time_sync_offset_ns = offset_ns
    return cfg


class TestPairBufferMatched:
    """Verify matched frames produce PAIRED outcomes."""

    def test_timestamp_pair_produces_matched(self):
        config = _make_config(pairing_tolerance_ms=10.0)
        buf = PairBuffer(config)
        left = _make_frame("left", 0, 1_000_000)
        right = _make_frame("right", 0, 1_500_000)

        pairs, outcomes = buf.push("left", left, [])
        assert pairs == []
        pairs, outcomes = buf.push("right", right, [])
        assert len(pairs) == 1
        assert any(o.status == "PAIRED" for o in outcomes)

    def test_frame_index_pair_produces_matched(self):
        config = _make_config(use_frame_index=True)
        buf = PairBuffer(config)
        left = _make_frame("left", 5, 1_000_000)
        right = _make_frame("right", 5, 2_000_000)

        buf.push("left", left, [])
        pairs, outcomes = buf.push("right", right, [])
        assert len(pairs) == 1
        assert any(o.status == "PAIRED" for o in outcomes)


class TestPairBufferUnmatched:
    """Verify unmatched frames produce UNMATCHED outcomes."""

    def test_buffer_eviction_produces_unmatched(self):
        config = _make_config(pairing_tolerance_ms=1.0)
        buf = PairBuffer(config)
        buf._maxlen = 2

        all_outcomes = []
        for i in range(3):
            left = _make_frame("left", i, i * 100_000_000)
            _, outcomes = buf.push("left", left, [])
            all_outcomes.extend(outcomes)

        assert any(
            o.status == "UNMATCHED" and "BUFFER_EVICTED" in (o.reason_codes or ())
            for o in all_outcomes
        )

    def test_timestamp_behind_produces_unmatched(self):
        config = _make_config(pairing_tolerance_ms=1.0)
        buf = PairBuffer(config)
        left = _make_frame("left", 0, 0)
        right = _make_frame("right", 0, 50_000_000)  # 50ms behind

        buf.push("left", left, [])
        pairs, outcomes = buf.push("right", right, [])
        assert pairs == []
        unmatched = [o for o in outcomes if o.status == "UNMATCHED"]
        assert len(unmatched) >= 1


class TestPairBufferEmpty:
    """Verify empty buffers produce no outcomes."""

    def test_flush_empty_buffer_returns_no_outcomes(self):
        config = _make_config()
        buf = PairBuffer(config)
        outcomes = buf.flush()
        assert outcomes == ()


class TestPairBufferFlush:
    """Verify flush gives terminal outcomes to all buffered frames."""

    def test_flush_gives_terminal_to_remaining(self):
        config = _make_config(pairing_tolerance_ms=10.0)
        buf = PairBuffer(config)
        left = _make_frame("left", 0, 1_000_000)
        buf.push("left", left, [])

        outcomes = buf.flush("SESSION_END")
        assert len(outcomes) == 1
        assert outcomes[0].status == "UNMATCHED"
        assert "SESSION_END" in outcomes[0].reason_codes
