"""Durable evidence records linking detections, stereo matches, observations, and verdicts."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = "evidence.v1"
STATUS_ACCEPTED = "ACCEPTED"
STATUS_REJECTED = "REJECTED"
STATUS_WARN = "WARN"
STATUS_PASS = "PASS"

Vec2 = Tuple[float, float]
Vec3 = Tuple[float, float, float]
Cov3 = Tuple[Tuple[float, float, float], Tuple[float, float, float], Tuple[float, float, float]]


@dataclass(frozen=True)
class Candidate2DEvidence:
    candidate_id: str
    camera_id: str
    frame_index: int
    t_capture_monotonic_ns: int
    center_px: Vec2
    radius_px: float
    confidence: float
    detector: str
    status: str = STATUS_ACCEPTED
    rejection_reasons: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_payload(self) -> Dict[str, Any]:
        return _payload(self, center_px=list(self.center_px))

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "Candidate2DEvidence":
        return cls(
            candidate_id=str(payload["candidate_id"]),
            camera_id=str(payload["camera_id"]),
            frame_index=int(payload["frame_index"]),
            t_capture_monotonic_ns=int(payload["t_capture_monotonic_ns"]),
            center_px=_vec2(payload["center_px"]),
            radius_px=float(payload["radius_px"]),
            confidence=float(payload["confidence"]),
            detector=str(payload["detector"]),
            status=str(payload.get("status", STATUS_ACCEPTED)),
            rejection_reasons=list(payload.get("rejection_reasons") or []),
            diagnostics=dict(payload.get("diagnostics") or {}),
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
        )


@dataclass(frozen=True)
class StereoMatchEvidence:
    match_id: str
    left_candidate_id: str
    right_candidate_id: str
    t_ns: int
    left_px: Vec2
    right_px: Vec2
    epipolar_error_px: Optional[float]
    score: float
    status: str = STATUS_ACCEPTED
    rejection_reasons: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_payload(self) -> Dict[str, Any]:
        return _payload(self, left_px=list(self.left_px), right_px=list(self.right_px))

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "StereoMatchEvidence":
        epipolar_error = payload.get("epipolar_error_px")
        return cls(
            match_id=str(payload["match_id"]),
            left_candidate_id=str(payload["left_candidate_id"]),
            right_candidate_id=str(payload["right_candidate_id"]),
            t_ns=int(payload["t_ns"]),
            left_px=_vec2(payload["left_px"]),
            right_px=_vec2(payload["right_px"]),
            epipolar_error_px=None if epipolar_error is None else float(epipolar_error),
            score=float(payload["score"]),
            status=str(payload.get("status", STATUS_ACCEPTED)),
            rejection_reasons=list(payload.get("rejection_reasons") or []),
            diagnostics=dict(payload.get("diagnostics") or {}),
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
        )


@dataclass(frozen=True)
class Observation3DEvidence:
    observation_id: str
    match_id: str
    t_ns: int
    xyz_ft: Vec3
    quality: float
    confidence: float
    covariance: Optional[Cov3] = None
    depth_sigma_ft: Optional[float] = None
    status: str = STATUS_ACCEPTED
    rejection_reasons: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_payload(self) -> Dict[str, Any]:
        covariance = None
        if self.covariance is not None:
            covariance = [list(row) for row in self.covariance]
        return _payload(self, xyz_ft=list(self.xyz_ft), covariance=covariance)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "Observation3DEvidence":
        depth_sigma = payload.get("depth_sigma_ft")
        return cls(
            observation_id=str(payload["observation_id"]),
            match_id=str(payload["match_id"]),
            t_ns=int(payload["t_ns"]),
            xyz_ft=_vec3(payload["xyz_ft"]),
            quality=float(payload["quality"]),
            confidence=float(payload["confidence"]),
            covariance=_cov3(payload.get("covariance")),
            depth_sigma_ft=None if depth_sigma is None else float(depth_sigma),
            status=str(payload.get("status", STATUS_ACCEPTED)),
            rejection_reasons=list(payload.get("rejection_reasons") or []),
            diagnostics=dict(payload.get("diagnostics") or {}),
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
        )


@dataclass(frozen=True)
class PitchVerdictEvidence:
    pitch_id: str
    status: str
    observation_ids: List[str] = field(default_factory=list)
    model_name: Optional[str] = None
    plate_crossing_xyz_ft: Optional[Vec3] = None
    confidence: Optional[float] = None
    expected_error_ft: Optional[float] = None
    rejection_reasons: List[str] = field(default_factory=list)
    warning_reasons: List[str] = field(default_factory=list)
    diagnostics: Dict[str, Any] = field(default_factory=dict)
    schema_version: str = SCHEMA_VERSION

    def to_payload(self) -> Dict[str, Any]:
        crossing = None
        if self.plate_crossing_xyz_ft is not None:
            crossing = list(self.plate_crossing_xyz_ft)
        return _payload(self, plate_crossing_xyz_ft=crossing)

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "PitchVerdictEvidence":
        confidence = payload.get("confidence")
        expected_error = payload.get("expected_error_ft")
        crossing = payload.get("plate_crossing_xyz_ft")
        return cls(
            pitch_id=str(payload["pitch_id"]),
            status=str(payload["status"]),
            observation_ids=list(payload.get("observation_ids") or []),
            model_name=None if payload.get("model_name") is None else str(payload.get("model_name")),
            plate_crossing_xyz_ft=None if crossing is None else _vec3(crossing),
            confidence=None if confidence is None else float(confidence),
            expected_error_ft=None if expected_error is None else float(expected_error),
            rejection_reasons=list(payload.get("rejection_reasons") or []),
            warning_reasons=list(payload.get("warning_reasons") or []),
            diagnostics=dict(payload.get("diagnostics") or {}),
            schema_version=str(payload.get("schema_version", SCHEMA_VERSION)),
        )


def _payload(instance: Any, **overrides: Any) -> Dict[str, Any]:
    payload = dict(instance.__dict__)
    payload.update(overrides)
    payload["rejection_reasons"] = list(payload.get("rejection_reasons") or [])
    if "warning_reasons" in payload:
        payload["warning_reasons"] = list(payload.get("warning_reasons") or [])
    payload["diagnostics"] = dict(payload.get("diagnostics") or {})
    return payload


def _vec2(value: Any) -> Vec2:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError("Expected a two-number vector.")
    return (float(value[0]), float(value[1]))


def _vec3(value: Any) -> Vec3:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Expected a three-number vector.")
    return (float(value[0]), float(value[1]), float(value[2]))


def _cov3(value: Any) -> Optional[Cov3]:
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        raise ValueError("Expected a 3x3 covariance matrix.")
    return (_vec3(value[0]), _vec3(value[1]), _vec3(value[2]))
