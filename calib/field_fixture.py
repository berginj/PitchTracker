"""Field validation fixture manifest checks."""

from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
from typing import Any


PASS = "PASS"
WARN = "WARN"
FAIL = "FAIL"
SCHEMA_VERSION = "field_fixture.v1"


def validate_field_fixture_manifest(manifest_path: Path) -> dict[str, Any]:
    """Validate a field fixture manifest and any referenced lightweight artifacts."""
    manifest_path = Path(manifest_path)
    root = manifest_path.parent.resolve()
    errors: list[str] = []
    warnings: list[str] = []
    case_results: list[dict[str, Any]] = []
    components: dict[str, dict[str, Any]] = {}

    manifest = _load_json(manifest_path, errors)
    if not isinstance(manifest, dict):
        return _result(FAIL, manifest_path, errors or ["Fixture manifest is not a JSON object."], warnings, case_results, components)

    if manifest.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}.")
    if not manifest.get("fixture_id"):
        errors.append("fixture_id is required.")

    _validate_status_artifact(root, manifest.get("calibration_report"), "calibration_report", "calibration", errors, warnings, components)
    _validate_status_artifact(root, manifest.get("sync_report"), "sync_report", "sync", errors, warnings, components)
    _validate_artifact_path(root, manifest.get("session_manifest"), "session_manifest", errors, warnings)

    cases = manifest.get("cases")
    if not isinstance(cases, list) or not cases:
        errors.append("cases must be a non-empty list.")
    else:
        for index, case in enumerate(cases):
            case_results.append(_validate_case(root, case, index))

    for case in case_results:
        if case["status"] == FAIL:
            errors.extend(f"{case['case_id']}: {item}" for item in case["errors"])
        elif case["status"] == WARN:
            warnings.extend(f"{case['case_id']}: {item}" for item in case["warnings"])

    _summarize_case_component("field_targets", [case for case in case_results if case["component"] == "field_targets"], components)
    _summarize_case_component("pitch_manifests", [case for case in case_results if case["component"] == "pitch_manifests"], components)

    status = FAIL if errors else WARN if warnings else PASS
    result = _result(status, manifest_path, errors, warnings, case_results, components)
    # The v1 fixture is intentionally diagnostic-only.  In particular, older
    # scaffolds copied system outputs into their expected fields.  Preserve the
    # regression status while making that limitation machine-enforced.
    result.update(
        accuracy_claim_eligible=False,
        claim_ready=False,
        claim_blockers=["LEGACY_FIELD_FIXTURE_SCHEMA"],
    )
    return result


def _validate_case(root: Path, case: Any, index: int) -> dict[str, Any]:
    case_errors: list[str] = []
    case_warnings: list[str] = []
    metrics: dict[str, Any] = {}
    case_id = f"case_{index}"
    if not isinstance(case, dict):
        return _case_result(case_id, "unknown", FAIL, ["case must be a JSON object."], [], metrics)

    case_id = str(case.get("case_id") or case_id)
    case_type = str(case.get("type") or "")
    if case_type == "static_target":
        component = "field_targets"
        _validate_static_target_case(case, case_errors, metrics)
    elif case_type == "pitch_manifest":
        component = "pitch_manifests"
        _validate_pitch_manifest_case(root, case, case_errors, case_warnings, metrics)
    else:
        component = "unknown"
        case_errors.append("type must be static_target or pitch_manifest.")

    status = FAIL if case_errors else WARN if case_warnings else PASS
    return _case_result(case_id, component, status, case_errors, case_warnings, metrics)


def _validate_static_target_case(case: dict[str, Any], errors: list[str], metrics: dict[str, Any]) -> None:
    expected = _xyz(case.get("expected_xyz_ft"), "expected_xyz_ft", errors)
    actual = _xyz(case.get("actual_xyz_ft"), "actual_xyz_ft", errors)
    max_error_ft = _positive_number(case.get("max_error_ft"), "max_error_ft", errors)
    if expected is None or actual is None or max_error_ft is None:
        return
    error_ft = _distance(expected, actual)
    metrics["error_ft"] = error_ft
    metrics["max_error_ft"] = max_error_ft
    if error_ft > max_error_ft:
        errors.append(f"static target error {error_ft:.3f} ft exceeds {max_error_ft:.3f} ft.")


def _validate_pitch_manifest_case(
    root: Path,
    case: dict[str, Any],
    errors: list[str],
    warnings: list[str],
    metrics: dict[str, Any],
) -> None:
    manifest_ref = case.get("manifest_path")
    path = _validate_artifact_path(root, manifest_ref, "manifest_path", errors, warnings)
    if path is None:
        return
    manifest = _load_json(path, errors)
    if not isinstance(manifest, dict):
        errors.append(f"Pitch manifest is not a JSON object: {manifest_ref}")
        return

    expected = case.get("expected") or {}
    if not isinstance(expected, dict):
        errors.append("expected must be a JSON object.")
        return
    if case.get("validation_eligible") is False:
        warnings.append("scaffolded system observations are diagnostic-only and cannot serve as expected truth.")
        return

    expected_status = expected.get("observation_quality_status")
    if expected_status is not None:
        actual_status = ((manifest.get("observation_quality") or {}).get("status"))
        metrics["observation_quality_status"] = actual_status
        if actual_status != expected_status:
            errors.append(f"observation_quality.status is {actual_status!r}, expected {expected_status!r}.")

    expected_mode = expected.get("trajectory_mode")
    if expected_mode is not None:
        actual_mode = ((manifest.get("trajectory") or {}).get("mode"))
        metrics["trajectory_mode"] = actual_mode
        if actual_mode != expected_mode:
            errors.append(f"trajectory.mode is {actual_mode!r}, expected {expected_mode!r}.")

    expected_z = expected.get("plate_z_ft")
    if expected_z is not None:
        max_z_error = _positive_number(expected.get("max_plate_z_error_ft", 0.5), "max_plate_z_error_ft", errors)
        actual_z = _plate_z(manifest)
        metrics["plate_z_ft"] = actual_z
        if actual_z is None:
            errors.append("trajectory.plate_crossing_xyz_ft[2] is missing.")
        elif max_z_error is not None and abs(float(actual_z) - float(expected_z)) > max_z_error:
            errors.append(
                f"plate z error {abs(float(actual_z) - float(expected_z)):.3f} ft exceeds {max_z_error:.3f} ft."
            )


