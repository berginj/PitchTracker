"""Supervise the entire experiment, including blocked codecs and model workers."""

import json
import logging
from pathlib import Path
import queue
import subprocess
from threading import Thread
from time import monotonic

import psutil

from app.pipeline.recording.evidence_package import _atomic_write_text
from app.services.analysis.process_cleanup import terminate_worker
from app.services.analysis.research_priority import capture_active
from app.worker_process import worker_command
from contracts.pipeline_comparison import PipelineComparisonProgress, PipelineComparisonResult
from contracts.research_artifacts import research_metadata

logger = logging.getLogger(__name__)


def supervise_comparison(request, cancel, progress):
    from app.services.analysis.comparison_inputs import load_dataset

    # Keep multi-gigabyte video hashing inside the killable worker. The parent
    # checks local paths/containment before it can write a cancelled report.
    load_dataset(request.dataset_path, request.output_dir, hash_inputs=False)
    existing = request.output_dir / "reports" / f"{request.job_id}.json"
    if existing.is_file() and json.loads(existing.read_text(encoding="utf-8")).get("request") != request.to_payload():
        raise ValueError("Comparison job identity belongs to a different request")
    while capture_active():
        if cancel.wait(0.05):
            return interrupted_report(request, "cancelled")
    if cancel.is_set():
        return interrupted_report(request, "cancelled")
    process = subprocess.Popen(
        worker_command("pipeline_comparison"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    stdin, stdout, stderr = process.stdin, process.stdout, process.stderr
    messages: queue.Queue = queue.Queue()

    def read():
        for line in stdout:
            messages.put(line)
        messages.put(None)

    def errors():
        for line in stderr:
            logger.debug("Comparison worker: %s", line.rstrip()[:1000])

    def write():
        try:
            stdin.write(json.dumps(request.to_payload(), allow_nan=False) + "\n")
            stdin.flush()
        except (OSError, ValueError):
            messages.put(None)

    readers = [Thread(target=read, daemon=True), Thread(target=errors, daemon=True), Thread(target=write, daemon=True)]
    suspended: list[psutil.Process] = []
    active, previous = 0.0, monotonic()
    try:
        for thread in readers:
            thread.start()
        while True:
            if cancel.is_set():
                terminate_worker(process)
                return interrupted_report(request, "cancelled")
            now = monotonic()
            if not suspended:
                active += now - previous
            previous = now
            if active > 3600:
                terminate_worker(process)
                return interrupted_report(request, "failed", "Comparison active deadline exceeded")
            paused = capture_active()
            if paused and not suspended:
                try:
                    owned = psutil.Process(process.pid)
                    # Suspend the owner first, then descendants: it cannot spawn
                    # another model worker while the owned tree is paused.
                    owned.suspend()
                    suspended = [owned]
                    for child in owned.children(recursive=True):
                        child.suspend()
                        suspended.append(child)
                except psutil.NoSuchProcess:
                    pass
                if progress:
                    progress(PipelineComparisonProgress(request.job_id, 0, 0, "paused_for_capture"))
            elif not paused and suspended:
                for owned in reversed(suspended):
                    try:
                        owned.resume()
                    except psutil.NoSuchProcess:
                        pass
                suspended = []
            if paused:
                cancel.wait(0.05)
                continue
            try:
                line = messages.get(timeout=0.05)
            except queue.Empty:
                continue
            if line is None:
                terminate_worker(process)
                return interrupted_report(request, "failed", "Comparison worker exited without a result")
            response = json.loads(line)
            if response["message_type"] == "progress":
                event = PipelineComparisonProgress(**response["payload"])
                if event.job_id != request.job_id:
                    raise ValueError("Comparison progress identity mismatch")
                if progress:
                    progress(event)
            elif response["message_type"] == "result":
                expected = request.output_dir.resolve() / "reports" / f"{request.job_id}.json"
                if response["job_id"] != request.job_id or Path(response["report_path"]).resolve() != expected:
                    raise ValueError("Comparison result identity mismatch")
                return PipelineComparisonResult(json.loads(expected.read_text(encoding="utf-8")), expected)
            else:
                terminate_worker(process)
                return interrupted_report(request, "failed", response.get("error", "Invalid worker response"))
    finally:
        for owned in reversed(suspended):
            try:
                owned.resume()
            except psutil.NoSuchProcess:
                pass
        terminate_worker(process)
        for thread in readers:
            thread.join(timeout=1)
        for stream in (stdin, stdout, stderr):
            stream.close()


def interrupted_report(request, status, reason=None):
    path = request.output_dir / "reports" / f"{request.job_id}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    report = (
        json.loads(path.read_text(encoding="utf-8"))
        if path.is_file()
        else {
            **research_metadata("pipeline_comparison.v1"),
            "job_id": request.job_id,
            "request": request.to_payload(),
            "results": [],
            "monocular_results": [],
            "physical_claim_eligible": False,
            "live_qualified": False,
        }
    )
    report.update(status=status, error=reason)
    _atomic_write_text(path, json.dumps(report, allow_nan=False))
    return PipelineComparisonResult(report, path)
