"""Field-alignment provider and presentation model."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass
from pathlib import Path

from calib.field_transform import FieldTransform, estimate_field_transform
from ui.setup.quality_report_view import ReportRow, ReportView


@dataclass(frozen=True)
class FieldAlignmentSnapshot:
    passed: bool
    transform: FieldTransform | None
    recommendation: str
    fixture_source_sha256: str = ""
    fixture_point_count: int = 0


def load_or_estimate_field_alignment(
    calib_dir: Path = Path("calibration"),
    *,
    force_recalculate: bool = False,
) -> FieldAlignmentSnapshot:
    calib_dir = Path(calib_dir)
    transform_path = calib_dir / "field_transform.json"
    fixture_path = calib_dir / "field_fixture_points.json"
    try:
        fixture_payload = None
        fixture_source_sha256 = ""
        fixture_point_count = 0
        if fixture_path.exists():
            fixture_bytes = fixture_path.read_bytes()
            fixture_source_sha256 = hashlib.sha256(fixture_bytes).hexdigest()
            fixture_payload = json.loads(fixture_bytes.decode("utf-8"))
            camera_points = fixture_payload["camera_points_ft"]
            field_points = fixture_payload["field_points_ft"]
            if len(camera_points) != len(field_points):
                raise ValueError("camera and field fixture point counts differ")
            fixture_point_count = len(camera_points)

        existing_payload = None
        if transform_path.exists():
            existing_payload = json.loads(transform_path.read_text(encoding="utf-8"))

        should_estimate = fixture_payload is not None and (
            force_recalculate
            or existing_payload is None
            or existing_payload.get("fixture_source_sha256") != fixture_source_sha256
            or int(existing_payload.get("fixture_point_count") or 0) != fixture_point_count
        )
        if should_estimate:
            transform = estimate_field_transform(
                fixture_payload["camera_points_ft"],
                fixture_payload["field_points_ft"],
                fixture_id=str(fixture_payload.get("fixture_id") or fixture_path.stem),
                max_rms_residual_ft=float(fixture_payload.get("max_rms_residual_ft", 0.1)),
            )
            existing_payload = {
                **transform.to_payload(),
                "fixture_source_sha256": fixture_source_sha256,
                "fixture_point_count": fixture_point_count,
            }
            transform_path.write_text(json.dumps(existing_payload, indent=2), encoding="utf-8")
            recommendation = "Field transform estimated and persisted with fixture provenance."
        elif existing_payload is not None and not force_recalculate:
            transform = _transform_from_payload(existing_payload)
            fixture_source_sha256 = str(existing_payload.get("fixture_source_sha256") or fixture_source_sha256)
            fixture_point_count = int(existing_payload.get("fixture_point_count") or fixture_point_count)
            recommendation = "Field coordinate transform loaded and validated."
        else:
            return FieldAlignmentSnapshot(
                False,
                None,
                "Survey at least three non-collinear field targets and save calibration/field_fixture_points.json.",
            )

        if not transform.passes_residual_gate:
            return FieldAlignmentSnapshot(
                False,
                transform,
                f"Field alignment residual {transform.rms_residual_ft:.3f} ft exceeds "
                f"the {transform.max_rms_residual_ft:.3f} ft gate.",
                fixture_source_sha256,
                fixture_point_count,
            )
        return FieldAlignmentSnapshot(
            True,
            transform,
            recommendation,
            fixture_source_sha256,
            fixture_point_count,
        )
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return FieldAlignmentSnapshot(False, None, f"Field alignment data is invalid: {exc}")
    return FieldAlignmentSnapshot(
        False,
        None,
        "Survey at least three non-collinear field targets and save calibration/field_fixture_points.json.",
    )


def _transform_from_payload(payload: dict) -> FieldTransform:
    return FieldTransform(
        tuple(tuple(float(value) for value in row) for row in payload["matrix_4x4"]),
        float(payload["rms_residual_ft"]),
        str(payload["fixture_id"]),
        float(payload.get("max_rms_residual_ft", 0.1)),
    )


def present_field_alignment(snapshot: FieldAlignmentSnapshot) -> ReportView:
    rows: list[ReportRow] = []
    if snapshot.transform:
        rows.extend(
            [
                ReportRow("Fixture", snapshot.transform.fixture_id),
                ReportRow("RMS residual", f"{snapshot.transform.rms_residual_ft:.3f} ft"),
                ReportRow("Residual gate", f"≤ {snapshot.transform.max_rms_residual_ft:.3f} ft"),
                ReportRow("Fixture points", str(snapshot.fixture_point_count or "unknown")),
                ReportRow(
                    "Fixture source",
                    snapshot.fixture_source_sha256[:12] if snapshot.fixture_source_sha256 else "legacy / unavailable",
                ),
                ReportRow("Coordinate frame", "field", tone="success"),
            ]
        )
    rows.append(ReportRow("Result", "PASS" if snapshot.passed else "FAIL", tone="success" if snapshot.passed else "error"))
    return ReportView(
        "Field alignment: ready" if snapshot.passed else "Field alignment: required",
        "success" if snapshot.passed else "error",
        rows,
        [] if snapshot.passed else [snapshot.recommendation],
    )


__all__ = ["FieldAlignmentSnapshot", "load_or_estimate_field_alignment", "present_field_alignment"]
