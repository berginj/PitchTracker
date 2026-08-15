"""Characterization tests for multi-session trend analysis."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from analysis.trend_analyzer import SessionSummary, TrendAnalyzer


def _pitch(speed, run, rise, strike, pitch_type=None):
    return SimpleNamespace(
        speed_mph=speed,
        run_in=run,
        rise_in=rise,
        is_strike=strike,
        pitch_type=pitch_type,
    )


def _summary(
    session_id: str,
    date: str,
    velocity: float,
    strike_pct: float,
    consistency: float,
    horizontal: float = 2.0,
    vertical: float = -1.0,
) -> SessionSummary:
    return SessionSummary(
        session_id=session_id,
        session_date=date,
        pitcher_id="pitcher-1",
        total_pitches=10,
        avg_velocity_mph=velocity,
        max_velocity_mph=velocity + 1,
        min_velocity_mph=velocity - 1,
        velocity_std=1.0,
        avg_horizontal_in=horizontal,
        avg_vertical_in=vertical,
        strike_percentage=strike_pct,
        consistency_score=consistency,
    )


def _write_summary(analyzer: TrendAnalyzer, summary: SessionSummary) -> None:
    pitcher_dir = analyzer.summaries_dir / "pitcher-1"
    pitcher_dir.mkdir(exist_ok=True)
    (pitcher_dir / f"{summary.session_id}.json").write_text(
        json.dumps(summary.to_dict()),
        encoding="utf-8",
    )


def test_summarize_session_preserves_missing_data_and_units(tmp_path):
    analyzer = TrendAnalyzer(tmp_path)
    pitches = [
        _pitch(80.0, 2.0, None, True, "fastball"),
        _pitch(None, None, -1.0, False),
        _pitch(84.0, 4.0, -3.0, True, "fastball"),
    ]

    result = analyzer.summarize_session(
        "session-1",
        pitches,
        pitcher_id="pitcher-1",
        session_date="2026-08-01T10:00:00",
    )

    assert result.avg_velocity_mph == 82.0
    assert result.velocity_std == pytest.approx(2.8284271247461903)
    assert result.avg_horizontal_in == 3.0
    assert result.avg_vertical_in == -2.0
    assert result.strike_percentage == pytest.approx(2 / 3)
    assert result.consistency_score == pytest.approx(0.965507)
    assert result.pitch_type_counts == {"fastball": 2}
    stored = json.loads((tmp_path / "pitcher-1" / "session-1.json").read_text())
    assert stored == result.to_dict()


def test_empty_session_uses_zero_statistics(tmp_path):
    result = TrendAnalyzer(tmp_path).summarize_session(
        "empty",
        [],
        session_date="2026-08-01",
    )

    assert result.total_pitches == 0
    assert result.avg_velocity_mph == 0.0
    assert result.velocity_std == 0.0
    assert result.strike_percentage == 0.0
    assert result.consistency_score == 1.0
    assert (tmp_path / "unknown" / "empty.json").exists()


def test_analyze_trends_sorts_sessions_and_preserves_alert_order(tmp_path):
    analyzer = TrendAnalyzer(tmp_path)
    summaries = [
        _summary("late", "2026-08-03", 70.0, 0.40, 0.70),
        _summary("early", "2026-08-01", 90.0, 0.80, 0.90),
        _summary("middle", "2026-08-02", 80.0, 0.60, 0.80),
    ]
    for summary in summaries:
        _write_summary(analyzer, summary)

    report = analyzer.analyze_trends("pitcher-1")

    assert report is not None
    assert report.session_velocities == [
        ("2026-08-01", 90.0),
        ("2026-08-02", 80.0),
        ("2026-08-03", 70.0),
    ]
    assert report.velocity_trend_mph_per_session == pytest.approx(-10.0)
    assert report.strike_pct_trend == pytest.approx(-0.2)
    assert report.consistency_trend == pytest.approx(-0.1)
    assert report.velocity_current_vs_peak == pytest.approx(-22.2222222222)
    assert report.alerts == [
        "Velocity declining at 10.0 mph per session",
        "Current velocity 22.2% below peak performance",
        "Strike percentage trending downward",
    ]


def test_analyze_trends_requires_minimum_valid_summaries(tmp_path, capsys):
    analyzer = TrendAnalyzer(tmp_path)
    _write_summary(analyzer, _summary("valid", "2026-08-01", 80.0, 0.5, 0.8))
    malformed = tmp_path / "pitcher-1" / "malformed.json"
    malformed.write_text("{bad json", encoding="utf-8")

    assert analyzer.analyze_trends("pitcher-1", min_sessions=2) is None
    assert f"Error loading summary {malformed}" in capsys.readouterr().out


def test_compare_to_baseline_uses_most_recent_sessions(tmp_path):
    analyzer = TrendAnalyzer(tmp_path)
    old = _summary("old", "2026-07-01", 60.0, 0.2, 0.8)
    recent_1 = _summary("recent-1", "2026-08-01", 80.0, 0.5, 0.8)
    recent_2 = _summary("recent-2", "2026-08-02", 80.0, 0.5, 0.8)
    current = _summary("current", "2026-08-03", 88.0, 0.7, 0.8, 4.0, 1.0)
    for summary in [old, recent_1, recent_2, current]:
        _write_summary(analyzer, summary)

    comparison = analyzer.compare_to_baseline(current, baseline_sessions=2)

    assert comparison is not None
    assert comparison.velocity_vs_baseline_pct == 10.0
    assert comparison.velocity_vs_baseline_status == "significantly_above"
    assert comparison.horizontal_vs_baseline_in == 2.0
    assert comparison.vertical_vs_baseline_in == 2.0
    assert comparison.movement_status == "significant_shift"
    assert comparison.strike_pct_vs_baseline == pytest.approx(0.2)
    assert comparison.accuracy_status == "significantly_above"
    assert comparison.overall_status == "normal"
    assert comparison.recommendations == [
        "Velocity above baseline - maintain current approach",
        "Significant movement variation - review release point consistency",
        "Strong strike percentage - consider expanding zone usage",
    ]


def test_baseline_requires_pitcher_and_two_prior_sessions(tmp_path):
    analyzer = TrendAnalyzer(tmp_path)
    no_pitcher = _summary("current", "2026-08-03", 80.0, 0.5, 0.8)
    no_pitcher.pitcher_id = None
    assert analyzer.compare_to_baseline(no_pitcher) is None

    current = _summary("current", "2026-08-03", 80.0, 0.5, 0.8)
    _write_summary(analyzer, current)
    _write_summary(analyzer, _summary("prior", "2026-08-02", 80.0, 0.5, 0.8))
    assert analyzer.compare_to_baseline(current) is None


@pytest.mark.parametrize(
    ("slope", "threshold", "higher_is_better", "expected"),
    [
        (0.49, 0.5, True, "stable"),
        (0.5, 0.5, True, "improving"),
        (-0.5, 0.5, True, "declining"),
        (0.5, 0.5, False, "declining"),
    ],
)
def test_trend_classification_boundaries(
    tmp_path,
    slope,
    threshold,
    higher_is_better,
    expected,
):
    analyzer = TrendAnalyzer(tmp_path)
    assert analyzer._classify_trend(slope, threshold, higher_is_better) == expected
