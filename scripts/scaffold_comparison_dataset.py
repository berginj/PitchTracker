"""Create a local collection manifest; no synthetic labels become human truth."""

import argparse
import json
from typing import Any
from pathlib import Path


def scaffold(output):
    output = Path(output).resolve()
    if output.exists():
        raise FileExistsError("Choose a new collection directory")
    output.mkdir(parents=True)
    sessions: list[dict[str, Any]] = []
    for ball in ("baseball", "softball"):
        for index in range(3):
            identity = f"{ball}_{index + 1}"
            annotation = {
                "schema_version": "comparison_annotations.v1",
                "human_reviewed": False,
                "opportunities": [],
                "frames": [],
                "monocular": {},
            }
            (output / f"{identity}_annotations.json").write_text(json.dumps(annotation, indent=2), encoding="utf-8")
            sessions.append(
                {
                    "id": identity,
                    "root": f"sessions/{identity}",
                    "ball_type": ball,
                    "split": "development" if index < 2 else "evaluation",
                    "config": f"artifacts/{identity}/config.yaml",
                    "calibration": f"artifacts/{identity}/stereo.npz",
                    "roi": f"artifacts/{identity}/roi.json",
                    "field_transform": f"artifacts/{identity}/field_transform.json",
                    "annotations": f"{identity}_annotations.json",
                    "pixel_covariances": {},
                }
            )
    manifest = {
        "schema_version": "comparison_dataset.v1",
        "sessions": sessions,
        "broadcast_clips": [],
        "collection_targets": {
            "pitch_opportunities_per_session": 40,
            "surveyed_targets_per_ball_type": 12,
            "conditions": ["nominal", "lighting", "background", "image_edge", "occlusion", "negative"],
        },
    }
    path = output / "dataset.json"
    path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    print(scaffold(parser.parse_args().output))


if __name__ == "__main__":
    main()
