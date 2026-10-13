"""Operational profile gates; never issue physical accuracy approval."""

from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import math

from contracts.model_bundle import ModelBundle, file_hash
from contracts.versioning import APP_VERSION

QUALITY_THRESHOLDS = {
    "max_error_ratio": 1.05,
    "max_coverage_loss": 0.02,
    "minimum_improvement": 0.10,
    "min_positive_labels": 30,
    "min_opportunities": 40,
    "min_targets": 12,
}


def configuration_binding(config, bundle, variant):
    payload = asdict(config)
    for section in ("upload", "ui"):
        payload.pop(section, None)
    detector, stereo = variant.split(":")
    payload["stereo"]["association_mode"] = stereo
    payload["detector"].update(
        type="ml",
        model_format="yolo_v11",
        model_path=None,
        qualification_path=None,
        model_input_size=list(bundle.input_size),
        model_conf_threshold=bundle.confidence_threshold,
        model_class_id=bundle.ball_class_id,
    )
    return hashlib.sha256(json.dumps(payload, sort_keys=True, default=str, allow_nan=False).encode()).hexdigest()


def assess_quality(report):
    outputs = []
    rows = report.get("results", [])
    for variant in sorted({row["variant"] for row in rows if row["variant"].startswith("baseballcv")}):
        for ball in ("baseball", "softball"):
            selected = [
                r for r in rows if r["variant"] == variant and r["ball_type"] == ball and r["split"] == "evaluation"
            ]
            reasons, improved = [], False
            if not selected:
                reasons.append("NO_HELD_OUT_DATA")
            for row in selected:
                baseline = next(
                    (
                        r
                        for r in rows
                        if r["session_id"] == row["session_id"] and r["variant"] == "classical_a:greedy_v1"
                    ),
                    None,
                )
                if row["status"] != "COMPLETED" or baseline is None or baseline["status"] != "COMPLETED":
                    reasons.append("VARIANT_OR_BASELINE_UNAVAILABLE")
                    continue
                measured, reference = row["metrics"], baseline["metrics"]
                if measured["positive_labels"] < 30 or measured["opportunities"] < 40:
                    reasons.append("INSUFFICIENT_LABELS_OR_OPPORTUNITIES")
                if measured["target_error_ft"]["count"] < 12 or reference["target_error_ft"]["count"] < 12:
                    reasons.append("SURVEYED_TARGET_EVIDENCE_MISSING")
                if (
                    len(measured.get("surveyed_target_ids", [])) < 12
                    or len(reference.get("surveyed_target_ids", [])) < 12
                ):
                    reasons.append("DISTINCT_SURVEYED_TARGETS_MISSING")
                for name in ("center_error_px", "target_error_ft"):
                    value, old = measured[name]["p95"], reference[name]["p95"]
                    if value is None or old is None:
                        reasons.append("ERROR_TAIL_UNAVAILABLE")
                    elif value > old * 1.05 + 1e-12:
                        reasons.append("MEASUREMENT_ERROR_REGRESSION")
                    elif old > 0 and value <= 0.9 * old:
                        improved = True
                if measured["false_stereo_matches"] > reference["false_stereo_matches"]:
                    reasons.append("FALSE_STEREO_MATCH_REGRESSION")
                if measured["unverified_stereo_matches"]:
                    reasons.append("UNVERIFIED_STEREO_MATCHES")
                if (
                    measured.get("stereo_recall") is None
                    or reference.get("stereo_recall") is None
                    or measured["stereo_recall"] < reference["stereo_recall"] - 0.02
                ):
                    reasons.append("STEREO_COVERAGE_REGRESSION")
                if any(s not in measured.get("strata", {}) for s in row.get("required_strata", [])):
                    reasons.append("REQUIRED_STRATA_MISSING")
                if (
                    measured["recall"] is None
                    or reference["recall"] is None
                    or measured["recall"] < reference["recall"] - 0.02
                ):
                    reasons.append("DETECTION_COVERAGE_REGRESSION")
                offered = max(1, measured["opportunities"])
                if (
                    measured["completed_opportunities"] / offered
                    < reference["completed_opportunities"] / offered - 0.02
                ):
                    reasons.append("PITCH_COVERAGE_REGRESSION")
                for stratum, old in reference.get("strata", {}).items():
                    current = measured.get("strata", {}).get(stratum)
                    if not current or (
                        old["positive"]
                        and current["detected"] / old["positive"] < old["detected"] / old["positive"] - 0.02
                    ):
                        reasons.append("STRATUM_COVERAGE_REGRESSION")
                    if (
                        current
                        and current["center_error_px"]["p95"] is not None
                        and old["center_error_px"]["p95"] is not None
                    ):
                        if current["center_error_px"]["p95"] > old["center_error_px"]["p95"] * 1.05 + 1e-12:
                            reasons.append("STRATUM_ERROR_REGRESSION")
            if not improved:
                reasons.append("NO_MEASUREMENT_TAIL_IMPROVEMENT")
            outputs.append(
                {
                    "variant": variant,
                    "ball_type": ball,
                    "quality_passed": not reasons,
                    "reasons": sorted(set(reasons)),
                    "live_qualified": False,
                    "thresholds": QUALITY_THRESHOLDS,
                    "physical_claim_eligible": False,
                }
            )
    return outputs


