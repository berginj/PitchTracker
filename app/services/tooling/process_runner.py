"""Cancellation and timeout handling for one-shot tooling subprocesses."""

from __future__ import annotations

from concurrent.futures import CancelledError
from pathlib import Path
import subprocess
from threading import Event
from time import monotonic


def run_cancellable_worker(
    command: list[str], request: str, project_root: Path,
    timeout_seconds: float, cancel_event: Event,
) -> subprocess.CompletedProcess[str]:
    """Poll a worker and reap it before returning, failing, or cancelling."""
    if cancel_event.is_set():
        raise CancelledError("Environment validation cancelled")
    process = subprocess.Popen(
        command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, encoding="utf-8", cwd=str(project_root),
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    deadline = monotonic() + timeout_seconds
    worker_input: str | None = request
    try:
        while True:
            if cancel_event.is_set():
                raise CancelledError("Environment validation cancelled")
            remaining = deadline - monotonic()
            if remaining <= 0:
                raise subprocess.TimeoutExpired(command, timeout_seconds)
            try:
                stdout, stderr = process.communicate(worker_input, timeout=min(0.1, remaining))
                if cancel_event.is_set():
                    raise CancelledError("Environment validation cancelled")
                return subprocess.CompletedProcess(command, process.returncode, stdout, stderr)
            except subprocess.TimeoutExpired:
                # communicate() retains partial output and must receive input only once.
                worker_input = None
    finally:
        if process.poll() is None:
            process.terminate()
        try:
            process.communicate(timeout=1)
        except subprocess.TimeoutExpired:
            process.kill()
            process.communicate()
