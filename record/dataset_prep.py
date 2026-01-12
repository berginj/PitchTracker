"""Extract frames and metadata for ball detector training."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, Optional

import cv2


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare a YOLO dataset from a video.")
    parser.add_argument("--video", type=Path, required=True, help="Input video path.")
    parser.add_argument("--timestamps", type=Path, required=True, help="CSV with frame timestamps.")
    parser.add_argument("--out-dir", type=Path, required=True, help="Output dataset directory.")
    parser.add_argument("--fps", type=float, default=10.0, help="Target extraction FPS.")
    parser.add_argument("--prefix", default="left", help="Filename prefix.")
    return parser.parse_args()


def load_timestamps(path: Path) -> Dict[int, int]:
    if not path.exists():
        return {}
    mapping: Dict[int, int] = {}
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        for row in reader:
            try:
                frame_index = int(row["frame_index"])
                timestamp = int(row["t_capture_monotonic_ns"])
                mapping[frame_index] = timestamp
            except (KeyError, ValueError):
                continue
    return mapping


def write_dataset_yaml(path: Path, images_dir: Path) -> None:
    content = "\n".join(
        [
            f"path: {path.parent.as_posix()}",
            f"train: {images_dir.name}",
            f"val: {images_dir.name}",
            "names:",
            "  0: ball",
            "",
        ]
    )
    path.write_text(content)


def main() -> None:
    args = parse_args()
    args.out_dir.mkdir(parents=True, exist_ok=True)
    images_dir = args.out_dir / "images"
    labels_dir = args.out_dir / "labels"
    images_dir.mkdir(exist_ok=True)
    labels_dir.mkdir(exist_ok=True)

    timestamps = load_timestamps(args.timestamps)

    capture = cv2.VideoCapture(str(args.video))
    if not capture.isOpened():
        raise RuntimeError(f"Failed to open video {args.video}")

    src_fps = capture.get(cv2.CAP_PROP_FPS)
    if not src_fps or src_fps <= 0:
        src_fps = 60.0
    stride = max(int(round(src_fps / max(args.fps, 0.1))), 1)

    metadata_path = args.out_dir / "metadata.csv"
    with metadata_path.open("w", newline="") as meta_handle:
        writer = csv.writer(meta_handle)
        writer.writerow(["filename", "frame_index", "t_capture_monotonic_ns"])

        frame_index = 0
        saved = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            frame_index += 1
            if frame_index % stride != 0:
                continue
            filename = f"{args.prefix}_{frame_index:06d}.jpg"
            out_path = images_dir / filename
            cv2.imwrite(str(out_path), frame)
            writer.writerow(
                [filename, frame_index, timestamps.get(frame_index, "")]
            )
            saved += 1

    capture.release()

    dataset_yaml = args.out_dir / "dataset.yaml"
    write_dataset_yaml(dataset_yaml, images_dir)

    print(f"Saved {saved} frames to {images_dir}")
    print(f"Metadata: {metadata_path}")
    print(f"Dataset yaml: {dataset_yaml}")


if __name__ == "__main__":
    main()
