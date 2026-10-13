"""The same candidate identity, tracklet and eligibility step in live and replay."""

from dataclasses import replace
from app.pipeline.detection.decision_ids import canonicalize_detection_ids
from trajectory.tracklets import TrackletBuilder
from trajectory.tracklets_v2 import PredictiveTrackletBuilder


class CandidateProcessor:
    def __init__(self, config, *, builder=None):
        self.config = config
        builder_type = PredictiveTrackletBuilder if config.stereo.association_mode == "global_v3" else TrackletBuilder
        self.builder = builder or builder_type(
            max_speed_px_s=config.detector.filters.max_velocity or 5000.0, max_gap_frames=2
        )
        self._epochs = {}

    def enrich(self, frame, detections):
        camera = frame.camera_id
        epoch = self._epochs.get(camera)
        if epoch is not None and epoch != frame.capture_epoch:
            # Drop all owned state on an acquisition epoch boundary.
            builder_type = type(self.builder)
            self.builder = builder_type(
                max_speed_px_s=self.config.detector.filters.max_velocity or 5000.0, max_gap_frames=2
            )
            self._epochs.clear()
        self._epochs[camera] = frame.capture_epoch
        detections = canonicalize_detection_ids(frame, detections)
        tracks, decisions = self.builder.update_with_decisions(camera, detections)
        lengths = {track.tracklet_id: len(track.detections) for track in tracks}
        by_id = {decision.candidate_id: decision for decision in decisions}
        latest = {d.candidate_id: d for track in tracks for d in track.detections[-1:]}
        results = []
        for detection in detections:
            decision = by_id.get(detection.candidate_id)
            track_id = decision.tracklet_id if decision else None
            eligible = bool(track_id and lengths[track_id] >= self.config.detector.min_consecutive)
            results.append(
                replace(
                    latest.get(detection.candidate_id, detection),
                    tracklet_id=track_id,
                    tracklet_action=decision.action if decision else None,
                    association_eligible=eligible,
                    rejection_reasons=() if eligible else ("TRACKLET_RAMP_UP",),
                )
            )
        return results
