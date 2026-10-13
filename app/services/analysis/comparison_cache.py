"""Session-scoped detector cache independent of stereo and tracklet variants."""

from dataclasses import asdict, replace
import hashlib
import json
import logging
import math
from time import perf_counter

from app.pipeline.recording.evidence_package import _atomic_write_text
from contracts import Detection
from contracts.research_artifacts import research_metadata

logger = logging.getLogger(__name__)


class CachedDetector:
    def __init__(self, detector, cache_dir, identity, expected_frames, covariance=None):
        self.detector = detector
        self.expected_frames = expected_frames
        self.covariance = covariance
        self.key = hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()
        self.path = cache_dir / f"{self.key}.json"
        self.rows = {}
        self.times = []
        self.reused = False
        self.offered = 0
        if self.path.is_file():
            try:
                saved = json.loads(self.path.read_text(encoding="utf-8"))
                if (
                    saved.get("cache_key") == self.key
                    and saved.get("complete")
                    and len(saved["rows"]) == expected_frames
                ):
                    for key, row in saved["rows"].items():
                        epoch, index, timestamp = key.rsplit(":", 2)
                        if not math.isfinite(row["milliseconds"]) or row["milliseconds"] < 0:
                            raise ValueError("Invalid cached timing")
                        for value in row["detections"]:
                            detection = Detection(**value)
                            if (detection.camera_id, detection.frame_index, detection.t_capture_monotonic_ns) != (
                                identity["camera_id"],
                                int(index),
                                int(timestamp),
                            ):
                                raise ValueError("Cached candidate identity mismatch")
                            if not all(
                                math.isfinite(v)
                                for v in (detection.u, detection.v, detection.radius_px, detection.confidence)
                            ):
                                raise ValueError("Nonfinite cached candidate")
                    self.rows = saved["rows"]
                    self.reused = True
            except (OSError, ValueError, KeyError, TypeError):
                logger.warning("Invalid detector cache; replaying source: %s", self.path.name, exc_info=True)

    def detect(self, frame):
        key = f"{frame.capture_epoch}:{frame.frame_index}:{frame.t_capture_monotonic_ns}"
        self.offered += 1
        if self.reused:
            if key not in self.rows:
                raise ValueError("Cached detector input identity mismatch")
            row = self.rows[key]
            values = [Detection(**value) for value in row["detections"]]
        else:
            started = perf_counter()
            values = self.detector.detect(frame)
            elapsed = (perf_counter() - started) * 1000
            self.rows[key] = {"detections": [asdict(v) for v in values], "milliseconds": elapsed}
            row = self.rows[key]
        self.times.append(row["milliseconds"])
        if self.covariance is not None:
            values = [replace(v, pixel_covariance_px2=self.covariance) for v in values]
        return values

    def commit(self):
        if not self.reused and len(self.rows) == self.expected_frames:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(
                self.path,
                json.dumps(
                    {
                        **research_metadata("detector_cache.v1"),
                        "cache_key": self.key,
                        "complete": True,
                        "rows": self.rows,
                    },
                    allow_nan=False,
                ),
            )

    def close(self):
        close = getattr(self.detector, "close", None)
        if close:
            close()
