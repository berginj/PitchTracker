"""Persistent, disposable focus-preview camera owner. No rig evidence is saved."""

from __future__ import annotations

import base64
import contextlib
import json
import os
import sys
import threading
from typing import TextIO

import cv2

from app.services.capture.setup_devices import open_setup_pair
from capture.camera_device import CameraDevice
from contracts import Frame
from contracts.focus_preview import FOCUS_PREVIEW_SCHEMA
from contracts.setup_capture import SetupCaptureRequest
from exceptions import CameraError
from log_config.logger import get_logger

logger = get_logger(__name__)


def stream(request: SetupCaptureRequest, output: TextIO, stop: threading.Event) -> None:
    """Open once and show diagnostic images, including black frames, honestly."""
    latest: dict[str, Frame] = {}
    lock = threading.Lock()

    def read(camera: CameraDevice, side: str) -> None:
        while not stop.is_set():
            try:
                frame = camera.read_frame(1000)
            except CameraError as exc:
                logger.warning("Focus camera {} read failed: {}", side, exc)
                if stop.wait(0.1):
                    return
                continue
            with lock:
                latest[side] = frame

    with open_setup_pair(request) as (left, right):
        readers = [threading.Thread(target=read, args=(camera, side), daemon=True)
                   for camera, side in ((left, "left"), (right, "right"))]
        for reader in readers:
            reader.start()
        output.write(json.dumps({"schema_version": FOCUS_PREVIEW_SCHEMA, "kind": "ready"}) + "\n")
        output.flush()
        sent: dict[str, int] = {}
        try:
            while not stop.wait(0.05):
                with lock:
                    snapshot = dict(latest)
                for side, frame in snapshot.items():
                    if frame.image is None or sent.get(side) == frame.frame_index:
                        continue
                    sent[side] = frame.frame_index
                    _send_frame(output, side, frame)
        finally:
            stop.set()
            for reader in readers:
                reader.join(timeout=1.5)
            if any(reader.is_alive() for reader in readers):
                # Closing a device under an active native reader is unsafe.
                # Only this disposable camera-owner process exits; the parent reaps it.
                logger.error("Focus reader did not stop; exiting the disposable camera-owner process")
                os._exit(2)


def _send_frame(output: TextIO, side: str, frame: Frame) -> None:
    ok, encoded = cv2.imencode(".jpg", frame.image, [cv2.IMWRITE_JPEG_QUALITY, 92])
    if not ok:
        raise ValueError("Unable to encode a focus preview frame")
    payload = {
        "schema_version": FOCUS_PREVIEW_SCHEMA, "kind": "frame", "side": side,
        "camera_id": frame.camera_id, "frame_index": frame.frame_index,
        "t_capture_monotonic_ns": frame.t_capture_monotonic_ns,
        "timing": frame.timing.to_payload(),
        "jpeg": base64.b64encode(encoded).decode("ascii"),
    }
    output.write(json.dumps(payload) + "\n")
    output.flush()


def main() -> None:
    """Read one request; stdin closure requests graceful camera shutdown."""
    output = sys.stdout
    stop = threading.Event()
    try:
        envelope = json.loads(sys.stdin.readline())
        if envelope.get("schema_version") != FOCUS_PREVIEW_SCHEMA:
            raise ValueError("Unsupported focus preview schema")
        request = SetupCaptureRequest.from_payload(envelope["request"])

        def watch_input() -> None:
            sys.stdin.readline()
            stop.set()

        threading.Thread(target=watch_input, daemon=True).start()
        with contextlib.redirect_stdout(sys.stderr):
            stream(request, output, stop)
    except Exception as exc:  # deliberate subprocess isolation boundary
        logger.exception("Focus preview failed")
        output.write(json.dumps({"schema_version": FOCUS_PREVIEW_SCHEMA, "kind": "error", "message": str(exc)}) + "\n")
        output.flush()
    finally:
        stop.set()


if __name__ == "__main__":
    main()
