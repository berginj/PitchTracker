"""Measured sample spread keeps bias, provenance and denominators explicit."""

from copy import deepcopy
import pytest

from calib.physical_validation import evaluate_physical_validation
from calib.residual_spread import residual_spread
from tests.test_physical_validation_v2 import _case, _dataset, _protocol


def test_sample_variance_and_xy_covariance_use_n_minus_one():
    result = residual_spread([-1, 1], [(1, 2), (3, 6)])
    assert result["speed_error_variance_mph2"] == 2
    assert result["speed_error_std_mph"] == pytest.approx(2 ** 0.5)
    assert result["plate_error_covariance_ft2"] == [[2, 4], [4, 8]]
    assert result["includes_reference_error"] and not result["physical_prediction_uncertainty"]


@pytest.mark.parametrize("count", [0, 1])
def test_insufficient_spread_is_unavailable_instead_of_zero(count):
    result = residual_spread([0] * count, [(0, 0)] * count)
    assert result["speed_error_variance_mph2"] is None
    assert result["speed_error_std_mph"] is None
    assert result["plate_error_covariance_ft2"] is None


def test_rejected_invalid_and_assisted_results_cannot_establish_variance():
    protocol = _protocol()
    cases = [
        _case(case_id="one", measured_speed_mph=89),
        _case(case_id="two", measured_speed_mph=91),
        _case(case_id="rejected", system_outcome="REJECTED", measured_speed_mph=None, measured_plate_xy_ft=None),
        _case(case_id="invalid", reference_status="INVALID", measured_speed_mph=100),
        _case(case_id="radar", measured_speed_source="radar", measured_speed_mph=100),
        _case(case_id="other-plane", reference_speed_reference_z_ft=10, measured_speed_mph=100),
    ]
    dataset = _dataset(protocol, phase="shadow", cases=cases)
    before = deepcopy(dataset.to_payload())
    report = evaluate_physical_validation(protocol, dataset)
    spread = report["metrics"]["residual_spread"]
    assert spread["speed_sample_count"] == 2 and spread["speed_error_variance_mph2"] == 2
    assert report["metrics"]["rejected_count"] == 1
    assert report["metrics"]["reference_invalid_count"] == 1
    assert not report["accuracy_claim_eligible"]
    assert dataset.to_payload() == before


def test_stratum_spread_does_not_pool_different_conditions():
    protocol = _protocol()
    cases = [
        _case(case_id="one", stratum="nominal", measured_speed_mph=89),
        _case(case_id="two", stratum="nominal", measured_speed_mph=91),
        _case(case_id="three", stratum="lighting", measured_speed_mph=92),
        _case(case_id="four", stratum="lighting", measured_speed_mph=92),
    ]
    report = evaluate_physical_validation(protocol, _dataset(protocol, phase="shadow", cases=cases))
    strata = report["metrics"]["residual_spread_by_stratum"]
    assert strata["nominal"]["speed_error_variance_mph2"] == 2
    assert strata["lighting"]["speed_error_variance_mph2"] == 0
    assert strata["middle"]["speed_error_variance_mph2"] is None