def qualify_profile(report_path, timing_path, config, bundle_path, variant):
    from app.services.analysis.comparison_inputs import verify_inputs
    from app.services.analysis.pipeline_comparison import comparison_fingerprint

    report = json.loads(Path(report_path).read_text(encoding="utf-8"))
    timing = json.loads(Path(timing_path).read_text(encoding="utf-8"))
    bundle = ModelBundle.load(Path(bundle_path))
    if report.get("status") != "completed" or report.get("implementation") != comparison_fingerprint():
        raise ValueError("A completed comparison of the current implementation is required")
    verify_inputs(report["inputs"])
    if report.get("model", {}).get("bundle_sha256") != bundle.bundle_sha256:
        raise ValueError("Comparison does not bind this model bundle")
    localization = "refined" if variant.split(":")[0].endswith("refined") else "box"
    if bundle.localization != localization:
        raise ValueError("Bundle localization must match the selected live profile")
    assessment = next(
        (r for r in assess_quality(report) if r["variant"] == variant and r["ball_type"] == config.ball.type), None
    )
    if assessment is None or not assessment["quality_passed"]:
        raise ValueError("Held-out measurement quality gates have not passed")
    binding = configuration_binding(config, bundle, variant)
    from configs.settings import load_config

    scope = [
        r
        for r in report["results"]
        if r["variant"] == variant and r["ball_type"] == config.ball.type and r["split"] == "evaluation"
    ]
    if any(row.get("localization_override") for row in scope):
        raise ValueError(
            "Import ML localization covariance into the model bundle and rerun evaluation before live qualification"
        )
    if any(configuration_binding(load_config(Path(r["config_path"])), bundle, variant) != binding for r in scope):
        raise ValueError("Held-out sessions do not match the selected rig configuration")
    geometry = timing.get("rig_binding")
    if not geometry or any(r.get("rig_binding") != geometry for r in scope):
        raise ValueError("Held-out sessions and sustained run do not bind the same actual rig geometry")
    if timing.get("schema_version") != "detector_sustained_run.v1" or timing.get("configuration_binding") != binding:
        raise ValueError("Sustained run does not bind this configuration")
    if timing.get("implementation") != report["implementation"] or timing.get("bundle_sha256") != bundle.bundle_sha256:
        raise ValueError("Sustained run implementation/model changed")
    if timing.get("recording_enabled") is not True or timing.get("duration_seconds", 0) < 900:
        raise ValueError("Fifteen minutes with recording enabled is required")
    if timing.get("source_kind") != "operator_capture":
        raise ValueError("Actual operator-directed capture qualification is required")
    timestamp_hashes = validate_timing_journal(timing)
    for camera in timing.get("cameras", []):
        offered, processed, p95 = camera["offered"], camera["processed"], camera["roundtrip_p95_ms"]
        if offered < config.camera.fps * 900 * 0.99 or processed / max(1, offered) < 0.99:
            raise ValueError("Sustained run lost too many detection opportunities")
        if p95 is None or not math.isfinite(p95) or p95 > 1000 / config.camera.fps:
            raise ValueError("Detector latency exceeds the selected frame period")
        pipeline = camera.get("pipeline_p95_ms")
        if pipeline is None or not math.isfinite(pipeline) or pipeline > 1000 / config.camera.fps:
            raise ValueError("Shadow pipeline latency exceeds the selected frame period")
    if len(timing.get("cameras", [])) != 2:
        raise ValueError("Both cameras must be qualified")
    return {
        "schema_version": "detector_qualification.v1",
        "app_version": APP_VERSION,
        "created_utc": timing["created_utc"],
        "variant": variant,
        "ball_type": config.ball.type,
        "configuration_binding": binding,
        "rig_binding": geometry,
        "bundle_sha256": bundle.bundle_sha256,
        "implementation": report["implementation"],
        "report_path": str(Path(report_path).resolve()),
        "report_sha256": file_hash(Path(report_path)),
        "timing_path": str(Path(timing_path).resolve()),
        "timing_sha256": file_hash(Path(timing_path)),
        "source_timestamp_sha256": timestamp_hashes,
        "operationally_qualified": True,
        "physical_claim_eligible": False,
    }


