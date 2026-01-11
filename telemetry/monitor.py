"""Telemetry tracking for latency and capture health."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List


@dataclass
class LatencyStats:
    p50_ms: float
    p95_ms: float
    max_ms: float


@dataclass
class TelemetrySnapshot:
    fps_by_camera: Dict[str, float]
    drop_rate_by_camera: Dict[str, float]
    track_success_rate: float
    latency: LatencyStats


@dataclass
class TelemetryMonitor:
    latency_samples_ms: List[float] = field(default_factory=list)

    def record_latency_ms(self, value: float) -> None:
        self.latency_samples_ms.append(value)

    def summarize(self) -> LatencyStats:
        if not self.latency_samples_ms:
            return LatencyStats(p50_ms=0.0, p95_ms=0.0, max_ms=0.0)
        values = sorted(self.latency_samples_ms)
        max_ms = values[-1]
        p50_ms = values[int(0.5 * (len(values) - 1))]
        p95_ms = values[int(0.95 * (len(values) - 1))]
        return LatencyStats(p50_ms=p50_ms, p95_ms=p95_ms, max_ms=max_ms)
