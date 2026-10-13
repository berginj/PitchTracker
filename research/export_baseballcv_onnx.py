"""Export a supplied checkpoint in an isolated Ultralytics environment."""

import argparse
import os
from pathlib import Path
import shutil
import socket
import importlib
import hashlib
import json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--ball-class-id", type=int)
    args = parser.parse_args()
    source, output = args.checkpoint.resolve(), args.output.resolve()
    if (
        not source.is_file()
        or source.suffix != ".pt"
        or source.is_relative_to(output)
        or output.is_relative_to(source.parent)
    ):
        raise ValueError("Select a local checkpoint and a separate new export directory")
    if output.exists():
        raise FileExistsError("Choose a new export directory")
    output.mkdir(parents=True)
    copied = output / "supplied.pt"
    shutil.copyfile(source, copied)
    os.environ["YOLO_CONFIG_DIR"] = str(output / "settings")

    def denied(*values, **kwargs):
        raise RuntimeError("Automatic model download is disabled")

    socket.create_connection = denied
    setattr(socket.socket, "connect", denied)
    model = importlib.import_module("ultralytics").YOLO(str(copied))
    path = model.export(format="onnx", imgsz=640, opset=12, dynamic=False, nms=False, simplify=False, device="cpu")
    names = [model.names[i] for i in range(len(model.names))]
    possible = [i for i, name in enumerate(names) if name.lower() in {"baseball", "ball", "softball"}]
    ball_id = args.ball_class_id if args.ball_class_id is not None else (possible[0] if len(possible) == 1 else None)
    if ball_id is None or not 0 <= ball_id < len(names):
        raise ValueError("Declare the ball class explicitly when model names are ambiguous")
    digest = hashlib.sha256()
    with source.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    metadata = {
        "name": source.stem,
        "class_names": names,
        "ball_class_id": ball_id,
        "source_revision": args.source_revision,
        "checkpoint_sha256": digest.hexdigest(),
        "licenses": {"code": "unknown", "weights": "unknown", "data": "unknown"},
    }
    (output / "export_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    main()
