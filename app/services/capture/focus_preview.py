"""Supervised live focus preview with bounded latest-frame handoff and shutdown."""

from __future__ import annotations

import base64
from collections import deque
from dataclasses import replace
import json
from pathlib import Path
import subprocess
import threading
import time
from typing import Any

import cv2
import numpy as np

from app.worker_process import worker_command
from contracts.focus_preview import FOCUS_PREVIEW_SCHEMA, FocusPreviewFrame
from contracts.setup_capture import (
    SetupCaptureFailureCode, SetupCaptureRequest, SetupCaptureState, SetupCaptureTerminal,
)
from contracts.timing import TimestampEvidence
from log_config.logger import get_logger

logger = get_logger(__name__)


class FocusPreviewService:
    """Own one disposable worker; retain camera admission until it is reaped."""

    def __init__(self, *, project_root: Path | None = None, session_seconds: float = 600) -> None:
        self._root = project_root or Path(__file__).resolve().parents[3]
        self._session_seconds = session_seconds
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.Lock()
        self._done = threading.Event()
        self._done.set()
        self._latest: dict[str, FocusPreviewFrame] = {}
        self._terminal: SetupCaptureTerminal | None = None
        self._stop_at: float | None = None
        self._ready = False
        self._force_killed = False
        self._received: dict[str, float] = {}
        self._errors: deque[str] = deque(maxlen=30)

    @property
    def done(self) -> bool:
        return self._done.is_set()

    @property
    def terminal(self) -> SetupCaptureTerminal | None:
        with self._lock:
            return self._terminal

    def latest(self) -> dict[str, FocusPreviewFrame]:
        """Return at most one frame per side; consumers never queue stale images."""
        with self._lock:
            return dict(self._latest)

    def diagnostics(self) -> tuple[str, ...]:
        """Return bounded local worker messages for failure diagnosis."""
        with self._lock:
            return tuple(self._errors)

    def start(self, request: SetupCaptureRequest) -> None:
        """A service instance owns one process; construct another to restart."""
        if self._process is not None:
            raise RuntimeError("Create a new focus preview service before restarting")
        self._done.clear()
        self._terminal = None
        self._latest = {}
        self._received = {}
        self._ready = False
        self._stop_at = None
        self._errors.clear()
        try:
            self._process = subprocess.Popen(
                worker_command("focus_preview"), cwd=self._root, stdin=subprocess.PIPE,
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding="utf-8",
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            assert self._process.stdin is not None
            self._process.stdin.write(json.dumps({"schema_version": FOCUS_PREVIEW_SCHEMA,
                                                 "request": request.to_payload()}) + "\n")
            self._process.stdin.flush()
        except Exception:
            if self._process is not None:
                self._process.kill()
                self._process.wait(timeout=3)
            self._done.set()
            raise
        threading.Thread(target=self._drain_errors, daemon=True).start()
        threading.Thread(target=self._read, args=(request,), daemon=True).start()
        threading.Thread(target=self._watch, args=(request,), daemon=True).start()
        logger.info("Focus preview started correlation={} worker={}", request.correlation_id, self._process.pid)

    def stop(self) -> None:
        """Request graceful stop; a watchdog terminates a stalled native worker."""
        process = self._process
        if self.done or process is None or self._stop_at is not None:
            return
        self._stop_at = time.monotonic()
        logger.info("Stopping focus preview worker={}", process.pid)
        try:
            if process.stdin:
                process.stdin.close()
        except OSError:
            logger.warning("Focus worker input closed during stop")

    def _drain_errors(self) -> None:
        process = self._process
        assert process is not None and process.stderr is not None
        for line in process.stderr:
            with self._lock:
                self._errors.append(line[-1000:].rstrip())

    def _read(self, request: SetupCaptureRequest) -> None:
        process = self._process
        assert process is not None and process.stdout is not None
        try:
            while line := process.stdout.readline(4_000_000):
                if not line.endswith("\n"):
                    raise ValueError("Oversized focus preview message")
                self._accept(json.loads(line), request)
            process.wait(timeout=3)
        except Exception as exc:  # protocol/worker isolation; never promote bad frames
            logger.exception("Focus preview protocol failed")
            self._fail(request, str(exc), SetupCaptureFailureCode.INVALID_RESULT)
            self._force_killed = True
            process.kill()
            process.wait(timeout=3)
        finally:
            with self._lock:
                if self._terminal is None:
                    cancelled = self._stop_at is not None
                    self._terminal = SetupCaptureTerminal(
                        request.correlation_id, SetupCaptureState.CANCELLED if cancelled else SetupCaptureState.FAILED,
                        None if cancelled else SetupCaptureFailureCode.WORKER_CRASHED,
                        "Preview stopped" if cancelled else "Focus worker exited; restart preview.",
                        self._force_killed,
                    )
                elif self._force_killed:
                    self._terminal = replace(self._terminal, force_killed=True)
            self._done.set()
            logger.info("Focus preview worker reaped pid={} exit={}", process.pid, process.returncode)

    def _accept(self, payload: dict[str, Any], request: SetupCaptureRequest) -> None:
        if payload.get("schema_version") != FOCUS_PREVIEW_SCHEMA:
            raise ValueError("Unsupported focus preview response schema")
        if payload.get("kind") == "error":
            raise RuntimeError(str(payload.get("message", "Focus capture failed")))
        if payload.get("kind") == "ready":
            with self._lock:
                self._ready = True
                self._received = {side: time.monotonic() for side in ("left", "right")}
            return
        side = payload.get("side")
        if side not in ("left", "right") or payload.get("kind") != "frame":
            raise ValueError("Invalid focus preview message")
        expected = request.left_camera_id if side == "left" else request.right_camera_id
        if payload.get("camera_id") != expected:
            raise ValueError("Focus frame belongs to a different camera")
        encoded = base64.b64decode(payload["jpeg"], validate=True)
        image = cv2.imdecode(np.frombuffer(encoded, dtype=np.uint8), cv2.IMREAD_COLOR)
        if image is None or min(image.shape[:2]) < 1 or max(image.shape[:2]) > 4096:
            raise ValueError("Invalid focus image")
        frame = FocusPreviewFrame(side, expected, int(payload["frame_index"]),
                                  int(payload["t_capture_monotonic_ns"]), image,
                                  TimestampEvidence.from_payload(payload.get("timing")))
        with self._lock:
            self._latest[side] = frame
            self._received[side] = time.monotonic()

    def _fail(self, request: SetupCaptureRequest, message: str, code: SetupCaptureFailureCode) -> None:
        logger.error("Focus preview failed correlation={}: {}", request.correlation_id, message)
        with self._lock:
            if self._terminal is None:
                state = SetupCaptureState.TIMED_OUT if code == SetupCaptureFailureCode.DEADLINE_EXCEEDED else SetupCaptureState.FAILED
                self._terminal = SetupCaptureTerminal(request.correlation_id, state, code, message)

    def _watch(self, request: SetupCaptureRequest) -> None:
        started = time.monotonic()
        process = self._process
        assert process is not None
        while not self._done.wait(0.1):
            now = time.monotonic()
            with self._lock:
                stalled = self._ready and any(now - stamp > 4 for stamp in self._received.values())
                starting = not self._ready and now - started > request.overall_deadline_ms / 1000
            if self._stop_at is None and (stalled or starting or now - started > self._session_seconds):
                self._fail(request, "Focus preview timed out or stopped receiving frames; restart preview.",
                           SetupCaptureFailureCode.DEADLINE_EXCEEDED)
                self.stop()
            if self._stop_at is not None and now - self._stop_at > 2 and process.poll() is None:
                self._force_killed = True
                process.kill()
