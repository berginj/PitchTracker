"""Shadow candidate/stereo processing, using public pipeline boundaries."""

from dataclasses import replace
from pathlib import Path

from app.pipeline.detection.candidate_processing import CandidateProcessor
from app.pipeline.detection.processor import DetectionProcessor
from app.pipeline.initialization import PipelineInitializer


class ShadowStereoPipeline:
    def __init__(self, config, variant, calibration_path, roi_path, left_id, right_id):
        if calibration_path is None or roi_path is None:
            raise ValueError("Timing trials require the actual rig calibration and ROI artifacts")
        self.config = replace(config, stereo=replace(config.stereo, association_mode=variant.split(":")[1]))
        initializer = PipelineInitializer()
        _, lane, stereo, plate, plate_stereo = initializer.load_rois(left_id, right_id, Path(roi_path), Path(roi_path))
        matcher = initializer.create_stereo_matcher(self.config, Path(calibration_path))
        self.candidates = CandidateProcessor(self.config)
        self.processor = DetectionProcessor(
            self.config, matcher, lane, plate, stereo, plate_stereo, lambda: config.ball.radius_in[config.ball.type]
        )
        self.labels = {left_id: "left", right_id: "right"}

    def process(self, frame, detections):
        values = self.candidates.enrich(frame, detections)
        self.processor.process_detection_result(
            self.labels[frame.camera_id], frame, [d for d in values if d.association_eligible]
        )

    def close(self):
        self.processor.flush_pairing_buffers("TRIAL_STOP")
