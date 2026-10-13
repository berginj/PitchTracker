"""Separate, supervised broadcast-image research; never a stereo fallback."""

import json
import logging
from pathlib import Path
import queue
import subprocess
from threading import Thread
from time import monotonic
import sys

from app.services.analysis.process_cleanup import terminate_worker
from contracts.model_bundle import file_hash

logger = logging.getLogger(__name__)
REVISION = "c3c26c979766b28e0c78c3fee2edc2aa3dad571e"


def load_research_assets(path):
    path = path.resolve()
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("schema_version") != "baseballcv_research_assets.v1":
        raise ValueError("Unsupported monocular model assets")
    if not all(data.get("licenses", {}).get(k) for k in ("code", "weights", "data")):
        raise ValueError("Declare research asset licensing")
    models = {}
    for alias, item in data["models"].items():
        model = (path.parent / item["file"]).resolve()
        if not model.is_relative_to(path.parent) or model.suffix != ".pt" or file_hash(model) != item["sha256"]:
            raise ValueError("Missing, changed or unexpected research model")
        models[alias] = {"path": str(model), "sha256": item["sha256"]}
    if not all(alias in models for alias in ("phc_detector", "glove_tracking", "ball_trackingv4")):
        raise ValueError("Monocular research requires catcher, glove and ball models")
    return models, data["licenses"]


def run_local_worker(request, payload, check):
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3]))
    script = root / "research" / "baseballcv_local_worker.py"
    if not script.is_file():
        raise ValueError("Installed local research worker is missing")
    process = subprocess.Popen(
        [str(request.external_python), str(script)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    replies: queue.Queue = queue.Queue()
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    stdin, stdout, stderr = process.stdin, process.stdout, process.stderr

    def read():
        for line in stdout:
            replies.put(line)
        replies.put(None)

    def errors():
        for line in stderr:
            logger.debug("Monocular worker: %s", line.rstrip()[:1000])

    def write():
        try:
            stdin.write(json.dumps(payload, allow_nan=False) + "\n")
            stdin.flush()
        except (OSError, ValueError):
            replies.put(None)

    readers = [Thread(target=read, daemon=True), Thread(target=errors, daemon=True), Thread(target=write, daemon=True)]
    try:
        for reader in readers:
            reader.start()
        deadline = monotonic() + 300
        while monotonic() < deadline:
            check()
            try:
                line = replies.get(timeout=0.05)
            except queue.Empty:
                continue
            if not line:
                raise ValueError("Monocular worker exited without a result")
            value = json.loads(line)
            if not value.get("ok"):
                raise ValueError(value.get("error", "Monocular worker failed"))
            return value
        raise ValueError("Monocular research exceeded its five-minute clip deadline")
    finally:
        terminate_worker(process)
        for reader in readers:
            if reader.ident is not None:
                reader.join(timeout=1)
        for stream in (stdin, stdout, stderr):
            stream.close()


def run_monocular_comparisons(request, sessions, broadcasts, check, cancel):
    clips = [
        (f"{s['id']}:{side}", s["paths"][f"video_{side}"], s["annotation"].get("monocular", {}).get(side, {}))
        for s in sessions
        for side in ("left", "right")
    ]
    clips.extend((str(c["id"]), c["video"], c.get("labels", {})) for c in broadcasts)
    try:
        models, licenses = load_research_assets(request.monocular_assets)
        revision = subprocess.run(
            ["git", "-C", str(request.external_repository), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        if revision != REVISION:
            raise ValueError("Research repository does not match the pinned upstream revision")
        status = subprocess.run(
            ["git", "-C", str(request.external_repository), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True,
            text=True,
            check=True,
            timeout=10,
        ).stdout.strip()
        if status:
            raise ValueError("Upstream tracked research source changed")
    except (ValueError, OSError, subprocess.SubprocessError) as exc:
        return [
            {
                "clip_id": name,
                "status": "UNAVAILABLE",
                "reason": str(exc),
                "measurement_basis": "image_zone_at_glove_arrival",
            }
            for name, video, labels in clips
        ]
    outputs = []
    for name, video, labels in clips:
        check()
        key = file_hash(video)
        result = {
            "clip_id": name,
            "source_sha256": key,
            "upstream_revision": revision,
            "licenses": licenses,
            "model_hashes": {alias: v["sha256"] for alias, v in models.items()},
            "measurement_basis": "image_zone_at_glove_arrival",
            "physical_claim_eligible": False,
            "plate_crossing_xyz_ft": None,
            "speed_mph": None,
        }
        try:
            payload = {
                "video": str(video),
                "models": models,
                "repository": str(request.external_repository),
                "output_dir": str(request.output_dir / "monocular" / key),
            }
            response = run_local_worker(request, payload, check)
            if (
                response.get("schema_version") != "baseballcv_local_result.v1"
                or response.get("measurement_basis") != "image_zone_at_glove_arrival"
            ):
                raise ValueError("Monocular worker returned an unexpected measurement basis")
            result.update(
                status="COMPLETED",
                results=response["results"],
                packages=response.get("packages"),
                adapter_sha256=response.get("adapter_sha256"),
            )
            estimates = response["results"]
            if estimates and labels.get("glove_frame") is not None:
                predicted = estimates[0].get("ball_glove_frame")
                result["glove_frame_error"] = None if predicted is None else abs(predicted - labels["glove_frame"])
        except (ValueError, OSError, KeyError) as exc:
            logger.warning("Monocular comparison unavailable: clip=%s", name, exc_info=True)
            result.update(status="UNAVAILABLE", reason=str(exc))
        outputs.append(result)
    return outputs
