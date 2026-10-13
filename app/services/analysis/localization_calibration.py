"""Development-only localization error models; evaluation labels cannot train them."""

import json
from pathlib import Path
import numpy as np

from app.services.analysis.comparison_inputs import load_dataset, verify_inputs
from contracts.model_bundle import file_hash
from contracts.research_artifacts import research_metadata


def estimate_localization_models(report_path):
    report_path = Path(report_path)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    verify_inputs(report["inputs"])
    request = report["request"]
    sessions, _, _ = load_dataset(Path(request["dataset_path"]), Path(request["output_dir"]))
    by_id = {s["id"]: s for s in sessions}
    errors: dict[str, list[np.ndarray]] = {}
    for row in report["results"]:
        if row["split"] != "development" or row["status"] != "COMPLETED" or not row["variant"].endswith(":greedy_v1"):
            continue
        session = by_id[row["session_id"]]
        labels = {
            (f["camera_id"], f["frame_index"]): f
            for f in session["annotation"]["frames"]
            if f["visibility"] == "visible"
        }
        artifact = Path(row["artifact"])
        if file_hash(artifact) != row["artifact_sha256"]:
            raise ValueError("Comparison artifact changed")
        for frame in json.loads(artifact.read_text(encoding="utf-8"))["frames"]:
            label = labels.get((frame["camera_id"], frame["frame_index"]))
            if label is None or not frame["detections"]:
                continue
            truth = np.asarray(label["center_px"])
            candidates = [(np.linalg.norm(np.array([d["u"], d["v"]]) - truth), d) for d in frame["detections"]]
            distance, best = min(candidates, key=lambda v: v[0])
            if distance > max(3.0, label.get("radius_px", 4.0) * 2):
                continue
            profile = row["variant"].split(":")[0]
            basis = best.get("localization_method", "legacy")
            key = f"{profile}:{basis}"
            errors.setdefault(key, []).append(np.array([best["u"], best["v"]]) - truth)
    models = {}
    for key, vectors in errors.items():
        if len(vectors) < 30:
            continue
        values = np.asarray(vectors)
        # Second moment retains bias rather than subtracting it from uncertainty.
        covariance = values.T @ values / len(values) + np.eye(2) * 0.25
        models[key] = {
            "count": len(values),
            "pixel_covariance_px2": covariance.tolist(),
            "mean_error_px": values.mean(axis=0).tolist(),
        }
    return {
        **research_metadata("localization_models.v1"),
        "source_report_sha256": file_hash(report_path),
        "source_inputs": report["inputs"],
        "model": report["model"],
        "models": models,
        "basis": "development_localization_second_moment",
        "physical_claim_eligible": False,
    }
