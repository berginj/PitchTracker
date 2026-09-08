"""Independent geometry regressions from the September measurement review."""

from dataclasses import replace

import cv2
import numpy as np
import pytest

from contracts import Detection, StereoObservation
from metrics.strike_zone import build_strike_zone, is_strike
from stereo.calibrated_stereo import CalibratedStereoGeometry, CalibratedStereoMatcher, _fundamental_from_rt


@pytest.mark.parametrize("distortion", [[0.0, 0.0, 0.0, 0.0, 0.0], [-0.2, 0.03, 0.001, -0.002, 0.0]])
@pytest.mark.parametrize("asymmetric", [False, True])
def test_raw_distorted_pixels_reconstruct_independent_truth(distortion, asymmetric):
    left_k = np.array([[1200.0, 0.0, 640.0], [0.0, 1200.0, 360.0], [0.0, 0.0, 1.0]])
    right_k = left_k.copy()
    right_k[0, 0] += 100 if asymmetric else 0
    left_d = np.array(distortion)
    right_d = left_d * (0.6 if asymmetric else 1.0)
    rotation = cv2.Rodrigues(np.array([0.01, 0.03, -0.01]) if asymmetric else np.zeros(3))[0]
    translation = np.array([[-1.625 * 304.8], [0.0], [0.0]])
    geometry = CalibratedStereoGeometry(
        left_k,
        left_d,
        right_k,
        right_d,
        rotation,
        translation,
        _fundamental_from_rt(left_k, right_k, rotation, translation),
        (1280, 720),
        3.0,
        3.0,
        80.0,
    )
    matcher = CalibratedStereoMatcher(geometry)
    truth = np.array([15.0, 5.0, 50.0])
    left = cv2.projectPoints(truth * 304.8, np.zeros(3), np.zeros(3), left_k, left_d)[0].reshape(2)
    right = cv2.projectPoints(truth * 304.8, cv2.Rodrigues(rotation)[0], translation, right_k, right_d)[0].reshape(2)
    detections = [Detection(side, 0, 0, *uv, 10.0, 1.0) for side, uv in [("left", left), ("right", right)]]
    match = matcher.match(*detections)
    assert match is not None
    observed = matcher.triangulate(match)
    np.testing.assert_allclose([observed.X, observed.Y, observed.Z], truth, atol=2e-5)
    assert observed.left == tuple(left)
    assert observed.right == tuple(right)
    assert observed.covariance is not None
    assert np.linalg.eigvalsh(observed.covariance).min() >= -1e-10
    assert observed.covariance[0][0] > 0
    with pytest.raises(ValueError, match="raw detector"):
        matcher.match(replace(detections[0], pixel_coordinate_space="ideal"), detections[1])


def observation(t, z, x=0.0, y=2.5):
    return StereoObservation(round(t * 1e9), (0.0, 0.0), (0.0, 0.0), x, y, z, quality=1.0, confidence=1.0)


@pytest.mark.parametrize("fps", [30, 60, 120])
@pytest.mark.parametrize("mph", [30, 60, 90])
@pytest.mark.parametrize("phase", [0.15, 0.5, 0.85])
@pytest.mark.parametrize("radius", [1.45, 1.88])
def test_strike_is_independent_of_sampling_phase(fps, mph, phase, radius):
    zone = build_strike_zone(0.0, 17.0, 17.0, 66.0, 0.5, 0.27)
    step = mph * 22 / 15 / fps
    observations = [observation(i / fps, (phase - i) * step) for i in range(-2, 5)]
    result = is_strike(observations, zone, radius)
    assert result.is_strike
    assert result.available
    assert result.zone_col == 1
    assert not is_strike([replace(obs, X=2.0) for obs in observations], zone, radius).is_strike


def test_zone_translation_uses_feet_and_unobserved_crossing_is_unavailable():
    zone = build_strike_zone(12.0, 17.0, 17.0, 66.0, 0.5, 0.27)
    assert zone.polygon_xz[0][1] == 12.0
    assert is_strike([observation(0.0, 12.0)], zone, 1.45).is_strike
    before_plate = is_strike([observation(0.0, 15.0), observation(0.01, 14.0)], zone, 1.45)
    assert not before_plate.available
    assert before_plate.zone_row is None
    gap = is_strike([observation(0.0, 13.0), observation(0.2, 9.0)], zone, 1.45)
    assert not gap.available


def test_sphere_does_not_clip_a_corner_outside_its_radius():
    zone = build_strike_zone(0.0, 17.0, 17.0, 66.0, 0.5, 0.27)
    radius_ft = 1.45 / 12
    # Vertical and horizontal offsets individually fit the radius, but their
    # Euclidean distance from the volume exceeds it.
    obs = observation(0.0, 0.0, 17 / 24 + 0.8 * radius_ft, zone.y_top_ft + 0.8 * radius_ft)
    assert not is_strike([obs], zone, 1.45).is_strike
