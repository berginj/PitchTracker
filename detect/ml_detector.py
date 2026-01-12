"""ML detector using OpenCV DNN with YOLO-style outputs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import cv2
import numpy as np

from contracts import Detection, Frame
from detect.detector import Detector, DetectorHealth


@dataclass(frozen=True)
class MlDetector(Detector):
    model_path: Optional[str] = None
    input_size: Tuple[int, int] = (640, 640)
    conf_threshold: float = 0.25
    class_id: int = 0
    output_format: str = "yolo_v5"

    def detect(self, frame: Frame) -> List[Detection]:
        if self.model_path is None:
            return []
        net = cv2.dnn.readNetFromONNX(self.model_path)
        blob = cv2.dnn.blobFromImage(
            frame.image,
            scalefactor=1 / 255.0,
            size=self.input_size,
            swapRB=False,
            crop=False,
        )
        net.setInput(blob)
        outputs = net.forward()
        return _parse_outputs(
            outputs=outputs,
            frame=frame,
            conf_threshold=self.conf_threshold,
            class_id=self.class_id,
            output_format=self.output_format,
        )

    def health(self) -> DetectorHealth:
        return DetectorHealth(false_positive_rate_hz=0.0, last_detection_ns=0)


def _parse_outputs(
    outputs: np.ndarray,
    frame: Frame,
    conf_threshold: float,
    class_id: int,
    output_format: str,
) -> List[Detection]:
    detections: List[Detection] = []
    output = outputs
    if isinstance(outputs, (list, tuple)):
        output = outputs[0]
    if output.ndim == 3:
        output = output[0]
    height = frame.height
    width = frame.width
    for row in output:
        if output_format == "yolo_v5":
            obj_conf = float(row[4])
            if obj_conf < conf_threshold:
                continue
            scores = row[5:]
            best_class = int(np.argmax(scores))
            class_conf = float(scores[best_class])
            conf = obj_conf * class_conf
        else:
            scores = row[4:]
            best_class = int(np.argmax(scores))
            conf = float(scores[best_class])
        if best_class != class_id or conf < conf_threshold:
            continue
        cx, cy, w, h = row[0:4]
        x = cx * width
        y = cy * height
        radius = max(w, h) * max(width, height) / 2.0
        detections.append(
            Detection(
                camera_id=frame.camera_id,
                frame_index=frame.frame_index,
                t_capture_monotonic_ns=frame.t_capture_monotonic_ns,
                u=float(x),
                v=float(y),
                radius_px=float(radius),
                confidence=conf,
            )
        )
    return detections
