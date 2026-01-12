"""ML detector using OpenCV DNN with YOLO-style outputs."""

from __future__ import annotations

from typing import List, Optional, Tuple

import cv2
import numpy as np

from contracts import Detection, Frame
from detect.detector import Detector, DetectorHealth


class MlDetector(Detector):
    def __init__(
        self,
        model_path: Optional[str] = None,
        input_size: Tuple[int, int] = (640, 640),
        conf_threshold: float = 0.25,
        class_id: int = 0,
        output_format: str = "yolo_v5",
        nms_threshold: float = 0.45,
    ) -> None:
        self.model_path = model_path
        self.input_size = input_size
        self.conf_threshold = conf_threshold
        self.class_id = class_id
        self.output_format = output_format
        self.nms_threshold = nms_threshold
        self._net: Optional[cv2.dnn.Net] = None

    def _load_net(self) -> Optional[cv2.dnn.Net]:
        if self.model_path is None:
            return None
        if self._net is None:
            self._net = cv2.dnn.readNetFromONNX(self.model_path)
        return self._net

    def detect(self, frame: Frame) -> List[Detection]:
        net = self._load_net()
        if net is None:
            return []
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
            input_size=self.input_size,
            conf_threshold=self.conf_threshold,
            class_id=self.class_id,
            output_format=self.output_format,
            nms_threshold=self.nms_threshold,
        )

    def health(self) -> DetectorHealth:
        return DetectorHealth(false_positive_rate_hz=0.0, last_detection_ns=0)


def _parse_outputs(
    outputs: np.ndarray,
    frame: Frame,
    input_size: Tuple[int, int],
    conf_threshold: float,
    class_id: int,
    output_format: str,
    nms_threshold: float,
) -> List[Detection]:
    output = outputs
    if isinstance(outputs, (list, tuple)):
        output = outputs[0]
    if output.ndim == 3:
        output = output[0]
    height = frame.height
    width = frame.width
    input_w, input_h = input_size
    scale_x = width / float(input_w)
    scale_y = height / float(input_h)
    boxes: List[List[int]] = []
    confidences: List[float] = []
    centers: List[tuple[float, float, float, float]] = []
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
        if max(cx, cy, w, h) <= 1.5:
            cx *= input_w
            cy *= input_h
            w *= input_w
            h *= input_h
        x = cx * scale_x
        y = cy * scale_y
        w_px = w * scale_x
        h_px = h * scale_y
        x1 = int(x - w_px / 2)
        y1 = int(y - h_px / 2)
        boxes.append([x1, y1, int(w_px), int(h_px)])
        confidences.append(conf)
        centers.append((x, y, w_px, h_px))

    detections: List[Detection] = []
    if not boxes:
        return detections
    indices = cv2.dnn.NMSBoxes(boxes, confidences, conf_threshold, nms_threshold)
    if len(indices) == 0:
        return detections
    for idx in indices:
        i = int(idx) if not isinstance(idx, (list, tuple, np.ndarray)) else int(idx[0])
        x, y, w_px, h_px = centers[i]
        radius = max(w_px, h_px) / 2.0
        detections.append(
            Detection(
                camera_id=frame.camera_id,
                frame_index=frame.frame_index,
                t_capture_monotonic_ns=frame.t_capture_monotonic_ns,
                u=float(x),
                v=float(y),
                radius_px=float(radius),
                confidence=float(confidences[i]),
            )
        )
    return detections
