"""Independent truth records plate bias and comparable cropped-window speed."""

import pytest

from benchmarks.trajectory_model_envelope import EnvelopeScenario, evaluate_case, sweep_cases


def test_independent_control_reports_plate_and_speed_bias():
    result = evaluate_case(60.0, 0.3, 0.0, scenario=EnvelopeScenario(noise_sigma_ft=0.001))
    assert result["eligible"]
    assert abs(result["speed_error_mph_even_if_rejected"]) < 0.2
    assert result["plate_position_error_ft_even_if_rejected"] < 0.02
    assert len(result["plate_position_bias_ft_even_if_rejected"]) == 3
    assert result["truth_plate_xyz_ft"][2] == pytest.approx(0.0, abs=1e-10)


def test_cropped_window_compares_to_first_visible_truth_not_initial_speed():
    result = evaluate_case(60.0, 0.3, 0.0, scenario=EnvelopeScenario(visibility_start_s=0.08, noise_sigma_ft=0.001))
    assert result["truth_first_observed_speed_mph"] < result["input_speed_mph"]
    assert abs(result["speed_error_mph_even_if_rejected"]) < 0.2


def test_sweep_is_bounded_and_contains_deliberate_comparison_factors():
    cases = sweep_cases()
    assert len(cases) <= 32
    assert {scenario.noise_seed for _, _, _, scenario in cases} >= {7, 19, 43}
    assert {scenario.fps for _, _, _, scenario in cases} >= {30, 60, 120}
    assert any(scenario.drag_prior_enabled for _, _, _, scenario in cases)
    assert any(scenario.timing_jitter_s > 0 for _, _, _, scenario in cases)
    assert any(scenario.visibility_start_s > 0 for _, _, _, scenario in cases)
    assert len({scenario.truth_drag_ft_inverse for _, _, _, scenario in cases}) > 1
