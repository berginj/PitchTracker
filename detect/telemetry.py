from __future__ import annotations

import logging
from dataclasses import dataclass


LOGGER = logging.getLogger("telemetry")


@dataclass(frozen=True)
class TimingRecord:
    camera_id: str
    mode: str
    elapsed_ms: float
    budget_ms: float


def log_timing(camera_id: str, mode: str, elapsed_ms: float, budget_ms: float) -> None:
    record = TimingRecord(
        camera_id=camera_id, mode=mode, elapsed_ms=elapsed_ms, budget_ms=budget_ms
    )
    LOGGER.info(
        "detect.timing camera=%s mode=%s elapsed_ms=%.3f budget_ms=%.3f",
        record.camera_id,
        record.mode,
        record.elapsed_ms,
        record.budget_ms,
    )
    if elapsed_ms > budget_ms:
        LOGGER.warning(
            "detect.timing_budget_exceeded camera=%s mode=%s elapsed_ms=%.3f budget_ms=%.3f",
            record.camera_id,
            record.mode,
            record.elapsed_ms,
            record.budget_ms,
        )
