"""Timestamp-aware per-camera candidate tracklets."""

from __future__ import annotations

from dataclasses import dataclass, field
from math import hypot, isfinite
from typing import Iterable

from contracts import Detection


@dataclass
class Tracklet:
    tracklet_id: str
    camera_id: str
    detections: list[Detection] = field(default_factory=list)
    missed_frames: int = 0

    @property
    def last(self) -> Detection:
        return self.detections[-1]


@dataclass(frozen=True)
class TrackletDecision:
    candidate_id: str
    tracklet_id: str
    action: str


class TrackletBuilder:
    def __init__(
        self,
        *,
        max_speed_px_s: float,
        max_gap_frames: int = 2,
        max_time_gap_ns: int = 250_000_000,
    ) -> None:
        self.max_speed_px_s = float(max_speed_px_s)
        self.max_gap_frames = int(max_gap_frames)
        self.max_time_gap_ns = int(max_time_gap_ns)
        if not isfinite(self.max_speed_px_s) or self.max_speed_px_s <= 0:
            raise ValueError("max_speed_px_s must be finite and positive")
        if self.max_gap_frames < 0:
            raise ValueError("max_gap_frames must be non-negative")
        if self.max_time_gap_ns <= 0:
            raise ValueError("max_time_gap_ns must be positive")
        self._active: dict[str, list[Tracklet]] = {}
        self._next_id = 0

    def update(self, camera_id: str, detections: Iterable[Detection]) -> list[Tracklet]:
        tracks, _ = self.update_with_decisions(camera_id, detections)
        return tracks

    def update_with_decisions(
        self,
        camera_id: str,
        detections: Iterable[Detection],
    ) -> tuple[list[Tracklet], tuple[TrackletDecision, ...]]:
        candidates = sorted(list(detections), key=_detection_sort_key)
        tracks = self._active.setdefault(camera_id, [])
        unmatched = set(range(len(candidates)))
        decisions: list[TrackletDecision] = []
        for track in tracks:
            best_index = self._best_candidate(track, candidates, unmatched)
            if best_index is None:
                track.missed_frames += 1
            else:
                candidate = candidates[best_index]
                track.detections.append(candidate)
                track.missed_frames = 0
                unmatched.remove(best_index)
                decisions.append(TrackletDecision(_candidate_id(candidate), track.tracklet_id, "CONTINUE"))
        tracks[:] = [track for track in tracks if track.missed_frames <= self.max_gap_frames]
        for index in sorted(unmatched):
            self._next_id += 1
            candidate = candidates[index]
            tracklet_id = f"{camera_id}-{self._next_id}"
            tracks.append(Tracklet(tracklet_id, camera_id, [candidate]))
            decisions.append(TrackletDecision(_candidate_id(candidate), tracklet_id, "START"))
        return list(tracks), tuple(decisions)

    def active(self, camera_id: str) -> tuple[Tracklet, ...]:
        return tuple(self._active.get(camera_id, ()))

    def _best_candidate(self, track: Tracklet, candidates: list[Detection], available: set[int]) -> int | None:
        best: tuple[float, int] | None = None
        for index in sorted(available):
            candidate = candidates[index]
            dt_ns = candidate.t_capture_monotonic_ns - track.last.t_capture_monotonic_ns
            if dt_ns <= 0 or dt_ns > self.max_time_gap_ns:
                continue
            dt_s = dt_ns / 1e9
            speed = hypot(candidate.u - track.last.u, candidate.v - track.last.v) / dt_s
            radius_change = abs(candidate.radius_px - track.last.radius_px) / max(track.last.radius_px, 1e-6)
            if speed > self.max_speed_px_s or radius_change > 0.75:
                continue
            score = speed / max(self.max_speed_px_s, 1e-6) + radius_change
            if best is None or score < best[0]:
                best = (score, index)
        return None if best is None else best[1]


def _detection_sort_key(detection: Detection) -> tuple:
    """Canonicalize detector output before assigning stable track IDs."""
    return (
        int(detection.t_capture_monotonic_ns),
        int(detection.frame_index),
        float(detection.u),
        float(detection.v),
        float(detection.radius_px),
        -float(detection.confidence),
        str(detection.camera_id),
    )


def _candidate_id(detection: Detection) -> str:
    if detection.candidate_id:
        return detection.candidate_id
    return "legacy:" + ":".join(str(value) for value in _detection_sort_key(detection))


__all__ = ["Tracklet", "TrackletBuilder", "TrackletDecision"]
