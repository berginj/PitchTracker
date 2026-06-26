"""Tests for the setup-time left/right synchronization check (calib.sync_check)."""

from __future__ import annotations

from calib.sync_check import check_sync, pair_timestamps
from contracts.setup import (
    SYNC_VERDICT_GOOD,
    SYNC_VERDICT_POOR,
    SYNC_VERDICT_UNKNOWN,
)


def _stream(start_ns: int, count: int, period_ns: int):
    return [start_ns + i * period_ns for i in range(count)]


def test_pair_timestamps_perfectly_aligned():
    left = _stream(0, 10, 16_000_000)  # 60fps
    right = list(left)
    deltas, unpaired = pair_timestamps(left, right, tolerance_ns=8_000_000)
    assert len(deltas) == 10
    assert unpaired == 0
    assert max(deltas) == 0


def test_pair_timestamps_constant_offset_within_tolerance():
    left = _stream(0, 10, 16_000_000)
    right = [t + 2_000_000 for t in left]  # 2ms constant offset
    deltas, unpaired = pair_timestamps(left, right, tolerance_ns=8_000_000)
    assert len(deltas) == 10
    assert unpaired == 0
    assert all(d == 2_000_000 for d in deltas)


def test_pair_timestamps_counts_unpaired_when_offset_exceeds_tolerance():
    # Right stream shifted by a full frame; greedy nearest still pairs most,
    # but the leading/trailing frames have no partner within tolerance.
    left = _stream(0, 5, 16_000_000)
    right = [t + 20_000_000 for t in left]  # 20ms > 8ms tolerance
    deltas, unpaired = pair_timestamps(left, right, tolerance_ns=8_000_000)
    assert deltas == [] or max(deltas) <= 8_000_000
    assert unpaired > 0


def test_check_sync_good_when_aligned():
    left = _stream(1_000, 60, 16_000_000)
    right = [t + 1_000_000 for t in left]  # 1ms skew
    result = check_sync(left, right, tolerance_ms=8.0, max_speed_mph=60.0)
    assert result.verdict == SYNC_VERDICT_GOOD
    assert result.passed is True
    assert result.sample_count == 60
    assert result.unpaired_count == 0
    assert result.mean_delta_ms == 1.0


def test_check_sync_poor_when_skew_large():
    # 7ms skew (within 8ms tolerance so frames still pair) translates to a large
    # ball-motion error at 90mph -> POOR verdict, not passed.
    left = _stream(0, 60, 16_000_000)
    right = [t + 7_000_000 for t in left]
    result = check_sync(left, right, tolerance_ms=8.0, max_speed_mph=90.0)
    assert result.verdict == SYNC_VERDICT_POOR
    assert result.passed is False
    assert result.max_motion_in > 8.0


def test_check_sync_unknown_when_no_pairs():
    left = _stream(0, 5, 16_000_000)
    right = [t + 100_000_000 for t in left]  # 100ms apart, nothing pairs
    result = check_sync(left, right, tolerance_ms=8.0)
    assert result.verdict == SYNC_VERDICT_UNKNOWN
    assert result.passed is False
    assert result.sample_count == 0


def test_check_sync_payload_round_trips():
    left = _stream(0, 30, 16_000_000)
    right = [t + 1_000_000 for t in left]
    result = check_sync(left, right, tolerance_ms=8.0)
    payload = result.to_payload()
    assert payload["verdict"] == result.verdict
    assert payload["sample_count"] == result.sample_count
    assert set(payload) >= {
        "mean_delta_ms",
        "p95_delta_ms",
        "max_delta_ms",
        "jitter_ms",
        "max_motion_in",
        "tolerance_ms",
        "max_speed_mph",
        "passed",
    }
