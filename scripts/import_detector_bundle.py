"""Import an explicitly supplied ONNX file into a local detector bundle."""

import argparse
import json
from pathlib import Path
import shutil

from contracts.model_bundle import ModelBundle, file_hash
from contracts.research_artifacts import research_metadata


def import_bundle(model, destination, metadata):
    model, destination = Path(model).resolve(), Path(destination).resolve()
    if model.suffix.lower() != ".onnx" or not model.is_file():
        raise ValueError("Select a local ONNX model")
    if destination.is_relative_to(model.parent) or model.is_relative_to(destination):
        raise ValueError("Bundle output must be separate from the source model directory")
    target, manifest = destination / "model.onnx", destination / "bundle.json"
    if target.exists() or manifest.exists():
        raise FileExistsError("Choose a new bundle directory; existing assets are preserved")
    payload = {
        **research_metadata("detector_bundle.v1"),
        "model_file": target.name,
        "model_sha256": file_hash(model),
        "input_size": [640, 640],
        "output_layout": "channels_first",
        "preprocessing": "rgb_letterbox_114_div255",
        "confidence_threshold": 0.25,
        "nms_threshold": 0.45,
        "localization": "box",
        "max_candidates": 20,
        "redistribution_allowed": False,
        **metadata,
    }
    if payload["model_file"] != target.name or payload["model_sha256"] != file_hash(model):
        raise ValueError("Metadata cannot replace model identity")
    ModelBundle.from_payload(payload, manifest, model_source=model)
    destination.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(model, target)
    manifest.write_text(json.dumps(payload, indent=2, allow_nan=False), encoding="utf-8")
    return ModelBundle.load(manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--model", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--metadata",
        type=Path,
        required=True,
        help="JSON declaring name, class_names, ball_class_id, source_revision and licenses",
    )
    args = parser.parse_args()
    result = import_bundle(args.model, args.output, json.loads(args.metadata.read_text(encoding="utf-8")))
    print(result.manifest_path)


if __name__ == "__main__":
    main()
