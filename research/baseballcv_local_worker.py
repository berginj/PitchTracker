"""Local-only adapter around the pinned upstream public analyze method.

Run with an isolated research Python. No upstream source or weights are vendored.
"""

import contextlib
import hashlib
import json
import os
from pathlib import Path
import socket
import sys
import importlib
import importlib.metadata

UPSTREAM_REVISION = "c3c26c979766b28e0c78c3fee2edc2aa3dad571e"


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            value.update(chunk)
    return value.hexdigest()


def deny_network(*args, **kwargs):
    raise RuntimeError("Network access is disabled in local BaseballCV research")


def analyze_local_video(module, scraper_module, pandas, request):
    """Provide local assets and a local video source through upstream public APIs."""
    root = Path(request["output_dir"]).resolve()
    root.mkdir(parents=True, exist_ok=True)
    source = Path(request["video"]).resolve()
    target_dir = root / "savant_videos"
    target_dir.mkdir(exist_ok=True)
    target = target_dir / "local_0_0.mp4"
    if target.exists():
        if digest(target) != digest(source):
            raise ValueError("Monocular input mirror changed")
    else:
        import shutil

        shutil.copyfile(source, target)
    models = {alias: Path(value["path"]).resolve() for alias, value in request["models"].items()}
    for alias, path in models.items():
        if digest(path) != request["models"][alias]["sha256"]:
            raise ValueError("Research model hash mismatch")

    class LocalLoader:
        def load_model(self, alias, *args, **kwargs):
            if alias not in models:
                raise ValueError(f"Local model missing: {alias}")
            return str(models[alias])

    class LocalSource:
        play_ids_df = pandas.DataFrame([{"play_id": "0", "game_pk": "0"}])

        @classmethod
        def from_date_range(cls, *args, **kwargs):
            return cls()

        def run_executor(self):
            return None

    real_yolo = module.YOLO

    def local_yolo(path, *args, **kwargs):
        resolved = Path(path).resolve()
        if str(path) == "yolov8n-pose.pt" and "pose" in models:
            resolved = models["pose"]
        if resolved not in models.values():
            raise ValueError("Undeclared model request; automatic download is forbidden")
        return real_yolo(str(resolved), *args, **kwargs)

    module.LoadTools = LocalLoader
    module.YOLO = local_yolo
    scraper_module.BaseballSavVideoScraper = LocalSource
    analyzer = module.DistanceToZone(results_dir=str(root), device="cpu", verbose=False)
    return analyzer.analyze("2000-01-01", "2000-01-01", create_video=False, save_csv=False)


def sanitize(value):
    import math

    if isinstance(value, dict):
        return {str(k): sanitize(v) for k, v in value.items()}
    if isinstance(value, (tuple, list)):
        return [sanitize(v) for v in value]
    if hasattr(value, "item"):
        return sanitize(value.item())
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def main():
    request = json.loads(sys.stdin.readline())
    socket.create_connection = deny_network
    setattr(socket.socket, "connect", deny_network)
    os.environ["YOLO_OFFLINE"] = "true"
    try:
        sys.path.insert(0, request["repository"])
        with contextlib.redirect_stdout(sys.stderr):
            pandas = importlib.import_module("pandas")
            distance_to_zone = importlib.import_module("baseballcv.functions.utils.baseball_utils.distance_to_zone")
            savant_scraper = importlib.import_module("baseballcv.functions.savant_scraper")

            rows = analyze_local_video(distance_to_zone, savant_scraper, pandas, request)
        print(
            json.dumps(
                {
                    "ok": True,
                    "schema_version": "baseballcv_local_result.v1",
                    "results": sanitize(rows),
                    "measurement_basis": "image_zone_at_glove_arrival",
                    "packages": {
                        name: importlib.metadata.version(name)
                        for name in ("ultralytics", "torch", "opencv-python", "numpy", "mediapipe")
                    },
                    "adapter_sha256": digest(Path(__file__)),
                    "physical_claim_eligible": False,
                },
                allow_nan=False,
            ),
            flush=True,
        )
    except Exception as exc:
        print(
            json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}", "physical_claim_eligible": False}),
            flush=True,
        )


if __name__ == "__main__":
    main()
