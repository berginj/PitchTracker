"""Operator-requested shadow timing collection from already-recording capture."""

import json
import logging
from pathlib import Path
import queue
from threading import Event, Lock, Thread
from time import monotonic

import numpy as np

from app.events.event_types import FrameCapturedEvent
from app.pipeline.recording.evidence_package import _atomic_write_text
from app.services.analysis.comparison_metrics import distribution
from app.services.analysis.comparison_qualification import configuration_binding
from app.services.analysis.pipeline_comparison import comparison_fingerprint
from app.services.analysis.trial_pipeline import ShadowStereoPipeline
from contracts import Frame
from contracts.research_artifacts import research_metadata
from contracts.model_bundle import ModelBundle, file_hash
from detect.supervised import SupervisedONNXDetector

logger = logging.getLogger(__name__)


class DetectorTrial:
    """A timing sidecar never publishes detections into primary analysis."""

    def __init__(
        self,
        bus,
        config,
        bundle_path,
        variant,
        output,
        recording_state,
        session_dir,
        backend,
        calibration_path,
        roi_path,
        left_id,
        right_id,
        field_transform,
        cancel=None,
    ):
        self.bus, self.config = bus, config
        self.bundle = ModelBundle.load(Path(bundle_path))
        self.variant, self.output = variant, Path(output).resolve()
        if self.output.exists() or self.output.with_suffix(".frames.jsonl").exists():
            raise FileExistsError("Choose a new trial output file")
        if self.output.is_relative_to(Path(session_dir).resolve()):
            raise ValueError("Trial output must be outside the captured session")
        if variant != f"baseballcv_{self.bundle.localization}:{variant.split(':')[1]}" or variant.split(":")[1] not in {
            "greedy_v1",
            "global_v2",
            "global_v3",
        }:
            raise ValueError("Trial profile must match the bundle localization")
        self.recording_state, self.session_dir, self.backend = recording_state, str(session_dir), backend
        from app.services.analysis.comparison_rig import rig_binding

        self.rig_binding = rig_binding(
            calibration_path,
            json.loads(Path(roi_path).read_text(encoding="utf-8")),
            field_transform,
            {"left": left_id, "right": right_id},
        )
        self.cancel, self.lock = cancel or Event(), Lock()
        self.workers = [
            SupervisedONNXDetector(self.bundle.manifest_path, deadline_seconds=5, cancel=self.cancel) for _ in range(2)
        ]
        self.shadow = ShadowStereoPipeline(config, variant, calibration_path, roi_path, left_id, right_id)
        self.camera_order = {left_id: 0, right_id: 1}
        self.results: queue.Queue = queue.Queue(maxsize=4)
        self.queues: list[queue.Queue[tuple[Frame, float]]] = [queue.Queue(maxsize=2), queue.Queue(maxsize=2)]
        self.failures = {}
        self.threads = []
        self.cameras = {}
        self.rows = []
        self.started = None
        self.recorded = True
        self.subscribed = False

    def start(self):
        image = np.zeros((self.config.camera.height, self.config.camera.width, 3), np.uint8)
        try:
            for worker in self.workers:
                worker.detect(Frame("warmup", 0, 0, image, image.shape[1], image.shape[0], "BGR8"))
            if self.cancel.is_set():
                raise RuntimeError("Trial was cancelled during warmup")
            self.started = monotonic()
            self.threads = [Thread(target=self._run, args=(i,), daemon=True) for i in range(2)]
            self.threads.append(Thread(target=self._stereo, daemon=True))
            for thread in self.threads:
                thread.start()
            self.bus.subscribe(FrameCapturedEvent, self.offer)
            self.subscribed = True
            logger.info("Shadow detector trial started: variant=%s", self.variant)
        except Exception:
            self.cancel.set()
            for worker in self.workers:
                worker.close()
            raise

    def offer(self, event):
        frame = event.frame
        if self.cancel.is_set():
            return
        with self.lock:
            self.recorded = self.recorded and bool(self.recording_state())
            if frame.camera_id not in self.cameras:
                if frame.camera_id not in self.camera_order:
                    self.recorded = False
                    return
                self.cameras[frame.camera_id] = {
                    "index": self.camera_order[frame.camera_id],
                    "offered": 0,
                    "processed": 0,
                    "times": [],
                    "pipeline_times": [],
                    "capture_epoch": frame.capture_epoch,
                }
            camera = self.cameras[frame.camera_id]
            if camera["capture_epoch"] != frame.capture_epoch or (frame.width, frame.height) != (
                self.config.camera.width,
                self.config.camera.height,
            ):
                self.recorded = False
            camera["offered"] += 1
            index = camera["index"]
        try:
            self.queues[index].put_nowait((frame, monotonic()))
        except queue.Full:
            self._outcome(frame, "QUEUE_DROPPED", None)

    def _outcome(self, frame, status, elapsed, pipeline_elapsed=None):
        with self.lock:
            camera = self.cameras[frame.camera_id]
            if status == "PROCESSED":
                camera["processed"] += 1
                camera["times"].append(elapsed)
                camera["pipeline_times"].append(pipeline_elapsed)
            self.rows.append(
                {
                    "camera_id": frame.camera_id,
                    "frame_index": frame.frame_index,
                    "timestamp_ns": frame.t_capture_monotonic_ns,
                    "capture_epoch": frame.capture_epoch,
                    "status": status,
                    "roundtrip_ms": elapsed,
                    "pipeline_ms": pipeline_elapsed,
                }
            )

    def _run(self, index):
        worker = self.workers[index]
        while not self.cancel.is_set():
            try:
                frame, offered_at = self.queues[index].get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                values = worker.detect(frame)
                try:
                    self.results.put_nowait((frame, values, worker.last_roundtrip_ms, offered_at))
                except queue.Full:
                    self._outcome(frame, "RESULT_QUEUE_DROPPED", None)
            except Exception:
                count = self.failures.get(frame.camera_id, 0)
                if count < 2:
                    logger.warning(
                        "Shadow detector failed: camera=%s frame=%s", frame.camera_id, frame.frame_index, exc_info=True
                    )
                self.failures[frame.camera_id] = count + 1
                self._outcome(frame, "DETECTOR_FAILED", None)

    def _stereo(self):
        while not self.cancel.is_set():
            try:
                frame, values, elapsed, offered_at = self.results.get(timeout=0.05)
            except queue.Empty:
                continue
            try:
                self.shadow.process(frame, values)
                self._outcome(frame, "PROCESSED", elapsed, (monotonic() - offered_at) * 1000)
            except Exception:
                logger.warning(
                    "Shadow stereo failed: camera=%s frame=%s", frame.camera_id, frame.frame_index, exc_info=True
                )
                self._outcome(frame, "STEREO_FAILED", None)

    def stop(self):
        if self.subscribed:
            self.bus.unsubscribe(FrameCapturedEvent, self.offer)
            self.subscribed = False
        self.cancel.set()
        for worker in self.workers:
            worker.close()
        for thread in self.threads:
            thread.join(timeout=2)
        if any(thread.is_alive() for thread in self.threads):
            self.recorded = False
            logger.error("Shadow trial workers did not drain before the stop deadline")
        for source in self.queues:
            while not source.empty():
                try:
                    frame, offered_at = source.get_nowait()
                    self._outcome(frame, "CANCELLED", None)
                except queue.Empty:
                    break
        while not self.results.empty():
            frame, values, elapsed, offered_at = self.results.get_nowait()
            self._outcome(frame, "CANCELLED", None)
        self.shadow.close()
        duration = monotonic() - self.started if self.started is not None else 0.0
        self.output.parent.mkdir(parents=True, exist_ok=True)
        journal = self.output.with_suffix(".frames.jsonl")
        _atomic_write_text(journal, "".join(json.dumps(r, allow_nan=False) + "\n" for r in self.rows))
        cameras = [
            {
                "camera_id": key,
                "offered": value["offered"],
                "processed": value["processed"],
                "roundtrip_p95_ms": distribution(value["times"])["p95"],
                "pipeline_p95_ms": distribution(value["pipeline_times"])["p95"],
            }
            for key, value in self.cameras.items()
        ]
        report = {
            **research_metadata("detector_sustained_run.v1"),
            "variant": self.variant,
            "configuration_binding": configuration_binding(self.config, self.bundle, self.variant),
            "rig_binding": self.rig_binding,
            "bundle_sha256": self.bundle.bundle_sha256,
            "implementation": comparison_fingerprint(),
            "source_kind": "operator_capture" if self.backend in {"uvc", "opencv"} else "simulator_capture",
            "recording_enabled": self.recorded,
            "source_session": self.session_dir,
            "duration_seconds": duration,
            "cameras": cameras,
            "frame_outcomes_path": str(journal),
            "frame_outcomes_sha256": file_hash(journal),
            "physical_claim_eligible": False,
        }
        _atomic_write_text(self.output, json.dumps(report, indent=2, allow_nan=False))
        logger.info("Shadow detector trial stopped: variant=%s", self.variant)
        return self.output
