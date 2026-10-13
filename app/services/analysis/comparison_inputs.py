"""Validate study opportunities, human labels and exact recorded input bindings."""

import csv
import json
import math
from pathlib import Path

from contracts.model_bundle import file_hash, covariance2
from configs.settings import load_config


def local_path(base, value, suffix=None):
    path = (base / value).resolve()
    if not path.is_file() or (suffix and path.suffix.lower() not in suffix):
        raise ValueError(f"Missing or unexpected study input: {path.name}")
    return path


def load_dataset(path: Path, output: Path, *, hash_inputs=True):
    path = path.resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "comparison_dataset.v1" or not data.get("sessions"):
        raise ValueError("A comparison_dataset.v1 with sessions is required")
    sessions, identifiers = [], set()
    inputs = {str(path): file_hash(path)} if hash_inputs else {}
    for record in data["sessions"]:
        identity = str(record["id"])
        if not identity or identity in identifiers:
            raise ValueError("Study session identifiers must be distinct")
        identifiers.add(identity)
        root = (path.parent / record["root"]).resolve()
        if output.resolve().is_relative_to(root) or root.is_relative_to(output.resolve()):
            raise ValueError("Research output cannot contain or be inside captured sessions")
        if record["split"] not in {"development", "evaluation"} or record["ball_type"] not in {"baseball", "softball"}:
            raise ValueError("Declare a development/evaluation split and ball type")
        paths = {
            key: local_path(path.parent, record[key], suffix)
            for key, suffix in (
                ("config", {".yaml", ".yml"}),
                ("calibration", {".npz"}),
                ("roi", {".json"}),
                ("field_transform", {".json"}),
                ("annotations", {".json"}),
            )
        }
        annotation = json.loads(paths["annotations"].read_text(encoding="utf-8"))
        validate_annotations(annotation)
        counts = {}
        frame_mappings = {}
        camera_ids = {}
        for label in ("left", "right"):
            video = local_path(root, f"session_{label}.avi", {".avi"})
            timestamps = local_path(root, f"session_{label}_timestamps.csv", {".csv"})
            paths[f"video_{label}"] = video
            paths[f"timestamps_{label}"] = timestamps
            with timestamps.open(newline="", encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            counts[label] = sum(row.get("write_status") == "accepted" for row in rows)
            identities = {r["camera_id"] for r in rows if r.get("write_status") == "accepted"}
            if len(identities) != 1:
                raise ValueError("Each study video must contain one stable camera identity")
            camera_ids[label] = identities.pop()
            for row in rows:
                if row.get("write_status") == "accepted":
                    key = (row["camera_id"], int(row["frame_index"]))
                    if key in frame_mappings:
                        raise ValueError("Study frame identity is ambiguous")
                    frame_mappings[key] = int(row["t_capture_monotonic_ns"])
        if len(set(camera_ids.values())) != 2:
            raise ValueError("Study requires two distinct camera identities")
        camera = load_config(paths["config"]).camera
        for frame in annotation.get("frames", []):
            key = (frame["camera_id"], frame["frame_index"])
            if key not in frame_mappings or frame.get("timestamp_ns", frame_mappings[key]) != frame_mappings[key]:
                raise ValueError("Annotation does not match an accepted encoded frame")
            frame["timestamp_ns"] = frame_mappings[key]
            if frame["visibility"] == "visible":
                x, y = frame["center_px"]
                if not 0 <= x < camera.width or not 0 <= y < camera.height:
                    raise ValueError("Annotation center is outside the raw frame")
        for source in paths.values():
            if source.is_relative_to(output.resolve()):
                raise ValueError("Study inputs cannot be overwritten by research output")
            if hash_inputs:
                inputs[str(source)] = file_hash(source)
        covariances = {key: covariance2(value) for key, value in record.get("pixel_covariances", {}).items()}
        from app.services.analysis.comparison_rig import rig_binding

        geometry = rig_binding(
            paths["calibration"],
            json.loads(paths["roi"].read_text(encoding="utf-8")),
            json.loads(paths["field_transform"].read_text(encoding="utf-8")),
            camera_ids,
        )
        sessions.append(
            {
                **record,
                "root": root,
                "paths": paths,
                "annotation": annotation,
                "counts": counts,
                "rig_binding": geometry,
                "pixel_covariances": covariances,
            }
        )
    broadcasts = []
    for item in data.get("broadcast_clips", []):
        video = local_path(path.parent, item["video"], {".mp4", ".avi", ".mov"})
        if video.is_relative_to(output.resolve()):
            raise ValueError("Broadcast input is inside the output")
        if hash_inputs:
            inputs[str(video)] = file_hash(video)
        broadcasts.append({**item, "video": video})
    return sessions, broadcasts, inputs


def validate_annotations(data):
    if data.get("schema_version") != "comparison_annotations.v1" or data.get("human_reviewed") is not True:
        raise ValueError("Comparison labels require explicit human review")
    opportunities = data.get("opportunities", [])
    ids = set()
    for item in opportunities:
        if item["id"] in ids or type(item["start_ns"]) is not int or type(item["end_ns"]) is not int:
            raise ValueError("Invalid opportunity identity/time")
        if item["start_ns"] < 0 or item["end_ns"] <= item["start_ns"]:
            raise ValueError("Invalid opportunity window")
        ids.add(item["id"])
    ordered = sorted(opportunities, key=lambda v: v["start_ns"])
    if any(a["end_ns"] >= b["start_ns"] for a, b in zip(ordered, ordered[1:])):
        raise ValueError("Independent opportunity windows cannot overlap")
    seen = set()
    for frame in data.get("frames", []):
        key = (frame["camera_id"], frame["frame_index"])
        if key in seen or frame.get("visibility") not in {"visible", "occluded", "absent"}:
            raise ValueError("Duplicate frame or unsupported visibility label")
        seen.add(key)
        if type(frame["frame_index"]) is not int or frame["frame_index"] < 0:
            raise ValueError("Invalid labeled frame identity")
        if frame.get("opportunity_id") not in ids and frame.get("opportunity_id") is not None:
            raise ValueError("Frame references an unknown pitch opportunity")
        if frame["visibility"] == "visible":
            center = frame.get("center_px")
            if not center or len(center) != 2 or not all(math.isfinite(v) for v in center):
                raise ValueError("Visible ball requires a finite raw-pixel center")
        xyz = frame.get("xyz_ft")
        if xyz is not None and (len(xyz) != 3 or not all(math.isfinite(v) for v in xyz)):
            raise ValueError("Invalid surveyed target coordinates")


def verify_inputs(inputs):
    if any(file_hash(Path(path)) != digest for path, digest in inputs.items()):
        raise ValueError("Study inputs changed during comparison")
