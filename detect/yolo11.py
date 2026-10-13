"""Explicit YOLO11 preprocessing and raw-pixel output decoding."""

from dataclasses import dataclass, replace
import cv2
import numpy as np

from contracts import Detection, Frame
from contracts.model_bundle import ModelBundle


@dataclass(frozen=True)
class LetterboxTransform:
    scale: float
    pad_x: int
    pad_y: int
    width: int
    height: int


def prepare(image: np.ndarray, size: tuple[int, int]):
    if image.dtype != np.uint8 or image.ndim not in (2, 3):
        raise ValueError("Detector requires uint8 grayscale or BGR frames")
    if image.ndim == 2:
        image = cv2.cvtColor(image, cv2.COLOR_GRAY2BGR)
    if image.shape[2] != 3:
        raise ValueError("Detector requires three color channels")
    height, width = image.shape[:2]
    scale = min(size[0] / width, size[1] / height)
    resized = cv2.resize(image, (round(width * scale), round(height * scale)))
    x = (size[0] - resized.shape[1]) // 2
    y = (size[1] - resized.shape[0]) // 2
    canvas = np.full((size[1], size[0], 3), 114, np.uint8)
    canvas[y : y + resized.shape[0], x : x + resized.shape[1]] = resized
    blob = cv2.dnn.blobFromImage(canvas, 1 / 255.0, size, swapRB=True, crop=False)
    return blob, LetterboxTransform(scale, x, y, width, height)


def decode(outputs, frame: Frame, transform: LetterboxTransform, bundle: ModelBundle) -> list[Detection]:
    output = np.asarray(outputs[0] if isinstance(outputs, (list, tuple)) else outputs)
    if output.ndim == 3 and output.shape[0] == 1:
        output = output[0]
    if bundle.output_layout == "channels_first":
        output = output.T
    if output.ndim != 2 or output.shape[1] != 4 + len(bundle.class_names) or output.shape[0] > 100_000:
        raise ValueError("YOLO11 output layout does not match declared classes")
    if not np.isfinite(output).all():
        raise ValueError("Nonfinite detector output")
    boxes, scores, centers = [], [], []
    for row in output:
        probabilities = row[4:]
        if np.any(probabilities < 0) or np.any(probabilities > 1):
            raise ValueError("Invalid detector scores")
        label = int(np.argmax(probabilities))
        score = float(probabilities[label])
        if label != bundle.ball_class_id or score < bundle.confidence_threshold:
            continue
        cx, cy, w, h = map(float, row[:4])
        if w <= 0 or h <= 0:
            continue
        cx, cy = (cx - transform.pad_x) / transform.scale, (cy - transform.pad_y) / transform.scale
        w, h = w / transform.scale, h / transform.scale
        if not 0 <= cx < frame.width or not 0 <= cy < frame.height:
            continue
        box = (
            max(0.0, cx - w / 2),
            max(0.0, cy - h / 2),
            min(float(frame.width), cx + w / 2),
            min(float(frame.height), cy + h / 2),
        )
        boxes.append([box[0], box[1], box[2] - box[0], box[3] - box[1]])
        scores.append(score)
        centers.append((cx, cy, w, h, box))
    if not boxes:
        return []
    indices = np.asarray(cv2.dnn.NMSBoxes(boxes, scores, bundle.confidence_threshold, bundle.nms_threshold)).ravel()
    ordered = sorted((int(i) for i in indices), key=lambda i: (-scores[i], centers[i][0], centers[i][1]))
    results = []
    for i in ordered[: bundle.max_candidates]:
        x, y, w, h, box = centers[i]
        result = Detection(
            frame.camera_id,
            frame.frame_index,
            frame.t_capture_monotonic_ns,
            x,
            y,
            max(w, h) / 2,
            scores[i],
            bbox_xyxy=box,
            localization_method="yolo11_box",
            radius_basis="bbox",
            pixel_covariance_px2=bundle.box_covariance_px2,
        )
        if bundle.localization == "refined":
            result = refine(frame.image, result, bundle.refined_covariance_px2)
        results.append(result)
    return results


def refine(image, detection: Detection, covariance=None) -> Detection:
    """Refine only a compact, unambiguous component near the proposal center."""
    box = detection.bbox_xyxy
    if box is None:
        return detection
    x1, y1 = max(0, int(box[0]) - 2), max(0, int(box[1]) - 2)
    x2, y2 = min(image.shape[1], int(np.ceil(box[2])) + 2), min(image.shape[0], int(np.ceil(box[3])) + 2)
    crop = image[y1:y2, x1:x2]
    fallback = replace(detection, localization_method="yolo11_box_refinement_failed")
    if crop.size < 9:
        return fallback
    gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if crop.ndim == 3 else crop
    if float(gray.max()) - float(gray.min()) < 15:
        return fallback
    _, mask = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    count, _, stats, centers = cv2.connectedComponentsWithStats(mask)
    candidates = []
    for i in range(1, count):
        area = float(stats[i, cv2.CC_STAT_AREA])
        cx, cy = centers[i] + [x1, y1]
        distance = float(np.hypot(cx - detection.u, cy - detection.v))
        if 3 <= area <= crop.shape[0] * crop.shape[1] * 0.75 and distance <= max(2.0, detection.radius_px * 0.5):
            candidates.append((distance, area, float(cx), float(cy)))
    candidates.sort()
    if not candidates or (len(candidates) > 1 and candidates[1][0] - candidates[0][0] < 1):
        return fallback
    _, area, cx, cy = candidates[0]
    return replace(
        detection,
        u=cx,
        v=cy,
        radius_px=float(np.sqrt(area / np.pi)),
        localization_method="yolo11_refined",
        radius_basis="component_area",
        pixel_covariance_px2=covariance,
    )
