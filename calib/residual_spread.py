"""Observed reference-residual spread; never physical prediction uncertainty."""

from statistics import covariance, stdev, variance
from collections.abc import Iterable
from contracts.physical_validation import PhysicalValidationCaseV2


def residual_spread(speed_errors, plate_vectors):
    """Use sample statistics (n - 1); fewer than two cases remain unavailable."""
    speed_variance = variance(speed_errors) if len(speed_errors) >= 2 else None
    plate_covariance = None
    if len(plate_vectors) >= 2:
        x, y = zip(*plate_vectors)
        xy = covariance(x, y)
        plate_covariance = [[variance(x), xy], [xy, variance(y)]]
    return {
        "basis": "observed_reference_residuals",
        "sample_variance_ddof": 1,
        "speed_sample_count": len(speed_errors),
        "speed_error_variance_mph2": speed_variance,
        "speed_error_std_mph": stdev(speed_errors) if speed_variance is not None else None,
        "plate_sample_count": len(plate_vectors),
        "plate_error_covariance_ft2": plate_covariance,
        "includes_reference_error": True,
        "physical_prediction_uncertainty": False,
    }


def case_residual_spread(cases: Iterable[PhysicalValidationCaseV2]):
    speed_errors, plate_vectors = [], []
    for case in cases:
        if case.reference_status != "VALID" or case.system_outcome != "ACCEPTED":
            continue
        if (
            case.measured_speed_source == "vision_fit" and case.speed_estimator == "vision_only"
            and case.measured_speed_reference_z_ft is not None and case.reference_speed_reference_z_ft is not None
            and abs(case.measured_speed_reference_z_ft - case.reference_speed_reference_z_ft) <= 1e-6
            and case.measured_speed_mph is not None and case.reference_speed_mph is not None
        ):
            speed_errors.append(case.measured_speed_mph - case.reference_speed_mph)
        measured, reference = case.measured_plate_xy_ft, case.reference_plate_xy_ft
        if measured is not None and reference is not None:
            plate_vectors.append((measured[0] - reference[0], measured[1] - reference[1]))
    result = residual_spread(speed_errors, plate_vectors)
    result["conditional_on"] = "accepted_reference_valid_cases"
    result["speed_basis"] = "vision_only_at_matched_reference_plane"
    return result
