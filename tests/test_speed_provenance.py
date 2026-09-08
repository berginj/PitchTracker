"""Preserve the independent vision measurement and its observation location."""

from dataclasses import asdict
from pathlib import Path

import pytest

from app.contracts import pitch_summary_from_dict
from app.pipeline.analysis.pitch_summary import PitchAnalyzer, _result_is_usable
from app.pipeline.recording.manifest import create_pitch_manifest
from configs.settings import load_config
from contracts import StereoObservation, TrackSample
from contracts.measurements import SpeedMeasurement, independent_vision_speed
from trajectory.contracts import FailureCode, TrajectoryDiagnostics, TrajectoryFitResult


def test_override_keeps_separate_vision_result_and_location(monkeypatch):
    config = load_config(Path("configs/default.yaml"))
    analyzer = PitchAnalyzer(config, lambda: 1.45, lambda: 75.0, lambda: "manual_override")
    observations = [
        StereoObservation(i * 20_000_000, (0.0, 0.0), (0.0, 0.0), 0.0, 2.5, 8.0 - i * 1.76, 1.0, confidence=1.0)
        for i in range(8)
    ]
    samples = [TrackSample(obs.t_ns, obs.X, obs.Y, obs.Z, 0.0, 0.0, -88.0) for obs in observations]
    fitted = TrajectoryFitResult(
        "physics_drag", samples, (0.0, 2.5, 0.0), 90_000_000, None, 0.9, TrajectoryDiagnostics()
    )
    requests = []

    def fit(mode, request):
        requests.append(request)
        return fitted

    monkeypatch.setattr(analyzer, "_run_mode", fit)
    summary = analyzer.analyze_pitch("pitch", 0, observations[-1].t_ns, observations)
    assert requests[0].radar_speed_mph is None
    assert summary.speed_mph == 75.0
    assert summary.vision_speed is not None
    assert summary.vision_speed.speed_mph == pytest.approx(60.0, abs=0.001)
    assert summary.vision_speed.reference == "first_observed_point"
    assert summary.vision_speed.reference_z_ft == 8.0
    assert summary.external_speed is not None and summary.external_speed.reference == "unspecified"
    assert pitch_summary_from_dict(asdict(summary)).vision_speed == summary.vision_speed
    manifest = create_pitch_manifest(summary, None)
    assert manifest["vision_speed"]["reference_z_ft"] == 8.0
    assert independent_vision_speed(summary.vision_speed, 8.0) == summary.vision_speed.speed_mph
    with pytest.raises(ValueError, match="locations"):
        independent_vision_speed(summary.vision_speed, config.metrics.release_plane_z_ft)
    with pytest.raises(ValueError, match="independent"):
        independent_vision_speed(summary.external_speed, 8.0)


@pytest.mark.parametrize("code", list(FailureCode))
def test_failure_codes_cannot_be_overridden_by_positive_fit_score(code):
    result = TrajectoryFitResult(
        "test", [], (0.0, 2.5, 0.0), 0, None, 0.99, TrajectoryDiagnostics(failure_codes=[code])
    )
    assert not _result_is_usable(result)


def test_assisted_measurement_is_not_independent_vision():
    measurement = SpeedMeasurement(60.0, "vision_fit", "first_observed_point", 8.0, 0, "radar_assisted")
    with pytest.raises(ValueError, match="independent"):
        independent_vision_speed(measurement, 8.0)
