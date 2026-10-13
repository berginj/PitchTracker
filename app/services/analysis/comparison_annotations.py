"""Local human annotation revisions never overwrite captured inputs."""

import json
from pathlib import Path

from app.services.analysis.comparison_inputs import validate_annotations


def save_annotation_revision(source, output, payload):
    source, output = Path(source).resolve(), Path(output).resolve()
    if source == output or output.exists() or output.suffix != ".json":
        raise ValueError("Choose a new JSON annotation revision")
    validate_annotations(payload)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    return output


def bind_annotation_revision(dataset, session_id, annotation, output):
    dataset, annotation, output = Path(dataset).resolve(), Path(annotation).resolve(), Path(output).resolve()
    if output.exists() or output == dataset:
        raise ValueError("Choose a new dataset revision")
    labels = json.loads(annotation.read_text(encoding="utf-8"))
    validate_annotations(labels)
    data = json.loads(dataset.read_text(encoding="utf-8"))
    found = False
    for session in data["sessions"]:
        for field in ("root", "config", "calibration", "roi", "field_transform", "annotations"):
            session[field] = str((dataset.parent / session[field]).resolve())
        if session["id"] == session_id:
            session["annotations"] = str(annotation)
            found = True
    if not found:
        raise ValueError("Unknown annotation session")
    for clip in data.get("broadcast_clips", []):
        clip["video"] = str((dataset.parent / clip["video"]).resolve())
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    return output
