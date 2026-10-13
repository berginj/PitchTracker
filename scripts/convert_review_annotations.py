"""Bind Review's clicked pixels to verified encoded-frame timestamps."""

import argparse
import csv
import json
from pathlib import Path


def convert(session, annotations):
    frames = []
    points = json.loads(Path(annotations).read_text(encoding="utf-8"))["annotations"]
    for side in ("left", "right"):
        with (Path(session) / f"session_{side}_timestamps.csv").open(newline="", encoding="utf-8") as stream:
            rows = list(csv.DictReader(stream))
        mapping = {int(r["encoded_frame_index"]): r for r in rows if r.get("write_status") == "accepted"}
        for point in points:
            if point["camera"] != side:
                continue
            row = mapping.get(point["frame_index"])
            if row is None:
                raise ValueError("Review point has no explicit encoded-frame mapping")
            frames.append(
                {
                    "camera_id": row["camera_id"],
                    "frame_index": int(row["frame_index"]),
                    "timestamp_ns": int(row["t_capture_monotonic_ns"]),
                    "visibility": "visible",
                    "center_px": [point["x"], point["y"]],
                    "opportunity_id": None,
                }
            )
    return {
        "schema_version": "comparison_annotations.v1",
        "human_reviewed": False,
        "opportunities": [],
        "frames": frames,
        "monocular": {},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("session", "annotations", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new annotation draft")
    result = convert(args.session, args.annotations)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
