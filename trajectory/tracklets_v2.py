"""Causal, covariance-aware candidate tracking for experimental stereo."""

from dataclasses import replace
import numpy as np
from scipy.optimize import linear_sum_assignment

from trajectory.tracklets import Tracklet, TrackletDecision, TrackletBuilder


class PredictiveTrackletBuilder(TrackletBuilder):
    def __init__(self, *, max_speed_px_s=5000.0, max_gap_frames=2, max_time_gap_ns=250_000_000):
        self.max_speed_px_s = float(max_speed_px_s)
        self.max_gap_frames = int(max_gap_frames)
        self.max_time_gap_ns = int(max_time_gap_ns)
        self._active: dict[str, list[Tracklet]] = {}
        self._next_id = 0

    def active(self, camera_id):
        return tuple(self._active.get(camera_id, ()))

    def update_with_decisions(self, camera_id, detections):
        values = sorted(detections, key=lambda d: (d.u, d.v, d.candidate_id))
        tracks = self._active.setdefault(camera_id, [])
        predictions = {}
        costs = np.full((len(tracks), len(values) + len(tracks)), 10.0, dtype=float)
        for row, track in enumerate(tracks):
            for col, candidate in enumerate(values):
                dt = (candidate.t_capture_monotonic_ns - track.last.t_capture_monotonic_ns) / 1e9
                if dt <= 0 or dt * 1e9 > self.max_time_gap_ns:
                    continue
                previous = np.array([track.last.u, track.last.v])
                velocity: np.ndarray = np.zeros(2)
                if len(track.detections) >= 2:
                    before = track.detections[-2]
                    interval = (track.last.t_capture_monotonic_ns - before.t_capture_monotonic_ns) / 1e9
                    if interval > 0:
                        velocity = (previous - [before.u, before.v]) / interval
                predicted = previous + velocity * dt
                covariance = np.array(track.last.pixel_covariance_px2 or ((0.25, 0.0), (0.0, 0.25)))
                covariance = covariance + np.eye(2) * max(1.0, (0.1 * self.max_speed_px_s * dt) ** 2)
                innovation = np.array([candidate.u, candidate.v]) - predicted
                total = covariance + np.array(candidate.pixel_covariance_px2 or ((0.25, 0.0), (0.0, 0.25)))
                cost = float(innovation @ np.linalg.solve(total, innovation))
                speed = float(np.linalg.norm(np.array([candidate.u, candidate.v]) - previous) / dt)
                if cost <= 9 and speed <= self.max_speed_px_s:
                    costs[row, col] = cost
                    predictions[row, col] = (predicted, covariance)
        assigned = set()
        decisions = []
        enriched = list(values)
        selected_rows = set()
        if tracks:
            rows, cols = linear_sum_assignment(costs)
            for row, col in zip(rows, cols):
                if col >= len(values) or costs[row, col] > 9:
                    continue
                predicted, covariance = predictions[row, col]
                candidate = replace(
                    values[col],
                    prediction_center_px=tuple(map(float, predicted)),
                    prediction_covariance_px2=tuple(tuple(map(float, r)) for r in covariance),
                )
                tracks[row].detections.append(candidate)
                tracks[row].missed_frames = 0
                enriched[col] = candidate
                assigned.add(col)
                selected_rows.add(row)
                decisions.append(TrackletDecision(candidate.candidate_id, tracks[row].tracklet_id, "CONTINUE"))
        for row, track in enumerate(tracks):
            if row not in selected_rows:
                track.missed_frames += 1
        tracks[:] = [t for t in tracks if t.missed_frames <= self.max_gap_frames]
        for col, candidate in enumerate(enriched):
            if col in assigned:
                continue
            self._next_id += 1
            track = Tracklet(f"{camera_id}-v2-{self._next_id}", camera_id, [candidate])
            tracks.append(track)
            decisions.append(TrackletDecision(candidate.candidate_id, track.tracklet_id, "START"))
        return list(tracks), tuple(decisions)
