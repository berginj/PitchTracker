"""Optional pipeline research with the twelve declared detector/stereo controls."""

from concurrent.futures import CancelledError
from dataclasses import replace
import hashlib
import json
import logging
from pathlib import Path
from threading import Event
from time import monotonic
import platform
import sysconfig
import sys
from typing import Any

import cv2
import numpy as np
import scipy

from app.pipeline.recording.evidence_package import _atomic_write_text
from app.services.analysis.comparison_cache import CachedDetector
from app.services.analysis.comparison_inputs import load_dataset, verify_inputs
from app.services.analysis.comparison_metrics import ComparisonAudit, distribution, summarize_fit
from app.services.analysis.fit_worker import FitWorkerPool
from app.services.analysis.research_priority import capture_active
from app.services.analysis.video_replay import replay
from configs.settings import load_config
from contracts.fit_jobs import FitBatchRequest
from contracts.model_bundle import ModelBundle, file_hash
from contracts.research_artifacts import research_metadata
from contracts.pipeline_comparison import (
    PipelineComparisonRequest,
    PipelineComparisonProgress,
    PipelineComparisonResult,
)
from detect.classical_detector import ClassicalDetector
from detect.config import Mode
from detect.detector import Detector
from detect.supervised import SupervisedONNXDetector

logger = logging.getLogger(__name__)


def comparison_fingerprint():
    from app.services.analysis.comparison_hardware import hardware_identity, native_cpu_identity

    root = Path(__file__).resolve().parents[3]
    files: list[Path] = []
    for directory in ("app", "capture", "calib", "configs", "detect", "stereo", "trajectory", "contracts", "record"):
        files.extend((root / directory).rglob("*.py"))
    files.extend((root / "research").glob("*.py"))
    identities = {str(p.relative_to(root)): file_hash(p) for p in sorted(files)}
    if getattr(sys, "frozen", False):
        for name in ("PitchTracker.exe", "PitchTrackerWorker.exe"):
            binary = Path(sys.executable).parent / name
            if binary.is_file():
                identities[name] = file_hash(binary)
    return {
        "files": identities,
        "hardware_sha256": hardware_identity(),
        "native_cpu_sha256": native_cpu_identity(),
        "python": platform.python_version(),
        "process_platform": sysconfig.get_platform(),
        "opencv": cv2.__version__,
        "opencv_build_sha256": hashlib.sha256(cv2.getBuildInformation().encode()).hexdigest(),
        "numpy": np.__version__,
        "scipy": scipy.__version__,
    }


