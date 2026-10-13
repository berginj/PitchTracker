"""Shared-memory detector console worker; no camera or UI ownership."""

from dataclasses import asdict, replace
import contextlib
import json
from multiprocessing.shared_memory import SharedMemory
import sys


def main():
    import cv2
    import numpy as np
    from pathlib import Path
    from contracts import Frame
    from contracts.model_bundle import ModelBundle
    from detect.yolo11 import prepare, decode

    try:
        setup = json.loads(sys.stdin.readline())
        bundle = ModelBundle.load(Path(setup["bundle"]))
        bundle = replace(bundle, localization=setup["localization"])
        cv2.setNumThreads(1)
        with contextlib.redirect_stdout(sys.stderr):
            net = cv2.dnn.readNetFromONNX(str(bundle.model_path))
            net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
            net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
            width, height = bundle.input_size
            warm_image = np.zeros((height, width, 3), dtype=np.uint8)
            blob, transform = prepare(warm_image, bundle.input_size)
            net.setInput(blob)
            decode(net.forward(), Frame("warmup", 0, 0, warm_image, width, height, "BGR8"), transform, bundle)
        print(
            json.dumps({"ok": True, "model_sha256": bundle.model_sha256, "bundle_sha256": bundle.bundle_sha256}),
            flush=True,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"MODEL_LOAD_FAILED: {exc}"}), flush=True)
        return
    for line in sys.stdin:
        request = {}
        memory = None
        try:
            request = json.loads(line)
            if request["schema_version"] != "detector_frame.v1":
                raise ValueError("Unsupported frame schema")
            shape = tuple(request["shape"])
            if len(shape) not in (2, 3) or any(type(v) is not int or v <= 0 for v in shape):
                raise ValueError("Invalid image shape")
            if len(shape) == 3 and shape[2] != 3:
                raise ValueError("Invalid color channels")
            memory = SharedMemory(name=request["memory"])
            if int(np.prod(shape)) > len(memory.buf):
                raise ValueError("Image exceeds shared memory")
            image: np.ndarray = np.ndarray(shape, dtype=np.uint8, buffer=memory.buf).copy()
            frame = Frame(image=image, **request["frame"])
            blob, transform = prepare(image, bundle.input_size)
            with contextlib.redirect_stdout(sys.stderr):
                net.setInput(blob)
                values = decode(net.forward(), frame, transform, bundle)
            response = {"ok": True, "token": request["token"], "detections": [asdict(v) for v in values]}
        except Exception as exc:
            response = {"ok": False, "token": request.get("token"), "error": f"INFERENCE_FAILED: {exc}"}
        finally:
            if memory is not None:
                memory.close()
        print(json.dumps(response, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
