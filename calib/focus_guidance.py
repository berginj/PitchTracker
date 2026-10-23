"""Relative manual-lens guidance, conditioned on a selected stationary target."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import time
from typing import Literal

import cv2
import numpy as np

from detect.utils import compute_focus_score

TurnDirection = Literal["clockwise", "counterclockwise"]


@dataclass(frozen=True)
class FocusAdvice:
    """Relative feedback only; neither readiness nor physical accuracy approval."""

    message: str
    score: float | None = None
    best: float | None = None
    change_percent: float | None = None
    tone: str = "info"


class FocusGuide:
    """Smooth target sharpness and compare a direction explicitly supplied by the operator."""

    def __init__(self) -> None:
        self.target: tuple[float, float] | None = None
        self._scores: deque[float] = deque(maxlen=7)
        self._best = 0.0
        self._baseline: float | None = None
        self._direction: TurnDirection | None = None
        self._turn_time = 0.0
        self.advice = FocusAdvice("Double-click the printed board to choose the focus target.")

    def select_target(self, x: float, y: float) -> None:
        """Store normalized coordinates and discard comparisons from another scene."""
        if not (0 <= x <= 1 and 0 <= y <= 1):
            raise ValueError("Focus target must be inside the image")
        self.target = (x, y)
        self.invalidate("Hold still while the target sharpness settles…")

    def invalidate(self, message: str) -> None:
        """Discard comparisons when the source or lighting stops being usable."""
        self._scores.clear()
        self._best = 0.0
        self._baseline = None
        self._direction = None
        self._turn_time = 0.0
        self.advice = FocusAdvice(message)

    def begin_turn(self, direction: TurnDirection, *, now: float | None = None) -> bool:
        """Record the stationary baseline before the operator turns the ring."""
        if direction not in ("clockwise", "counterclockwise"):
            raise ValueError("Unknown lens turn direction")
        if self.advice.score is None or len(self._scores) < 5:
            return False
        self._baseline = self.advice.score
        self._direction = direction
        self._turn_time = time.monotonic() if now is None else now
        self._best = self._baseline
        self.advice = FocusAdvice(f"Turn slightly {direction}, then hold still for a second.",
                                  self._baseline, self._best)
        return True

    def observe(self, image: np.ndarray, *, now: float | None = None) -> FocusAdvice:
        """Measure only the selected patch, rejecting washed-out or dark targets."""
        if self.target is None:
            return self.advice
        height, width = image.shape[:2]
        x, y = int(self.target[0] * (width - 1)), int(self.target[1] * (height - 1))
        patch = image[max(0, y - 64):min(height, y + 65), max(0, x - 64):min(width, x + 65)]
        gray = cv2.cvtColor(patch, cv2.COLOR_BGR2GRAY) if patch.ndim == 3 else patch
        if float(np.mean(gray >= 250)) > 0.6 or float(np.mean(gray)) < 8:
            bright = float(np.mean(gray)) >= 8
            message = ("Target is washed out — shade the board or reduce exposure." if bright else
                       "Target is too dark — add light or check the selected area.")
            self.invalidate(message)
            self.advice = FocusAdvice(message, tone="warning")
            return self.advice
        self._scores.append(compute_focus_score(patch))
        score = float(np.median(self._scores))
        self._best = max(self._best, score)
        current_time = time.monotonic() if now is None else now
        message, tone = self._message(score, current_time)
        change = None if self._baseline is None else 100 * (score - self._baseline) / max(self._baseline, 1)
        self.advice = FocusAdvice(message, score, self._best, change, tone)
        return self.advice

    def _message(self, score: float, now: float) -> tuple[str, str]:
        if len(self._scores) < 5:
            return "Hold still while the target sharpness settles…", "info"
        if self._baseline is None or self._direction is None:
            return "Choose Test clockwise or Test counterclockwise, then make one small turn.", "info"
        if now - self._turn_time < 1:
            return "Make a small turn, then hold still for a second…", "info"
        opposite = "counterclockwise" if self._direction == "clockwise" else "clockwise"
        if score < self._baseline * 0.92 or (self._best > self._baseline * 1.08 and score < self._best * 0.90):
            return f"Softer — reverse {opposite} toward the sharper position.", "warning"
        if score > self._baseline * 1.08:
            return f"Sharper after {self._direction}. Hold here, or try a smaller turn that way.", "success"
        return "No clear change. Try a tiny turn and hold; keep the board and exposure fixed.", "info"
