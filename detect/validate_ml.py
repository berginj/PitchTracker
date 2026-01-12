"""Run a quick ML detector pass on a single image."""

from __future__ import annotations

import argparse
from pathlib import Path

import cv2

from contracts import Frame
from detect.ml_detector import MlDetector


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate ML detector on one image.")
    parser.add_argument("--model", type=Path, required=True, help="ONNX model path.")
    parser.add_argument("--image", type=Path, required=True, help="Image path.")
    parser.add_argument("--input-size", default="640x640", help="Model input size WxH.")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold.")
    parser.add_argument("--class-id", type=int, default=0, help="Class id to keep.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    width, height = [int(x) for x in args.input_size.lower().split("x")]
    image = cv2.imread(str(args.image), cv2.IMREAD_GRAYSCALE)
    if image is None:
        raise RuntimeError("Failed to read image.")
    frame = Frame(
        camera_id="test",
        frame_index=1,
        t_capture_monotonic_ns=0,
        image=image,
        width=image.shape[1],
        height=image.shape[0],
        pixfmt="GRAY8",
    )
    detector = MlDetector(
        model_path=str(args.model),
        input_size=(width, height),
        conf_threshold=args.conf,
        class_id=args.class_id,
    )
    detections = detector.detect(frame)
    print(f"Detections: {len(detections)}")
    for det in detections:
        print(f"u={det.u:.1f} v={det.v:.1f} r={det.radius_px:.1f} conf={det.confidence:.2f}")


if __name__ == "__main__":
    main()
