"""Evidence gates for fatigue indicators."""

from analysis.fatigue_detector import FatigueDetector
from app.contracts import PitchSummary


def _pitch(
    index: int,
    run_in: float,
    rise_in: float,
    *,
    movement_validated: bool,
    measurement_status: str = "ESTIMATED",
    speed_source: str = "radar_measurement",
) -> PitchSummary:
    return PitchSummary(
        pitch_id=f"pitch_{index:03d}",
        t_start_ns=index * 1_000_000_000,
        t_end_ns=(index + 1) * 1_000_000_000,
        is_strike=False,
        zone_row=None,
        zone_col=None,
        run_in=run_in,
        rise_in=rise_in,
        speed_mph=80.0,
        rotation_rpm=None,
        sample_count=10,
        trajectory_confidence=0.9,
        measurement_status=measurement_status,
        speed_source=speed_source,
        quality_diagnostics={"movement_validated": movement_validated},
    )


def test_raw_endpoint_displacement_does_not_create_fatigue_movement_claim() -> None:
    pitches = [
        _pitch(index, run_in=float(index * index), rise_in=float(-index * index), movement_validated=False)
        for index in range(1, 11)
    ]

    result = FatigueDetector(baseline_window=5, rolling_window=5).analyze(
        pitches[-5:],
        all_session_pitches=pitches,
    )

    assert result.movement_variance_pct == 0.0
    assert not any("Movement variance" in factor for factor in result.contributing_factors)


def test_validated_movement_remains_available_to_fatigue_detector() -> None:
    detector = FatigueDetector()
    pitches = [
        _pitch(1, 1.0, -1.0, movement_validated=True),
        _pitch(2, 2.0, -2.0, movement_validated=False),
    ]

    stats = detector._compute_window_stats(pitches)

    assert stats["h_movement"]["mean"] == 1.0
    assert stats["h_movement"]["max"] == 1.0


def test_fatigue_is_unavailable_for_mixed_speed_provenance() -> None:
    pitches = [
        _pitch(index, 1.0, -1.0, movement_validated=False, speed_source=(
            "radar_measurement" if index < 6 else "vision_fit"
        ))
        for index in range(1, 11)
    ]

    result = FatigueDetector().analyze(pitches[-5:], pitches)

    assert result.available is False
    assert result.recommendation == "Unavailable"


def test_rejected_speed_and_trajectory_confidence_do_not_create_fatigue_claim() -> None:
    pitches = [
        _pitch(
            index,
            1.0,
            -1.0,
            movement_validated=False,
            measurement_status="REJECTED",
        )
        for index in range(1, 11)
    ]

    result = FatigueDetector().analyze(pitches[-5:], pitches)

    assert result.available is False
    assert result.trajectory_quality_drop == 0.0
