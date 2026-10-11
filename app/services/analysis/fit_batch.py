"""Bounded local research fitting with content-addressed, resumable results."""

from concurrent.futures import CancelledError, FIRST_COMPLETED, Future, ThreadPoolExecutor, wait
import hashlib
import json
from dataclasses import replace
import logging
import os
from pathlib import Path
import platform
import sys
import sysconfig
from threading import Event
from time import monotonic
from typing import Any

from app.pipeline.recording.evidence_package import _atomic_write_text
from app.services.analysis.batch_inputs import apply_overrides, digest, recorded_requests
from app.services.analysis.fit_worker import FitWorkerPool
from app.services.analysis.research_priority import capture_active
from contracts.fit_jobs import FitBatchProgress, FitBatchRequest, FitBatchResult
from trajectory.native_kernel import native_module
from trajectory.serialization import decode_result, encode_request, json_payload

logger = logging.getLogger(__name__)


def automatic_workers() -> int:
    import psutil

    return min(8, max(1, (psutil.cpu_count(logical=False) or os.cpu_count() or 2) - 2))


def implementation_fingerprint():
    import scipy
    import numpy
    import trajectory

    module = native_module()
    files = list(Path(trajectory.__file__).parent.glob("*.py"))
    files.append(Path(__file__))
    if module is not None:
        files.append(Path(module.__file__))
    if getattr(sys, "frozen", False):
        files.append(Path(sys.executable))
    if os.environ.get("PITCHTRACKER_NUMERICAL_WORKER"):
        files.append(Path(os.environ["PITCHTRACKER_NUMERICAL_WORKER"]))
    external_capabilities = None
    if os.environ.get("PITCHTRACKER_NUMERICAL_WORKER"):
        from app.services.analysis.fit_worker import PersistentFitWorker

        probe = PersistentFitWorker()
        try:
            probe.warm()
            external_capabilities = probe.capabilities
        finally:
            probe.close()
    device = module.cuda_device() if module is not None and getattr(module, "cuda_available", False) else None
    return {
        "files": {path.name: digest(path) for path in files if path.is_file()},
        "python": platform.python_version(),
        "machine": platform.machine(),
        "process_platform": sysconfig.get_platform(),
        "scipy": scipy.__version__,
        "numpy": numpy.__version__,
        "cuda_device": device,
        "external_worker_capabilities": external_capabilities,
    }


def _identity(request, provenance, fingerprint):
    payload = json.loads(encode_request(request))["payload"]
    payload.pop("correlation_id", None)
    identity = {
        "request": payload,
        "provenance": provenance,
        "implementation": "fit_batch.v1",
        "fingerprint": fingerprint,
    }
    return hashlib.sha256(json.dumps(identity, sort_keys=True, allow_nan=False).encode()).hexdigest()


def run_fit_batch(request: FitBatchRequest, cancel: Event | None = None, progress=None) -> FitBatchResult:
    """All numerical work runs in killable workers; captured evidence stays read-only."""
    cancel = cancel or Event()
    started = monotonic()
    fingerprint = implementation_fingerprint()
    inputs, blockers = [], []
    for session in request.session_dirs:
        try:
            if request.workflow == "videos":
                from app.services.analysis.video_refit import replay_requests

                rows = replay_requests(session, request, cancel)
            else:
                rows = recorded_requests(session)
            count = 0
            for pitch_id, fit, provenance in rows:
                fit = apply_overrides(fit, request.overrides, request.backend)
                inputs.append((str(session.resolve()), pitch_id, fit, provenance))
                count += 1
            if not count:
                blockers.append({"session": str(session), "reason": "No replayable fit requests"})
        except (ValueError, OSError, KeyError, TypeError) as exc:
            blockers.append({"session": str(session), "reason": str(exc)})
    if cancel.is_set():
        raise CancelledError()
    cache = request.output_dir / "results"
    cache.mkdir(parents=True, exist_ok=True)
    reports = request.output_dir / "reports"
    reports.mkdir(exist_ok=True)
    results: list[dict[str, Any]] = []
    report_path = reports / f"{request.job_id}.json"

    def publish(status, pitch_id=None):
        if progress:
            progress(FitBatchProgress(request.job_id, len(results), len(inputs), status, pitch_id))

    def fit_one(item, pool):
        session, pitch_id, fit, provenance = item
        fit = replace(fit, compute_concurrency=len(pool.workers))
        key = _identity(fit, provenance, fingerprint)
        path = cache / f"{key}.json"
        reused = False
        if path.is_file():
            try:
                saved = json.loads(path.read_text(encoding="utf-8"))
                if saved["cache_key"] != key:
                    raise ValueError("Cache identity mismatch")
                result = decode_result(saved["result"])
                reused = not result.diagnostics.failure_codes
            except (ValueError, KeyError, TypeError):
                logger.warning("Invalid derived cache entry; refitting: %s", path)
        if not reused:
            result = pool.fit(fit, cancel)
            saved = {
                "schema_version": "fit_batch_result.v1",
                "cache_key": key,
                "request": json.loads(encode_request(fit)),
                "result": json_payload(result.to_dict()),
                "source_session": session,
                "pitch_id": pitch_id,
                "provenance": provenance,
                "physical_claim_eligible": False,
            }
            _atomic_write_text(path, json.dumps(saved, sort_keys=True, allow_nan=False))
        return {
            "session": session,
            "pitch_id": pitch_id,
            "mode": fit.mode,
            "cache_key": key,
            "artifact": str(path.resolve()),
            "reused": reused,
            "failure_codes": [code.value for code in result.diagnostics.failure_codes],
            "performance": result.diagnostics.performance,
            "provenance": provenance,
        }

    workers = request.workers or automatic_workers()
    status = "completed"
    publish("preparing")
    pool = FitWorkerPool(workers)
    try:
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix="research-fit") as executor:
            pending: dict[Future, str] = {}
            iterator = iter(inputs)
            exhausted = False
            while pending or not exhausted:
                if cancel.is_set():
                    status = "cancelled"
                    pool.close()
                    for future in pending:
                        future.cancel()
                    break
                paused = capture_active()
                while not paused and not exhausted and len(pending) < workers:
                    item = next(iterator, None)
                    if item is None:
                        exhausted = True
                        break
                    pending[executor.submit(fit_one, item, pool)] = item[1]
                if paused and not pending:
                    publish("paused_for_capture")
                    cancel.wait(0.1)
                    continue
                done, _ = wait(pending, timeout=0.1, return_when=FIRST_COMPLETED)
                for future in done:
                    pitch_id = pending.pop(future)
                    try:
                        results.append(future.result())
                    except CancelledError:
                        status = "cancelled"
                        continue
                    publish("fitting", pitch_id)
    finally:
        pool.close()
    report = {
        "schema_version": "fit_batch.v1",
        "job_id": request.job_id,
        "status": status,
        "request": request.to_payload(),
        "total": len(inputs),
        "completed": len(results),
        "workers": workers,
        "elapsed_seconds": monotonic() - started,
        "implementation_fingerprint": fingerprint,
        "results": results,
        "blockers": blockers,
        "physical_claim_eligible": False,
    }
    _atomic_write_text(report_path, json.dumps(report, sort_keys=True, allow_nan=False))
    publish(status)
    return FitBatchResult({**report, "report_path": str(report_path.resolve())})