def execute_pipeline_comparison(request: PipelineComparisonRequest, cancel=None, progress=None):
    cancel = cancel or Event()
    sessions, broadcasts, inputs = load_dataset(request.dataset_path, request.output_dir)
    existing = request.output_dir / "reports" / f"{request.job_id}.json"
    if existing.is_file() and json.loads(existing.read_text(encoding="utf-8")).get("request") != request.to_payload():
        raise ValueError("Comparison job identity belongs to a different request")
    bundle, bundle_error = None, "No model bundle selected"
    if request.bundle_path:
        try:
            bundle = ModelBundle.load(request.bundle_path)
            inputs[str(bundle.manifest_path)] = bundle.bundle_sha256
            inputs[str(bundle.model_path)] = bundle.model_sha256
        except (ValueError, OSError, KeyError, TypeError) as exc:
            bundle_error = str(exc)
    fingerprint = comparison_fingerprint()
    total = len(sessions) * len(request.variants)
    results: list[dict[str, Any]] = []
    request.output_dir.mkdir(parents=True, exist_ok=True)
    destination = request.output_dir / "reports" / f"{request.job_id}.json"
    destination.parent.mkdir(exist_ok=True)
    started = monotonic()
    paused_seconds = 0.0

    def notify(status, variant=None):
        if progress:
            progress(PipelineComparisonProgress(request.job_id, len(results), total, status, variant))

    def check():
        nonlocal paused_seconds
        if cancel.is_set():
            raise CancelledError()
        paused_at = monotonic()
        while capture_active():
            notify("paused_for_capture")
            if cancel.wait(0.1):
                raise CancelledError()
        paused_seconds += monotonic() - paused_at
        if monotonic() - started - paused_seconds > 3600:
            raise ValueError("Comparison exceeded its one-hour deadline")

    report = {
        **research_metadata("pipeline_comparison.v1"),
        "job_id": request.job_id,
        "status": "running",
        "request": request.to_payload(),
        "inputs": inputs,
        "implementation": fingerprint,
        "model": bundle.identity() if bundle else None,
        "results": results,
        "monocular_results": [],
        "physical_claim_eligible": False,
        "live_qualified": False,
    }

    def persist():
        _atomic_write_text(destination, json.dumps(report, sort_keys=True, allow_nan=False))

    notify("preparing")
    pool = FitWorkerPool(1)
    try:
        for session in sessions:
            cfg = load_config(session["paths"]["config"])
            if cfg.ball.type != session["ball_type"]:
                raise ValueError("Dataset ball type does not match session configuration")
            session["transform"] = json.loads(session["paths"]["field_transform"].read_text(encoding="utf-8"))
            session_inputs = {str(p): inputs[str(p)] for p in session["paths"].values()}
            for variant in request.variants:
                check()
                detector_profile, stereo_profile = variant.split(":")
                audit = ComparisonAudit(session)
                accounting: dict[str, Any] = {}
                detectors: list[CachedDetector] = []
                attempts: list[dict[str, Any]] = []
                row = {
                    "session_id": session["id"],
                    "split": session["split"],
                    "ball_type": session["ball_type"],
                    "variant": variant,
                    "status": "COMPLETED",
                    "reason": None,
                    "localization_override": detector_profile.startswith("baseballcv")
                    and detector_profile in session["pixel_covariances"],
                    "camera": {
                        "width": cfg.camera.width,
                        "height": cfg.camera.height,
                        "fps": cfg.camera.fps,
                        "pixfmt": cfg.camera.pixfmt,
                        "color_mode": cfg.camera.color_mode,
                    },
                    "config_path": str(session["paths"]["config"]),
                    "rig_binding": session["rig_binding"],
                }
                row["required_strata"] = session.get(
                    "required_strata", ["nominal", "lighting", "background", "image_edge", "occlusion", "negative"]
                )
                row["source_frames_offered"] = sum(session["counts"].values())
                config = replace(
                    cfg,
                    stereo=replace(cfg.stereo, association_mode=stereo_profile),
                    trajectory=replace(cfg.trajectory, compare_modes=()),
                )
                batch = FitBatchRequest(
                    (session["root"],),
                    request.output_dir,
                    workflow="videos",
                    config_path=session["paths"]["config"],
                    calibration_path=session["paths"]["calibration"],
                    roi_path=session["paths"]["roi"],
                    field_transform_path=session["paths"]["field_transform"],
                )

                def factory(label, camera_id, polygon):
                    detector: Detector
                    if detector_profile.startswith("baseballcv"):
                        if bundle is None:
                            raise ValueError(bundle_error)
                        detector = SupervisedONNXDetector(
                            bundle.manifest_path,
                            localization="refined" if detector_profile.endswith("refined") else "box",
                            deadline_seconds=5,
                            cancel=cancel,
                        )
                    else:
                        from app.pipeline.initialization import PipelineInitializer

                        detector = ClassicalDetector(
                            PipelineInitializer.cv_detector_config(config),
                            Mode.MODE_A if detector_profile.endswith("a") else Mode.MODE_B,
                            {},  # Runtime detects on the full frame; shared processor gates the ROI.
                        )
                    identity = {
                        "source": session_inputs,
                        "profile": detector_profile,
                        "camera_id": camera_id,
                        "model": bundle.identity() if detector_profile.startswith("baseballcv") and bundle else None,
                        "implementation": fingerprint,
                    }
                    wrapped = CachedDetector(
                        detector,
                        request.output_dir / "detector_cache",
                        identity,
                        session["counts"][label],
                        session["pixel_covariances"].get(detector_profile),
                    )
                    detectors.append(wrapped)
                    return wrapped

                try:
                    rows = list(
                        replay(
                            session["root"],
                            batch,
                            check,
                            accounting,
                            config_override=config,
                            detector_factory=factory,
                            frame_sink=audit.frame,
                            association_sink=audit.association,
                        )
                    )
                    for detector in detectors:
                        detector.commit()
                    for pitch_id, fit, provenance in rows:
                        check()
                        fit = replace(
                            fit, compute_backend="cpu", deadline_seconds=config.trajectory.stereo_deadline_seconds
                        )
                        attempts.append(summarize_fit(pitch_id, fit, pool.fit(fit, cancel)))
                    for rejected in accounting.get("rejected_pitches", []):
                        attempts.append({**rejected, "status": "REJECTED"})
                except CancelledError:
                    raise
                except (OSError, ValueError, RuntimeError, KeyError, TypeError) as exc:
                    logger.warning(
                        "Comparison variant unavailable: session=%s variant=%s", session["id"], variant, exc_info=True
                    )
                    row.update(status="UNAVAILABLE", reason=f"{type(exc).__name__}: {exc}")
                finally:
                    for detector in detectors:
                        detector.close()
                key = hashlib.sha256(f"{session['id']}:{variant}:{request.job_id}".encode()).hexdigest()
                artifact = request.output_dir / "variants" / f"{key}.json"
                artifact.parent.mkdir(exist_ok=True)
                _atomic_write_text(
                    artifact,
                    json.dumps(
                        {
                            **research_metadata("pipeline_variant.v1"),
                            "frames": audit.frames,
                            "variant": variant,
                            "session_id": session["id"],
                            "inputs": session_inputs,
                            "implementation": fingerprint,
                            "model": bundle.identity() if bundle else None,
                            "associations": audit.associations,
                            "attempts": attempts,
                            "accounting": accounting,
                            "physical_claim_eligible": False,
                        },
                        allow_nan=False,
                    ),
                )
                row.update(
                    metrics=audit.summary(attempts),
                    artifact=str(artifact),
                    artifact_sha256=file_hash(artifact),
                    accounting=accounting,
                    detector_roundtrip_ms=distribution([t for d in detectors for t in d.times]),
                    cache_reused=bool(detectors and all(d.reused for d in detectors)),
                )
                results.append(row)
                persist()
                notify("comparing", variant)
        if request.monocular_assets:
            from app.services.analysis.monocular_comparison import run_monocular_comparisons

            report["monocular_results"] = run_monocular_comparisons(request, sessions, broadcasts, check, cancel)
        else:
            report["monocular_results"] = [
                {
                    "status": "UNAVAILABLE",
                    "reason": "Select isolated research environment and local model assets",
                    "measurement_basis": "image_zone_at_glove_arrival",
                }
            ]
        verify_inputs(inputs)
        from app.services.analysis.comparison_qualification import assess_quality

        report["quality_assessments"] = assess_quality(report)
        report["status"] = "completed"
    except CancelledError:
        report["status"] = "cancelled"
    except Exception as exc:
        report.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        logger.exception("Pipeline comparison failed")
    finally:
        pool.close()
        report["elapsed_seconds"] = monotonic() - started
        persist()
        notify(report["status"])
    return PipelineComparisonResult(report, destination)


def run_pipeline_comparison(request: PipelineComparisonRequest, cancel=None, progress=None):
    """Public boundary: native decoding and fitting stay in a killable worker."""
    from app.services.analysis.comparison_process import supervise_comparison

    return supervise_comparison(request, cancel or Event(), progress)