def _validate_artifact_path(
    root: Path,
    value: Any,
    field_name: str,
    errors: list[str],
    warnings: list[str],
) -> Path | None:
    if value in (None, ""):
        return None
    if not isinstance(value, str):
        errors.append(f"{field_name} must be a string path.")
        return None
    path = (root / value).resolve() if not Path(value).is_absolute() else Path(value).resolve()
    if not _is_relative_to(path, root):
        errors.append(f"{field_name} escapes fixture directory: {value!r}.")
        return None
    if not path.exists():
        warnings.append(f"{field_name} does not exist: {value}.")
        return None
    return path


def _validate_status_artifact(
    root: Path,
    value: Any,
    field_name: str,
    component_name: str,
    errors: list[str],
    warnings: list[str],
    components: dict[str, dict[str, Any]],
) -> None:
    path = _validate_artifact_path(root, value, field_name, errors, warnings)
    if value in (None, ""):
        return
    if path is None:
        components[component_name] = _component_result(WARN, [f"{field_name} missing or invalid."], [])
        return
    payload = _load_json(path, errors)
    if not isinstance(payload, dict):
        components[component_name] = _component_result(FAIL, [], [f"{field_name} is not a JSON object."])
        return

    status = _artifact_status(payload)
    detail = f"{field_name} status is {status}."
    if status == FAIL:
        errors.append(detail)
        components[component_name] = _component_result(FAIL, [], [detail])
    elif status == WARN:
        warnings.append(detail)
        components[component_name] = _component_result(WARN, [detail], [])
    else:
        components[component_name] = _component_result(PASS, [], [])


def _artifact_status(payload: dict[str, Any]) -> str:
    raw_status = payload.get("status", payload.get("sync_quality", payload.get("quality")))
    status = str(raw_status or "UNKNOWN").upper()
    if status in {"PASS", "GOOD", "EXCELLENT"}:
        return PASS
    if status in {"FAIL", "POOR", "CRITICAL"}:
        return FAIL
    return WARN


def _summarize_case_component(
    component_name: str,
    cases: list[dict[str, Any]],
    components: dict[str, dict[str, Any]],
) -> None:
    if not cases:
        return
    component_errors: list[str] = []
    component_warnings: list[str] = []
    for case in cases:
        component_errors.extend(f"{case['case_id']}: {item}" for item in case["errors"])
        component_warnings.extend(f"{case['case_id']}: {item}" for item in case["warnings"])
    status = FAIL if component_errors else WARN if component_warnings else PASS
    components[component_name] = _component_result(status, component_warnings, component_errors)


def _load_json(path: Path, errors: list[str]) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        errors.append(f"Could not read JSON {path}: {exc}.")
        return None


def _xyz(value: Any, field_name: str, errors: list[str]) -> tuple[float, float, float] | None:
    if not isinstance(value, list) or len(value) != 3:
        errors.append(f"{field_name} must be a three-number list.")
        return None
    try:
        return (float(value[0]), float(value[1]), float(value[2]))
    except (TypeError, ValueError):
        errors.append(f"{field_name} must contain only numbers.")
        return None


def _positive_number(value: Any, field_name: str, errors: list[str]) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        errors.append(f"{field_name} must be a number.")
        return None
    if number < 0.0:
        errors.append(f"{field_name} must be non-negative.")
        return None
    return number


def _distance(left: tuple[float, float, float], right: tuple[float, float, float]) -> float:
    return sqrt(sum((left[index] - right[index]) ** 2 for index in range(3)))


def _plate_z(manifest: dict[str, Any]) -> float | None:
    crossing = ((manifest.get("trajectory") or {}).get("plate_crossing_xyz_ft"))
    if not isinstance(crossing, list) or len(crossing) < 3:
        return None
    try:
        return float(crossing[2])
    except (TypeError, ValueError):
        return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _component_result(status: str, warnings: list[str], errors: list[str]) -> dict[str, Any]:
    return {
        "status": status,
        "warnings": list(warnings),
        "errors": list(errors),
    }


def _case_result(
    case_id: str,
    component: str,
    status: str,
    errors: list[str],
    warnings: list[str],
    metrics: dict[str, Any],
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "component": component,
        "status": status,
        "errors": list(errors),
        "warnings": list(warnings),
        "metrics": dict(metrics),
    }


def _result(
    status: str,
    manifest_path: Path,
    errors: list[str],
    warnings: list[str],
    case_results: list[dict[str, Any]],
    components: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    return {
        "schema_version": "field_fixture_report.v1",
        "status": status,
        "manifest_path": str(manifest_path),
        "errors": list(errors),
        "warnings": list(warnings),
        "components": dict(sorted(components.items())),
        "cases": list(case_results),
    }
