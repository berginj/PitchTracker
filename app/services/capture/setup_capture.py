"""Supervised process service for interruptible setup capture."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from typing import Callable, Sequence

from contracts.setup_capture import (
    SetupCaptureFailureCode,
    SetupCaptureRequest,
    SetupCaptureResult,
    SetupCaptureState,
    SetupCaptureTerminal,
)


JobDoneCallback = Callable[["SetupCaptureJob"], None]


class SetupCaptureJob:
    """Handle for one disposable camera-owner process.

    Native camera calls run only in the child.  The monitor thread waits on
    process I/O; operator cancellation terminates the child process and makes
    the monitor return without attempting to kill a Python camera thread.
    """

    def __init__(
        self,
        request: SetupCaptureRequest,
        process: subprocess.Popen[str],
        *,
        cleanup_on_failure: bool = True,
        terminate_grace_seconds: float = 0.35,
    ) -> None:
        self.request = request
        self._process = process
        self._cleanup_on_failure = cleanup_on_failure
        self._terminate_grace_seconds = terminate_grace_seconds
        self._lock = threading.RLock()
        self._done = threading.Event()
        self._cancel_requested = threading.Event()
        self._callbacks: list[JobDoneCallback] = []
        self._state = SetupCaptureState.STARTING
        self._result: SetupCaptureResult | None = None
        self._terminal: SetupCaptureTerminal | None = None
        self._force_killed = False
        self._monitor = threading.Thread(
            target=self._monitor_process,
            name=f"setup-capture-monitor-{request.correlation_id}",
            daemon=True,
        )
        self._monitor.start()

    @property
    def state(self) -> SetupCaptureState:
        with self._lock:
            return self._state

    @property
    def result(self) -> SetupCaptureResult | None:
        with self._lock:
            return self._result

    @property
    def terminal(self) -> SetupCaptureTerminal | None:
        with self._lock:
            return self._terminal

    @property
    def pid(self) -> int:
        return int(self._process.pid)

    @property
    def process_alive(self) -> bool:
        return self._process.poll() is None

    @property
    def done(self) -> bool:
        return self._done.is_set()

    def add_done_callback(self, callback: JobDoneCallback) -> None:
        invoke_now = False
        with self._lock:
            if self._done.is_set():
                invoke_now = True
            else:
                self._callbacks.append(callback)
        if invoke_now:
            callback(self)

    def wait(self, timeout: float | None = None) -> bool:
        return self._done.wait(timeout)

    def cancel(self) -> bool:
        """Request cancellation and immediately terminate the worker.

        Returns ``False`` when the job was already terminal.
        """
        with self._lock:
            if self._terminal is not None:
                return False
            self._cancel_requested.set()
            self._state = SetupCaptureState.CANCELLING
        self._terminate_process(force=False)
        threading.Thread(
            target=self._force_kill_after_grace,
            name=f"setup-capture-reaper-{self.request.correlation_id}",
            daemon=True,
        ).start()
        return True

    def force_kill(self) -> None:
        self._terminate_process(force=True)

    def _force_kill_after_grace(self) -> None:
        if self._done.wait(self._terminate_grace_seconds):
            return
        self._terminate_process(force=True)

    def _terminate_process(self, *, force: bool) -> None:
        try:
            if self._process.poll() is not None:
                return
            if force:
                self._force_killed = True
                self._process.kill()
            else:
                self._process.terminate()
        except (OSError, ProcessLookupError):
            return

    def _monitor_process(self) -> None:
        envelope = json.dumps({"task": "setup_capture", "payload": self.request.to_payload()})
        timeout_seconds = self.request.overall_deadline_ms / 1000.0
        with self._lock:
            if self._state == SetupCaptureState.STARTING:
                self._state = SetupCaptureState.CAPTURING
        try:
            stdout, stderr = self._process.communicate(input=envelope, timeout=timeout_seconds)
        except subprocess.TimeoutExpired:
            self._terminate_process(force=False)
            try:
                stdout, stderr = self._process.communicate(timeout=self._terminate_grace_seconds)
            except subprocess.TimeoutExpired:
                self._terminate_process(force=True)
                stdout, stderr = self._process.communicate()
            self._finish(
                SetupCaptureTerminal(
                    self.request.correlation_id,
                    SetupCaptureState.TIMED_OUT,
                    SetupCaptureFailureCode.DEADLINE_EXCEEDED,
                    f"setup capture exceeded {self.request.overall_deadline_ms}ms deadline",
                    self._force_killed,
                )
            )
            return
        except Exception as exc:  # noqa: BLE001 - normalize monitor failures
            if self._cancel_requested.is_set():
                self._finish(
                    SetupCaptureTerminal(
                        self.request.correlation_id,
                        SetupCaptureState.CANCELLED,
                        SetupCaptureFailureCode.CANCELLED_BY_OPERATOR,
                        "setup capture cancelled by operator",
                        self._force_killed,
                    )
                )
                return
            self._finish(
                SetupCaptureTerminal(
                    self.request.correlation_id,
                    SetupCaptureState.FAILED,
                    SetupCaptureFailureCode.WORKER_CRASHED,
                    f"setup capture monitor failed: {exc}",
                    self._force_killed,
                )
            )
            return

        if self._cancel_requested.is_set():
            self._finish(
                SetupCaptureTerminal(
                    self.request.correlation_id,
                    SetupCaptureState.CANCELLED,
                    SetupCaptureFailureCode.CANCELLED_BY_OPERATOR,
                    "setup capture cancelled by operator",
                    self._force_killed,
                )
            )
            return
        response = self._parse_response(stdout, stderr)
        if isinstance(response, SetupCaptureTerminal):
            self._finish(response)
            return
        self._finish(
            SetupCaptureTerminal(
                self.request.correlation_id,
                SetupCaptureState.SUCCEEDED,
            ),
            result=response,
        )

    def _parse_response(
        self,
        stdout: str,
        stderr: str,
    ) -> SetupCaptureResult | SetupCaptureTerminal:
        lines = [line for line in stdout.splitlines() if line.strip()]
        if not lines:
            detail = stderr.strip() or f"worker exited with code {self._process.returncode}"
            return self._failure(f"setup capture worker produced no response: {detail}")
        try:
            response = json.loads(lines[-1])
        except json.JSONDecodeError as exc:
            return self._failure(f"setup capture worker returned invalid JSON: {exc}")
        if not response.get("ok", False):
            raw_code = str(response.get("failure_code", SetupCaptureFailureCode.WORKER_CRASHED.value))
            try:
                failure_code = SetupCaptureFailureCode(raw_code)
            except ValueError:
                failure_code = SetupCaptureFailureCode.WORKER_CRASHED
            details = [str(response.get("error", "setup capture failed"))]
            if response.get("stderr"):
                details.append(str(response["stderr"]))
            return SetupCaptureTerminal(
                self.request.correlation_id,
                SetupCaptureState.FAILED,
                failure_code,
                "\n".join(details),
                self._force_killed,
            )
        try:
            result = SetupCaptureResult.from_payload(dict(response["result"]))
            self._validate_result(result)
            return result
        except Exception as exc:  # noqa: BLE001 - reject malformed worker data
            return self._failure(f"invalid setup capture result: {exc}", SetupCaptureFailureCode.INVALID_RESULT)

    def _validate_result(self, result: SetupCaptureResult) -> None:
        if result.correlation_id != self.request.correlation_id:
            raise ValueError("correlation ID mismatch")
        if result.purpose != self.request.purpose:
            raise ValueError("capture purpose mismatch")
        if result.assignment_generation != self.request.assignment_generation:
            raise ValueError("camera assignment generation mismatch")
        if self.request.config_sha256 and result.config_sha256 != self.request.config_sha256:
            raise ValueError("configuration digest mismatch")
        if not result.left_frames or not result.right_frames:
            raise ValueError("both cameras must return at least one frame")
        if result.requested_frames_per_camera != self.request.requested_frames_per_camera:
            raise ValueError("requested frame count mismatch")
        if len(result.left_frames) > result.requested_frames_per_camera:
            raise ValueError("left frame count exceeds request")
        if len(result.right_frames) > result.requested_frames_per_camera:
            raise ValueError("right frame count exceeds request")
        if result.artifact_dir is None or self.request.artifact_dir is None:
            raise ValueError("worker did not return its artifact directory")
        expected = self.request.artifact_dir.resolve()
        if result.artifact_dir.resolve() != expected:
            raise ValueError("worker artifact directory mismatch")
        for record in (*result.left_frames, *result.right_frames):
            if record.image_path is not None and expected not in record.image_path.resolve().parents:
                raise ValueError("frame artifact escaped the assigned job directory")

    def _failure(
        self,
        message: str,
        code: SetupCaptureFailureCode = SetupCaptureFailureCode.WORKER_CRASHED,
    ) -> SetupCaptureTerminal:
        return SetupCaptureTerminal(
            self.request.correlation_id,
            SetupCaptureState.FAILED,
            code,
            message,
            self._force_killed,
        )

    def _finish(
        self,
        terminal: SetupCaptureTerminal,
        *,
        result: SetupCaptureResult | None = None,
    ) -> None:
        callbacks: list[JobDoneCallback]
        with self._lock:
            if self._terminal is not None:
                return
            self._terminal = terminal
            self._state = terminal.state
            self._result = result
            callbacks = list(self._callbacks)
            self._callbacks.clear()
            self._done.set()
        if self._cleanup_on_failure and terminal.state != SetupCaptureState.SUCCEEDED:
            self.cleanup_artifacts()
        for callback in callbacks:
            try:
                callback(self)
            except Exception:
                # Completion observers must not alter job terminal state.
                continue

    def cleanup_artifacts(self) -> None:
        artifact_dir = self.request.artifact_dir
        if artifact_dir is None:
            return
        try:
            shutil.rmtree(artifact_dir.resolve(), ignore_errors=True)
        except OSError:
            return


class SupervisedSetupCaptureService:
    """Launch interruptible, one-shot setup capture workers."""

    def __init__(
        self,
        *,
        python_executable: str | None = None,
        project_root: Path | None = None,
        artifact_root: Path | None = None,
        worker_command: Sequence[str] | None = None,
    ) -> None:
        self._python_executable = python_executable or sys.executable
        self._project_root = (project_root or Path(__file__).resolve().parents[3]).resolve()
        default_root = Path(tempfile.gettempdir()) / "PitchTracker" / "setup-capture"
        self._artifact_root = (artifact_root or default_root).resolve()
        self._worker_command = tuple(worker_command) if worker_command is not None else None
        self._lock = threading.RLock()
        self._jobs: dict[str, SetupCaptureJob] = {}

    def submit(self, request: SetupCaptureRequest) -> SetupCaptureJob:
        with self._lock:
            existing = self._jobs.get(request.correlation_id)
            if existing is not None and not existing.done:
                raise RuntimeError(f"setup capture job already active: {request.correlation_id}")
            self._artifact_root.mkdir(parents=True, exist_ok=True)
            artifact_dir = self._artifact_root / request.correlation_id
            resolved = artifact_dir.resolve()
            if self._artifact_root not in resolved.parents:
                raise ValueError("setup capture artifact directory escaped configured root")
            if resolved.exists():
                shutil.rmtree(resolved)
            resolved.mkdir(parents=False)
            assigned_request = request.with_artifact_dir(resolved)
            command = list(self._worker_command) if self._worker_command is not None else [
                self._python_executable,
                "-m",
                "app.services.capture.setup_worker_main",
            ]
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                cwd=str(self._project_root),
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            job = SetupCaptureJob(assigned_request, process)
            self._jobs[request.correlation_id] = job
            job.add_done_callback(self._forget_job)
            return job

    def cancel(self, correlation_id: str) -> bool:
        with self._lock:
            job = self._jobs.get(correlation_id)
        return False if job is None else job.cancel()

    def _forget_job(self, job: SetupCaptureJob) -> None:
        with self._lock:
            current = self._jobs.get(job.request.correlation_id)
            if current is job:
                self._jobs.pop(job.request.correlation_id, None)


__all__ = ["SetupCaptureJob", "SupervisedSetupCaptureService"]
