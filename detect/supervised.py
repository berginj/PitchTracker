"""Bounded ONNX inference in an owned process with shared-memory frame input."""

from concurrent.futures import CancelledError
import json
import logging
from multiprocessing.shared_memory import SharedMemory
import queue
import subprocess
from threading import Event, RLock, Thread
from time import monotonic
from uuid import uuid4

import numpy as np

from app.services.analysis.process_cleanup import terminate_worker
from app.worker_process import worker_command
from contracts import Detection, Frame
from contracts.model_bundle import ModelBundle, covariance2
from detect.detector import Detector, DetectorHealth

logger = logging.getLogger(__name__)


class DetectorUnavailable(RuntimeError):
    """A detector failure that must remain visible in opportunity accounting."""


class SupervisedONNXDetector(Detector):
    version = "yolo11_onnx.v1"

    def __init__(self, bundle_path, *, localization=None, deadline_seconds=0.25, cancel=None):
        self.bundle = ModelBundle.load(bundle_path)
        self.localization = localization or self.bundle.localization
        if self.localization not in {"box", "refined"}:
            raise ValueError("Unknown localization profile")
        self.deadline_seconds = float(deadline_seconds)
        if not 0 < self.deadline_seconds <= 5:
            raise ValueError("Invalid inference deadline")
        self._lock = RLock()
        self._cancel = Event()
        self._parent_cancel = cancel or Event()
        self._process = None
        self._memory = None
        self._replies: queue.Queue = queue.Queue()
        self._readers: list[Thread] = []
        self._failures = 0
        self.last_roundtrip_ms = 0.0
        self.last_detection_ns = 0

    def _read(self, stream):
        try:
            for line in stream:
                self._replies.put(line)
        finally:
            self._replies.put(None)

    def _errors(self, stream):
        for line in stream:
            logger.debug("ONNX worker: %s", line.rstrip()[:1000])

    def _receive(self, deadline):
        while monotonic() < deadline:
            if self._cancel.is_set() or self._parent_cancel.is_set():
                raise CancelledError()
            try:
                line = self._replies.get(timeout=min(0.02, max(0.001, deadline - monotonic())))
            except queue.Empty:
                continue
            if line is None:
                raise DetectorUnavailable("Detector worker exited")
            response = json.loads(line)
            if not response.get("ok"):
                raise DetectorUnavailable(response.get("error", "Detector failed"))
            return response
        raise DetectorUnavailable("Detector deadline exceeded")

    def warm(self):
        with self._lock:
            if self._cancel.is_set() or self._failures >= 2:
                raise DetectorUnavailable("Detector is closed or failed repeatedly; select a profile while idle")
            if self._process is not None:
                return
            # Recheck bytes before every worker generation, including recovery.
            current = ModelBundle.load(self.bundle.manifest_path)
            if current.bundle_sha256 != self.bundle.bundle_sha256 or current.model_sha256 != self.bundle.model_sha256:
                raise DetectorUnavailable("Detector bundle changed; select a new profile while idle")
            self._replies = queue.Queue()
            self._process = subprocess.Popen(
                worker_command("detector"),
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            self._memory = SharedMemory(create=True, size=16 * 1024 * 1024)
            self._readers = [
                Thread(target=self._read, args=(self._process.stdout,), daemon=True),
                Thread(target=self._errors, args=(self._process.stderr,), daemon=True),
            ]
            for reader in self._readers:
                reader.start()
            try:
                self._send({"bundle": str(self.bundle.manifest_path), "localization": self.localization})
                ready = self._receive(monotonic() + 20)
                if (
                    ready.get("model_sha256") != self.bundle.model_sha256
                    or ready.get("bundle_sha256") != self.bundle.bundle_sha256
                ):
                    raise DetectorUnavailable("Worker loaded another model")
            except (Exception, CancelledError):
                self._failures += 1
                self._dispose()
                raise

    def _send(self, payload):
        assert self._process is not None and self._process.stdin is not None
        stream = self._process.stdin
        line = json.dumps(payload, allow_nan=False) + "\n"

        def write():
            try:
                stream.write(line)
                stream.flush()
            except (OSError, ValueError):
                self._replies.put(None)

        writer = Thread(target=write, daemon=True)
        self._readers = [reader for reader in self._readers if reader.is_alive()]
        self._readers.append(writer)
        writer.start()

    def detect(self, frame: Frame) -> list[Detection]:
        with self._lock:
            self.warm()
            started = monotonic()
            image = np.ascontiguousarray(frame.image)
            if image.dtype != np.uint8 or image.shape[:2] != (frame.height, frame.width):
                raise ValueError("Frame dimensions/type do not match detector input")
            assert self._memory is not None
            if image.nbytes > len(self._memory.buf):
                raise ValueError("Frame exceeds detector memory limit")
            token = uuid4().hex
            try:
                np.ndarray(image.shape, dtype=np.uint8, buffer=self._memory.buf)[:] = image
                metadata = {
                    key: getattr(frame, key)
                    for key in (
                        "camera_id",
                        "frame_index",
                        "t_capture_monotonic_ns",
                        "width",
                        "height",
                        "pixfmt",
                        "capture_epoch",
                        "correlation_id",
                    )
                }
                self._send(
                    {
                        "schema_version": "detector_frame.v1",
                        "token": token,
                        "memory": self._memory.name,
                        "shape": list(image.shape),
                        "frame": metadata,
                    }
                )
                response = self._receive(started + self.deadline_seconds)
                if response.get("token") != token:
                    raise DetectorUnavailable("Detector response identity mismatch")
                values = []
                for data in response["detections"]:
                    for key in ("pixel_covariance_px2", "prediction_covariance_px2"):
                        data[key] = covariance2(data.get(key))
                    detection = Detection(**data)
                    if (detection.camera_id, detection.frame_index, detection.t_capture_monotonic_ns) != (
                        frame.camera_id,
                        frame.frame_index,
                        frame.t_capture_monotonic_ns,
                    ):
                        raise DetectorUnavailable("Detection frame identity mismatch")
                    values.append(detection)
                self.last_detection_ns = frame.t_capture_monotonic_ns if values else self.last_detection_ns
                return values
            except (Exception, CancelledError):
                self._failures += 1
                self._dispose()
                raise
            finally:
                self.last_roundtrip_ms = (monotonic() - started) * 1000

    def _dispose(self):
        process, self._process = self._process, None
        if process is not None:
            terminate_worker(process)
            for reader in self._readers:
                reader.join(timeout=1)
            for stream in (process.stdin, process.stdout, process.stderr):
                if stream is not None:
                    stream.close()
        memory, self._memory = self._memory, None
        if memory is not None:
            memory.close()
            memory.unlink()

    def close(self):
        self._cancel.set()
        with self._lock:
            self._dispose()

    def health(self):
        return DetectorHealth(0.0, self.last_detection_ns)
