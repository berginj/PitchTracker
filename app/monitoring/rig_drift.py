"""Rolling rig-drift monitoring with hysteresis and no auto-mutation."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class DriftStatus:
    state: str
    metric_name: str
    rolling_value: float
    warn_threshold: float
    fail_threshold: float
    sample_count: int
    recommendation: str


class RigDriftMonitor:
    def __init__(
        self,
        metric_name: str,
        *,
        warn_threshold: float,
        fail_threshold: float,
        recovery_threshold: float,
        window_size: int = 30,
        required_bad_windows: int = 3,
    ) -> None:
        if not 0 <= recovery_threshold <= warn_threshold <= fail_threshold:
            raise ValueError("expected recovery <= warn <= fail thresholds")
        if window_size <= 0:
            raise ValueError("window_size must be positive")
        if required_bad_windows <= 0:
            raise ValueError("required_bad_windows must be positive")
        self.metric_name = metric_name
        self.warn_threshold = warn_threshold
        self.fail_threshold = fail_threshold
        self.recovery_threshold = recovery_threshold
        self._samples: deque[float] = deque(maxlen=window_size)
        self._required_bad_windows = required_bad_windows
        self._bad_windows = 0
        self._state = "PASS"

    def update(self, value: float) -> DriftStatus:
        numeric = float(value)
        if not isfinite(numeric) or numeric < 0:
            raise ValueError(f"{self.metric_name} must be finite and non-negative")
        self._samples.append(numeric)
        rolling = sum(self._samples) / len(self._samples)
        candidate = "FAIL" if rolling > self.fail_threshold else "WARN" if rolling > self.warn_threshold else "PASS"
        if candidate == "PASS":
            self._bad_windows = 0
            if rolling <= self.recovery_threshold:
                self._state = "PASS"
        else:
            self._bad_windows += 1
            if self._bad_windows >= self._required_bad_windows:
                if self._state != "FAIL" or candidate == "FAIL":
                    self._state = candidate
        recommendation = ""
        if self._state == "WARN":
            recommendation = "Inspect mounting and rerun the relevant setup check."
        elif self._state == "FAIL":
            recommendation = "Stop measurement mode and revalidate the rig."
        return DriftStatus(
            self._state,
            self.metric_name,
            rolling,
            self.warn_threshold,
            self.fail_threshold,
            len(self._samples),
            recommendation,
        )


__all__ = ["DriftStatus", "RigDriftMonitor"]
