"""Tests for stereo camera synchronization diagnostics."""

from __future__ import annotations

from app.pipeline.sync_diagnostics import summarize_sync_quality


def test_sync_quality_reports_ball_motion_inches() -> None:
    stats = summarize_sync_quality(
        deltas_ns=[1_000_000, 2_000_000, 3_000_000],
        total_paired=3,
        dropped_sync=0,
        max_speed_mph=60.0,
    )

    assert stats["sync_quality"] == "GOOD"
    assert abs(stats["mean_motion_in_at_max_speed"] - 2.112) < 0.01
    assert stats["max_motion_in_at_max_speed"] > 3.0


def test_sync_quality_flags_large_skew_as_poor() -> None:
    stats = summarize_sync_quality(
        deltas_ns=[10_000_000, 12_000_000, 15_000_000],
        total_paired=3,
        dropped_sync=2,
        max_speed_mph=60.0,
    )

    assert stats["sync_quality"] == "POOR"
    assert stats["p95_motion_in_at_max_speed"] > 12.0
    assert "hardware sync" in stats["sync_recommendation"]


def test_sync_quality_handles_empty_samples() -> None:
    stats = summarize_sync_quality([], total_paired=0, dropped_sync=0)

    assert stats["sync_quality"] == "UNKNOWN"
    assert stats["sync_recommendation"] == "No paired frames available yet."
