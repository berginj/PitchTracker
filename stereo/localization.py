"""Conditional raw-pixel geometry checks; no exposure/calibration accuracy claim."""

import cv2
import numpy as np
from typing import Any
from contracts.model_bundle import covariance2


def geometry_diagnostics(geometry, match) -> dict[str, Any]:
    if match.left.pixel_covariance_px2 is None or match.right.pixel_covariance_px2 is None:
        return {"valid": False, "reason": "PIXEL_COVARIANCE_MISSING"}
    try:
        covariance2(match.left.pixel_covariance_px2)
        covariance2(match.right.pixel_covariance_px2)
    except (ValueError, TypeError):
        return {"valid": False, "reason": "PIXEL_COVARIANCE_INVALID"}
    pixels = np.array([match.left.u, match.left.v, match.right.u, match.right.v], dtype=float)
    covariance = np.zeros((4, 4))
    covariance[:2, :2] = match.left.pixel_covariance_px2
    covariance[2:, 2:] = match.right.pixel_covariance_px2

    def ideal(values):
        left = cv2.undistortPoints(
            values[:2].reshape(1, 1, 2), geometry.mtx_left, geometry.dist_left, P=geometry.mtx_left
        ).reshape(2)
        right = cv2.undistortPoints(
            values[2:].reshape(1, 1, 2), geometry.mtx_right, geometry.dist_right, P=geometry.mtx_right
        ).reshape(2)
        return np.r_[left, 1.0], np.r_[right, 1.0]

    def signed_error(values):
        left, right = ideal(values)
        line_r, line_l = geometry.F @ left, geometry.F.T @ right
        denominator = np.sqrt((np.dot(line_r[:2], line_r[:2]) + np.dot(line_l[:2], line_l[:2])) / 2)
        return float(right @ geometry.F @ left / max(denominator, 1e-15))

    gradient = np.empty(4)
    for axis in range(4):
        delta = np.eye(4)[axis] * 0.1
        gradient[axis] = (signed_error(pixels + delta) - signed_error(pixels - delta)) / 0.2
    variance = float(gradient @ covariance @ gradient)
    epipolar_sigma = np.sqrt(max(variance, 1e-12))
    epipolar_normalized = abs(signed_error(pixels)) / epipolar_sigma
    left, right = ideal(pixels)
    p_left = geometry.mtx_left @ np.c_[np.eye(3), np.zeros(3)]
    p_right = geometry.mtx_right @ np.c_[geometry.R, geometry.T]
    homogeneous = cv2.triangulatePoints(p_left, p_right, left[:2].reshape(2, 1), right[:2].reshape(2, 1))
    if abs(float(homogeneous[3, 0])) < 1e-15:
        return {"valid": False, "reason": "TRIANGULATION_SINGULAR"}
    xyz = (homogeneous[:3, 0] / homogeneous[3, 0]).reshape(3)
    right_xyz = geometry.R @ xyz + geometry.T.ravel()
    if xyz[2] <= 0 or right_xyz[2] <= 0 or not geometry.z_min_ft <= xyz[2] / 304.8 <= geometry.z_max_ft:
        return {"valid": False, "reason": "DEPTH_OR_CHEIRALITY_FAILED"}
    projected_left = cv2.projectPoints(
        xyz.reshape(1, 3), np.zeros(3), np.zeros(3), geometry.mtx_left, geometry.dist_left
    )[0].ravel()
    rotation = cv2.Rodrigues(geometry.R)[0]
    projected_right = cv2.projectPoints(
        xyz.reshape(1, 3), rotation, geometry.T, geometry.mtx_right, geometry.dist_right
    )[0].ravel()
    residual = pixels - np.r_[projected_left, projected_right]
    reprojection_q = float(residual @ np.linalg.solve(covariance, residual))
    valid = bool(epipolar_normalized <= 3 and reprojection_q <= 36)
    return {
        "valid": valid,
        "reason": None if valid else "LOCALIZATION_GATE_FAILED",
        "epipolar_sigma_px": float(epipolar_sigma),
        "epipolar_normalized": float(epipolar_normalized),
        "reprojection_q": reprojection_q,
        "reprojection_px": float(np.linalg.norm(residual)),
        "covariance_basis": "localization_only",
    }
