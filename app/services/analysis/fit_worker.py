"""Persistent, killable trajectory workers with per-request wall-clock budgets."""

from __future__ import annotations

from concurrent.futures import CancelledError
import json
import logging
import os
import queue
import subprocess
from threading import Event, Lock, Thread
from time import monotonic
from uuid import uuid4
from dataclasses import replace
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.analysis.gpu_dispatcher import GPUFitDispatcher

from app.services.analysis.numerical_command import numerical_command
from trajectory.contracts import FailureCode, TrajectoryDiagnostics, TrajectoryFitRequest, TrajectoryFitResult
from trajectory.serialization import decode_result, encode_request

logger = logging.getLogger(__name__)


class Cancellation:
    """Read-only union of caller cancellation and owner shutdown."""

    def __init__(self, *events):
        self.events = events

    def is_set(self):
        return any(event.is_set() for event in self.events)


class PersistentFitWorker:
    def __init__(self, command: list[str] | None = None):
        self.command = command
        self.process: subprocess.Popen | None = None
        self._messages: queue.Queue = queue.Queue()
        self._readers: list[Thread] = []
        self._lock = Lock()
        self.generation = ""
        self.capabilities: dict = {}

    def _receive(self, deadline: float, cancel: Event | Cancellation) -> dict:
        while True:
            if cancel.is_set():
                raise CancelledError("Fit cancelled")
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise TimeoutError("Fit deadline exceeded")
            try:
                value = self._messages.get(timeout=min(0.05, remaining))
            except queue.Empty:
                continue
            if value is None:
                raise RuntimeError("Fit worker exited without a response")
            response = json.loads(value)
            if not isinstance(response, dict):
                raise ValueError("Worker response must be an object")
            return response

    def _read(self, process, output: queue.Queue) -> None:
        try:
            for line in process.stdout:
                output.put(line)
        finally:
            output.put(None)

    def _stderr(self, process) -> None:
        for line in process.stderr:
            logger.debug("Numerical worker: %s", line.rstrip()[:2000])

    def _send(self, envelope: dict) -> Thread:
        """Keep pipe backpressure inside the supervised deadline."""
        process, output = self.process, self._messages
        assert process is not None and process.stdin is not None
        stream = process.stdin
        payload = json.dumps(envelope, allow_nan=False) + "\n"

        def write() -> None:
            try:
                stream.write(payload)
                stream.flush()
            except (OSError, ValueError):
                output.put(None)

        self._readers = [reader for reader in self._readers if reader.is_alive()]
        writer = Thread(target=write, daemon=True)
        self._readers.append(writer)
        writer.start()
        return writer

    @staticmethod
    def _finish_write(writer: Thread, deadline: float) -> None:
        writer.join(timeout=max(0, deadline - monotonic()))
        if writer.is_alive():
            raise TimeoutError("Request write exceeded the fit deadline")

    def _start(self, deadline: float, cancel: Event | Cancellation) -> None:
        if self.process is not None and self.process.poll() is None:
            return
        self._dispose()
        self.generation = uuid4().hex
        self._messages = queue.Queue()
        environment = dict(os.environ)
        for name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS", "NUMEXPR_NUM_THREADS"):
            environment[name] = "1"
        process = subprocess.Popen(
            self.command or numerical_command(),
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            bufsize=1,
            env=environment,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        self.process = process
        self._readers = [
            Thread(target=self._read, args=(process, self._messages), daemon=True),
            Thread(target=self._stderr, args=(process,), daemon=True),
        ]
        for reader in self._readers:
            reader.start()
        ready = self._receive(deadline, cancel)
        if ready.get("message_type") != "ready":
            raise ValueError("Fit worker readiness mismatch")
        self.capabilities = dict(ready.get("capabilities", {}))
        logger.info("Trajectory worker ready: pid=%s generation=%s", process.pid, self.generation)

    def warm(self, timeout: float = 15.0, cancel: Event | None = None) -> None:
        with self._lock:
            try:
                self._start(monotonic() + timeout, cancel or Event())
            except Exception:
                self._dispose()
                raise

    def fit(self, request: TrajectoryFitRequest, cancel: Event | Cancellation | None = None) -> TrajectoryFitResult:
        cancel = cancel or Event()
        started = monotonic()
        deadline = started + request.deadline_seconds
        if not self._lock.acquire(timeout=request.deadline_seconds):
            return self._failure(request, FailureCode.DEADLINE_EXCEEDED, "Worker busy")
        try:
            self._start(deadline, cancel)
            request = replace(request, correlation_id=request.correlation_id or uuid4().hex)
            token = uuid4().hex
            envelope = json.loads(encode_request(request))
            envelope.update(generation=self.generation, request_id=token)
            writer = self._send(envelope)
            response = self._receive(deadline, cancel)
            self._finish_write(writer, deadline)
            if (response.get("correlation_id"), response.get("generation"), response.get("request_id")) != (
                request.correlation_id,
                self.generation,
                token,
            ):
                raise ValueError("Fit worker response identity mismatch")
            if not response.get("ok"):
                raise ValueError(response.get("error", "Fit worker failed"))
            result = decode_result(response["result"])
            if monotonic() > deadline:
                raise TimeoutError("Response decoding exceeded the fit deadline")
            performance = dict(result.diagnostics.performance)
            assert self.process is not None
            performance.update(worker_roundtrip_ms=(monotonic() - started) * 1000, worker_pid=self.process.pid)
            return replace(result, diagnostics=replace(result.diagnostics, performance=performance))
        except CancelledError:
            self._dispose()
            raise
        except TimeoutError:
            self._dispose()
            return self._failure(request, FailureCode.DEADLINE_EXCEEDED, "Worker killed and reaped at deadline")
        except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
            logger.exception("Persistent trajectory worker failed")
            self._dispose()
            return self._failure(request, FailureCode.INVALID_INPUT, str(exc))
        finally:
            self._lock.release()

    @staticmethod
    def _failure(request: TrajectoryFitRequest, code: FailureCode, note: str) -> TrajectoryFitResult:
        return TrajectoryFitResult(
            request.mode, [], None, None, None, 0.0, TrajectoryDiagnostics(failure_codes=[code], notes=[note])
        )

    def fit_batch(self, requests, cancel):
        """One process owns all optimizers and their shared GPU allocation."""
        timeout = min(request.deadline_seconds for request in requests)
        deadline = monotonic() + timeout
        if not self._lock.acquire(timeout=timeout):
            return [self._failure(request, FailureCode.DEADLINE_EXCEEDED, "GPU worker busy") for request in requests]
        try:
            self._start(deadline, cancel)
            token, correlation = uuid4().hex, uuid4().hex
            envelope = {
                "schema_version": "trajectory_batch_worker.v1",
                "correlation_id": correlation,
                "generation": self.generation,
                "request_id": token,
                "requests": [
                    json.loads(encode_request(replace(request, correlation_id=request.correlation_id or uuid4().hex)))
                    for request in requests
                ],
            }
            writer = self._send(envelope)
            response = self._receive(deadline, cancel)
            self._finish_write(writer, deadline)
            if (response.get("correlation_id"), response.get("generation"), response.get("request_id")) != (
                correlation,
                self.generation,
                token,
            ) or not response.get("ok"):
                raise ValueError("GPU batch response identity or status mismatch")
            results = [decode_result(value) for value in response["results"]]
            for result in results:
                result.diagnostics.performance["gpu_environment"] = self.capabilities.get("gpu_environment")
            if len(results) != len(requests):
                raise ValueError("GPU batch response count mismatch")
            if monotonic() > deadline:
                raise TimeoutError("GPU batch response deadline")
            return results
        except CancelledError:
            self._dispose()
            raise
        except TimeoutError:
            self._dispose()
            return [self._failure(request, FailureCode.DEADLINE_EXCEEDED, "GPU batch deadline") for request in requests]
        except (OSError, RuntimeError, ValueError, KeyError, TypeError) as exc:
            logger.exception("GPU batch worker failed")
            self._dispose()
            return [self._failure(request, FailureCode.INVALID_INPUT, str(exc)) for request in requests]
        finally:
            self._lock.release()

    def _dispose(self) -> None:
        process, self.process = self.process, None
        if process is None:
            return
        if process.poll() is None:
            process.terminate()
        try:
            process.wait(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=1)
        for reader in self._readers:
            reader.join(timeout=1)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if pipe is not None:
                try:
                    pipe.close()
                except OSError:
                    logger.debug("Reaped worker pipe failed its final flush", exc_info=True)
        self._readers.clear()
        logger.info("Trajectory worker stopped: pid=%s", process.pid)

    def close(self) -> None:
        with self._lock:
            self._dispose()


class FitWorkerPool:
    """One request per independently supervised worker; bounded admission."""

    def __init__(self, count: int = 1):
        if not 1 <= count <= 16:
            raise ValueError("Worker count must be between 1 and 16")
        self.workers = [PersistentFitWorker() for _ in range(count)]
        self._idle: queue.Queue[PersistentFitWorker] = queue.Queue()
        for worker in self.workers:
            self._idle.put(worker)
        self._closed = Event()
        self._gpu_dispatcher: GPUFitDispatcher | None = None
        self._gpu_lock = Lock()

    def warm(self) -> None:
        for worker in self.workers:
            worker.warm(cancel=self._closed)

    def fit(self, request: TrajectoryFitRequest, cancel: Event | None = None) -> TrajectoryFitResult:
        started = monotonic()
        cancel = cancel or Event()
        if request.mode == "stereo_3d" and request.compute_backend in {"cuda", "auto"}:
            from trajectory.native_kernel import native_module

            module = native_module()
            if (module is not None and getattr(module, "cuda_available", False)) or os.environ.get(
                "PITCHTRACKER_NUMERICAL_WORKER"
            ):
                from app.services.analysis.gpu_dispatcher import GPUFitDispatcher

                # Creating the dispatcher is protected against concurrent callers.
                with self._gpu_lock:
                    if self._gpu_dispatcher is None:
                        self._gpu_dispatcher = GPUFitDispatcher(len(self.workers))
                return self._gpu_dispatcher.fit(request, Cancellation(cancel, self._closed))
        while True:
            if cancel.is_set() or self._closed.is_set():
                raise CancelledError("Fit pool stopped")
            remaining = request.deadline_seconds - (monotonic() - started)
            if remaining <= 0:
                return PersistentFitWorker._failure(request, FailureCode.DEADLINE_EXCEEDED, "Admission deadline")
            try:
                worker = self._idle.get(timeout=min(remaining, 0.05))
                break
            except queue.Empty:
                continue
        try:
            remaining = request.deadline_seconds - (monotonic() - started)
            if remaining <= 0:
                return PersistentFitWorker._failure(request, FailureCode.DEADLINE_EXCEEDED, "Admission deadline")
            return worker.fit(
                replace(request, deadline_seconds=remaining, compute_concurrency=len(self.workers)),
                Cancellation(cancel, self._closed),
            )
        finally:
            self._idle.put(worker)

    def close(self) -> None:
        self._closed.set()
        if self._gpu_dispatcher is not None:
            self._gpu_dispatcher.close()
        for worker in self.workers:
            worker.close()

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        self.close()