def validate_timing_journal(timing):
    import csv
    from app.services.analysis.comparison_metrics import distribution

    journal = Path(timing["frame_outcomes_path"])
    if file_hash(journal) != timing["frame_outcomes_sha256"]:
        raise ValueError("Detector timing journal changed")
    rows = [json.loads(line) for line in journal.read_text(encoding="utf-8").splitlines()]
    identities = [(r["camera_id"], r["capture_epoch"], r["frame_index"], r["timestamp_ns"]) for r in rows]
    if len(identities) != len(set(identities)):
        raise ValueError("Timing opportunities were counted more than once")
    recorded = set()
    timestamp_hashes = {}
    for side in ("left", "right"):
        timestamps = Path(timing["source_session"]) / f"session_{side}_timestamps.csv"
        timestamp_hashes[str(timestamps.resolve())] = file_hash(timestamps)
        with timestamps.open(newline="", encoding="utf-8") as stream:
            for row in csv.DictReader(stream):
                if row.get("write_status") == "accepted":
                    recorded.add(
                        (
                            row["camera_id"],
                            row["capture_epoch"],
                            int(row["frame_index"]),
                            int(row["t_capture_monotonic_ns"]),
                        )
                    )
    if any(identity not in recorded for identity in identities):
        raise ValueError("Trial includes frames without recorded video mappings")
    for camera in timing["cameras"]:
        values = [r for r in rows if r["camera_id"] == camera["camera_id"]]
        processed = [r for r in values if r["status"] == "PROCESSED"]
        if len(values) != camera["offered"] or len(processed) != camera["processed"]:
            raise ValueError("Timing summary does not conserve frame opportunities")
        actual = distribution([r["roundtrip_ms"] for r in processed])["p95"]
        if actual != camera["roundtrip_p95_ms"]:
            raise ValueError("Timing summary does not match the measured journal")
        pipeline = distribution([r["pipeline_ms"] for r in processed])["p95"]
        if pipeline != camera["pipeline_p95_ms"]:
            raise ValueError("Pipeline timing summary does not match the measured journal")
    return timestamp_hashes


def admit_live_profile(config):
    if config.detector.model_format != "yolo_v11" or config.detector.type != "ml":
        if config.stereo.association_mode == "global_v3":
            raise ValueError(
                "Experimental global_v3 is comparison-only until a complete detector/stereo profile qualifies"
            )
        return
    if not config.detector.model_path or not config.detector.qualification_path:
        raise ValueError(
            "Experimental detector requires a model bundle and live qualification receipt; use Review comparisons first"
        )
    path = Path(config.detector.qualification_path)
    saved = json.loads(path.read_text(encoding="utf-8"))
    if saved.get("schema_version") != "detector_qualification.v1" or not saved.get("operationally_qualified"):
        raise ValueError("Experimental detector qualification is unavailable")
    if saved["variant"].split(":")[1] != config.stereo.association_mode or saved["ball_type"] != config.ball.type:
        raise ValueError("Selected detector/stereo/ball profile differs from qualification")
    if (
        file_hash(Path(saved["report_path"])) != saved["report_sha256"]
        or file_hash(Path(saved["timing_path"])) != saved["timing_sha256"]
    ):
        raise ValueError("Qualification evidence changed")
    regenerated = qualify_profile(
        saved["report_path"], saved["timing_path"], config, config.detector.model_path, saved["variant"]
    )
    if regenerated != saved:
        raise ValueError("Qualification identity changed; rerun qualification")
