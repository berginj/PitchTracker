import numpy as np
import cv2

from contracts import Frame
from detect.classical_detector import ClassicalDetector
from detect.config import DetectorConfig as CvDetectorConfig, FilterConfig, Mode
from stereo.simple_stereo import SimpleStereoMatcher, StereoGeometry


def _make_frame(camera_id: str, index: int, image: np.ndarray) -> Frame:
    return Frame(
        camera_id=camera_id,
        frame_index=index,
        t_capture_monotonic_ns=index,
        image=image,
        width=image.shape[1],
        height=image.shape[0],
        pixfmt="GRAY8",
    )


def _detector() -> ClassicalDetector:
    filters = FilterConfig(
        min_area=10,
        max_area=None,
        min_circularity=0.05,
        max_circularity=None,
        min_velocity=0.0,
        max_velocity=None,
    )
    config = CvDetectorConfig(
        frame_diff_threshold=5.0,
        bg_diff_threshold=5.0,
        bg_alpha=0.1,
        edge_threshold=10.0,
        blob_threshold=5.0,
        runtime_budget_ms=10.0,
        crop_padding_px=0,
        min_consecutive=1,
        filters=filters,
    )
    return ClassicalDetector(config=config, mode=Mode.MODE_A)


def test_simulated_detection_and_triangulation() -> None:
    width, height = 320, 240
    detector = _detector()
    geometry = StereoGeometry(
        baseline_ft=1.0,
        focal_length_px=400.0,
        cx=width / 2.0,
        cy=height / 2.0,
        epipolar_epsilon_px=3.0,
        z_min_ft=3.0,
        z_max_ft=80.0,
    )
    stereo = SimpleStereoMatcher(geometry)

    detections = []
    for idx in range(6):
        left = np.zeros((height, width), dtype=np.uint8)
        right = np.zeros((height, width), dtype=np.uint8)
        cx = 60 + idx * 10
        cy = 120
        disparity = 8
        cv2.circle(left, (cx, cy), 6, 255, -1)
        cv2.circle(right, (cx - disparity, cy), 6, 255, -1)
        left_frame = _make_frame("left", idx, left)
        right_frame = _make_frame("right", idx, right)
        left_dets = detector.detect(left_frame)
        right_dets = detector.detect(right_frame)
        if left_dets and right_dets:
            match = stereo.match(left_dets[0], right_dets[0])
            assert match is not None
            obs = stereo.triangulate(match)
            detections.append(obs)

    assert detections
    assert all(geometry.z_min_ft <= obs.Z <= geometry.z_max_ft for obs in detections)
