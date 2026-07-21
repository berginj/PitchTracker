"""Stable identifiers for replayable detection decisions."""

from __future__ import annotations

import hashlib
from dataclasses import replace
from typing import Iterable

from contracts import Detection, Frame


def frame_decision_id(frame: Frame) -> str:
    """Return an ID stable across serialization and independent of object identity."""

    epoch = frame.capture_epoch or "default"
    return f"{frame.camera_id}:{epoch}:{int(frame.frame_index)}:{int(frame.t_capture_monotonic_ns)}"


def canonicalize_detection_ids(frame: Frame, detections: Iterable[Detection]) -> list[Detection]:
    """Attach content-derived candidate IDs while preserving detector return order."""

    values = list(detections)
    frame_id = frame_decision_id(frame)
    ranked = sorted(enumerate(values), key=lambda item: (_detection_key(item[1]), item[0]))
    ids: dict[int, str] = {}
    occurrences: dict[str, int] = {}
    for original_index, detection in ranked:
        digest = hashlib.sha256(repr(_detection_key(detection)).encode("utf-8")).hexdigest()[:12]
        occurrence = occurrences.get(digest, 0)
        occurrences[digest] = occurrence + 1
        ids[original_index] = f"{frame_id}:candidate:{digest}:{occurrence}"
    return [
        replace(detection, candidate_id=detection.candidate_id or ids[index])
        for index, detection in enumerate(values)
    ]


def stereo_pair_id(left: Frame, right: Frame) -> str:
    payload = f"{frame_decision_id(left)}|{frame_decision_id(right)}".encode("utf-8")
    return f"stereo:{hashlib.sha256(payload).hexdigest()[:20]}"


def association_edge_id(pair_id: str, left_candidate_id: str, right_candidate_id: str) -> str:
    payload = f"{pair_id}|{left_candidate_id}|{right_candidate_id}".encode("utf-8")
    return f"edge:{hashlib.sha256(payload).hexdigest()[:20]}"


def detection_decision_id(detection: Detection) -> str:
    if detection.candidate_id:
        return detection.candidate_id
    return (
        f"legacy:{detection.camera_id}:{detection.frame_index}:{detection.t_capture_monotonic_ns}:"
        f"{detection.u:.9g}:{detection.v:.9g}:{detection.radius_px:.9g}:{detection.confidence:.9g}"
    )


def observation_decision_id(edge_id: str) -> str:
    return f"observation:{hashlib.sha256(edge_id.encode('utf-8')).hexdigest()[:20]}"


def _detection_key(detection: Detection) -> tuple:
    return (
        str(detection.camera_id),
        int(detection.frame_index),
        int(detection.t_capture_monotonic_ns),
        float(detection.u),
        float(detection.v),
        float(detection.radius_px),
        float(detection.confidence),
    )


__all__ = [
    "association_edge_id",
    "canonicalize_detection_ids",
    "detection_decision_id",
    "frame_decision_id",
    "observation_decision_id",
    "stereo_pair_id",
]
