"""Tests for the canonical active pitch-result contract."""

from app.contracts import PitchResult, PitchSummary, measurement_is_usable, pitch_summary_from_dict
from contracts import MeasurementStatus


def test_pitch_result_is_the_active_pitch_summary_contract() -> None:
    assert PitchResult is PitchSummary


def test_measurement_status_round_trips_as_historical_string_value() -> None:
    pitch = PitchResult(
        pitch_id="p1",
        t_start_ns=1,
        t_end_ns=2,
        is_strike=False,
        zone_row=None,
        zone_col=None,
        run_in=0.0,
        rise_in=0.0,
        speed_mph=None,
        rotation_rpm=None,
        sample_count=0,
        measurement_status=MeasurementStatus.UNAVAILABLE,
    )

    assert pitch.measurement_status == "UNAVAILABLE"
    assert measurement_is_usable(pitch) is False


def test_pitch_summary_reader_reconstructs_canonical_measurement_status() -> None:
    payload = {
        "pitch_id": "pitch-1",
        "t_start_ns": 1,
        "t_end_ns": 2,
        "is_strike": False,
        "zone_row": None,
        "zone_col": None,
        "run_in": 0.0,
        "rise_in": 0.0,
        "speed_mph": None,
        "rotation_rpm": None,
        "sample_count": 1,
        "measurement_status": "VALIDATED",
    }

    pitch = pitch_summary_from_dict(payload)

    assert pitch.measurement_status is MeasurementStatus.VALIDATED
    assert measurement_is_usable(pitch) is True
