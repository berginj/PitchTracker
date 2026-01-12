import os

import cv2
import pytest

from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode


def _build_detector() -> ClassicalDetector:
    filters = FilterConfig(
        min_area=10,
        max_area=None,
        min_circularity=0.05,
        max_circularity=None,
        min_velocity=0.0,
        max_velocity=None,
    )
    config = CvDetectorConfig(
        frame_diff_threshold=8.0,
        bg_diff_threshold=8.0,
        bg_alpha=0.1,
        edge_threshold=12.0,
        blob_threshold=8.0,
        runtime_budget_ms=10.0,
        crop_padding_px=0,
        min_consecutive=1,
        filters=filters,
    )
    return ClassicalDetector(config=config, mode=Mode.MODE_A)


def test_video_clip_detection_optional() -> None:
    clip_path = os.environ.get("PITCHTRACKER_TEST_VIDEO")
    if not clip_path or not os.path.exists(clip_path):
        pytest.skip("Set PITCHTRACKER_TEST_VIDEO to run clip-based detection test.")

    cap = cv2.VideoCapture(clip_path)
    assert cap.isOpened()
    detector = _build_detector()
    detected = 0
    frame_index = 0
    while frame_index < 60:
        ok, frame = cap.read()
        if not ok:
            break
        frame_index += 1
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        frame_obj = Frame(
            camera_id="clip",
            frame_index=frame_index,
            t_capture_monotonic_ns=frame_index,
            image=gray,
            width=gray.shape[1],
            height=gray.shape[0],
            pixfmt="GRAY8",
        )
        if detector.detect(frame_obj):
            detected += 1
    cap.release()

    assert detected > 0
