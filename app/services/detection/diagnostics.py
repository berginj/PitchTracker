"""Detection rate and quality diagnostics."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:
    from app.services.detection.implementation import DetectionServiceImpl


def detection_stats(service: DetectionServiceImpl) -> Dict[str, Optional[float]]:
    with service._lock:
        if not service._running or service._detection_start_time == 0:
            return _zero_detection_stats()
        elapsed = max(0.001, time.time() - service._detection_start_time)
        return {
            "detections_per_sec": service._detection_count / elapsed,
            "observations_per_sec": service._observation_count / elapsed,
            "avg_detection_ms": 0.0,
            "stereo_detection_utilization": (
                min(1.0, (2.0 * service._observation_count) / service._detection_count)
                if service._detection_count > 0
                else None
            ),
        }


def quality_diagnostics(service: DetectionServiceImpl) -> dict:
    detection = detection_stats(service)
    with service._lock:
        processor = service._processor
        thread_pool = service._thread_pool
    sync = processor.get_sync_stats() if processor is not None else {}
    processing = thread_pool.get_runtime_stats() if thread_pool is not None else empty_pool_stats()
    opportunities = sum(processing[name]["queue_attempts"] for name in ("left", "right"))
    lost = (
        sum(processing[name]["queue_drops"] + processing[name]["failures"] for name in ("left", "right"))
        + processing["results"]["queue_drops"]
        + processing["results"]["failures"]
    )
    loss = {
        "numerator": lost,
        "denominator": opportunities,
        "value": min(1.0, lost / opportunities) if opportunities > 0 else None,
    }
    detection["detection_loss_rate"] = loss["value"]
    with service._tracklet_lock:
        detection["tracklet_start_rate"] = (
            service._tracklet_starts / service._tracklet_updates if service._tracklet_updates > 0 else None
        )
    with service._lock:
        pair_count = service._pair_count
        rejection_counts = dict(service._pair_rejection_counts)
        pairing_frame_count = service._pairing_frame_count
        unmatched_counts = dict(service._pairing_unmatched_counts)
        drift = service._last_drift_status
    return {
        "detection": detection,
        "processing": processing,
        "detection_loss": loss,
        "sync": sync,
        "drift": None if drift is None else drift.__dict__.copy(),
        "pair_outcomes": _pair_outcomes(pair_count, rejection_counts),
        "pairing_frame_outcomes": _pairing_frame_outcomes(pairing_frame_count, unmatched_counts),
    }


def _zero_detection_stats() -> Dict[str, Optional[float]]:
    return {
        "detections_per_sec": 0.0,
        "observations_per_sec": 0.0,
        "avg_detection_ms": 0.0,
        "stereo_detection_utilization": None,
    }


def _pair_outcomes(pair_count: int, counts: dict) -> dict:
    reasons = {
        "PAIR_SKEW_OUT_OF_TOLERANCE",
        "NO_CANDIDATES",
        "NO_VALID_STEREO_ASSOCIATION",
        *counts,
    }
    return {
        "denominator": pair_count,
        "rejection_counts": counts,
        "rejection_rates": {
            reason: counts.get(reason, 0) / pair_count if pair_count > 0 else None
            for reason in sorted(reasons)
        },
    }


def _pairing_frame_outcomes(frame_count: int, counts: dict) -> dict:
    return {
        "denominator": frame_count,
        "unmatched_counts": counts,
        "unmatched_rates": {
            reason: counts.get(reason, 0) / frame_count if frame_count > 0 else None
            for reason in sorted(counts)
        },
        "total_unmatched_rate": sum(counts.values()) / frame_count if frame_count > 0 else None,
    }


def empty_pool_stats() -> dict:
    payload = {
        name: {
            "attempts": 0,
            "failures": 0,
            "queue_attempts": 0,
            "queue_drops": 0,
            "failure_rate": {"numerator": 0, "denominator": 0, "value": None},
            "queue_drop_rate": {"numerator": 0, "denominator": 0, "value": None},
        }
        for name in ("left", "right", "results")
    }
    payload["frame_conservation"] = {
        "offered": 0,
        "terminal": 0,
        "outstanding": 0,
        "balanced": True,
        "terminal_outcomes": {},
    }
    return payload
