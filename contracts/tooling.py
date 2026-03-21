"""Contracts for process-backed tooling workflows."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional


def _path_to_str(path: Path | None) -> str | None:
    return None if path is None else str(path)


@dataclass(frozen=True)
class EnvironmentValidationResult:
    """Startup validation results returned by the tooling worker."""

    errors: list[str]
    warnings: list[str]

    def to_payload(self) -> dict[str, Any]:
        return {"errors": list(self.errors), "warnings": list(self.warnings)}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "EnvironmentValidationResult":
        return cls(
            errors=list(payload.get("errors", [])),
            warnings=list(payload.get("warnings", [])),
        )


@dataclass(frozen=True)
class TrainingReportRequest:
    """Request for building a training report in a worker process."""

    session_dir: Path
    config_path: Path
    roi_path: Path
    stride: int = 1
    skip_detection: bool = False
    skip_brightness: bool = False
    source: Optional[dict[str, Any]] = None
    report_id: Optional[str] = None
    created_utc: Optional[str] = None

    def to_payload(self) -> dict[str, Any]:
        return {
            "session_dir": str(self.session_dir),
            "config_path": str(self.config_path),
            "roi_path": str(self.roi_path),
            "stride": self.stride,
            "skip_detection": self.skip_detection,
            "skip_brightness": self.skip_brightness,
            "source": self.source,
            "report_id": self.report_id,
            "created_utc": self.created_utc,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TrainingReportRequest":
        return cls(
            session_dir=Path(payload["session_dir"]),
            config_path=Path(payload["config_path"]),
            roi_path=Path(payload["roi_path"]),
            stride=int(payload.get("stride", 1)),
            skip_detection=bool(payload.get("skip_detection", False)),
            skip_brightness=bool(payload.get("skip_brightness", False)),
            source=payload.get("source"),
            report_id=payload.get("report_id"),
            created_utc=payload.get("created_utc"),
        )


@dataclass(frozen=True)
class TrainingReportResult:
    """JSON-safe training report payload from the worker."""

    payload: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {"payload": self.payload}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "TrainingReportResult":
        return cls(payload=dict(payload["payload"]))


@dataclass(frozen=True)
class CalibrationRequest:
    """Request for running stereo calibration in a worker process."""

    left_paths: tuple[Path, ...]
    right_paths: tuple[Path, ...]
    pattern: str
    square_mm: float
    config_path: Path
    mode: str = "quick"
    write_updates: bool = True

    def to_payload(self) -> dict[str, Any]:
        return {
            "left_paths": [str(path) for path in self.left_paths],
            "right_paths": [str(path) for path in self.right_paths],
            "pattern": self.pattern,
            "square_mm": self.square_mm,
            "config_path": str(self.config_path),
            "mode": self.mode,
            "write_updates": self.write_updates,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CalibrationRequest":
        return cls(
            left_paths=tuple(Path(path) for path in payload["left_paths"]),
            right_paths=tuple(Path(path) for path in payload["right_paths"]),
            pattern=str(payload["pattern"]),
            square_mm=float(payload["square_mm"]),
            config_path=Path(payload["config_path"]),
            mode=str(payload.get("mode", "quick")),
            write_updates=bool(payload.get("write_updates", True)),
        )


@dataclass(frozen=True)
class CalibrationResult:
    """Summary of calibration outputs returned to the UI."""

    baseline_ft: float
    focal_length_px: float
    cx: float
    cy: float
    rms_error_px: float
    num_images_used: int
    total_input_images: int
    quality_rating: str
    quality_description: str
    quality_emoji: str
    recommendations: list[str]
    calibration_mode: str

    def to_payload(self) -> dict[str, Any]:
        return {
            "baseline_ft": self.baseline_ft,
            "focal_length_px": self.focal_length_px,
            "cx": self.cx,
            "cy": self.cy,
            "rms_error_px": self.rms_error_px,
            "num_images_used": self.num_images_used,
            "total_input_images": self.total_input_images,
            "quality_rating": self.quality_rating,
            "quality_description": self.quality_description,
            "quality_emoji": self.quality_emoji,
            "recommendations": list(self.recommendations),
            "calibration_mode": self.calibration_mode,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "CalibrationResult":
        return cls(
            baseline_ft=float(payload["baseline_ft"]),
            focal_length_px=float(payload["focal_length_px"]),
            cx=float(payload.get("cx", 0.0)),
            cy=float(payload.get("cy", 0.0)),
            rms_error_px=float(payload["rms_error_px"]),
            num_images_used=int(payload["num_images_used"]),
            total_input_images=int(payload["total_input_images"]),
            quality_rating=str(payload["quality_rating"]),
            quality_description=str(payload["quality_description"]),
            quality_emoji=str(payload["quality_emoji"]),
            recommendations=list(payload.get("recommendations", [])),
            calibration_mode=str(payload.get("calibration_mode", "FULL")),
        )

    @classmethod
    def from_updates(cls, updates: dict[str, Any]) -> "CalibrationResult":
        return cls(
            baseline_ft=float(updates.get("baseline_ft", 0.0)),
            focal_length_px=float(updates.get("focal_length_px", 0.0)),
            cx=float(updates.get("cx", 0.0)),
            cy=float(updates.get("cy", 0.0)),
            rms_error_px=float(updates.get("rms_error_px", 0.0)),
            num_images_used=int(updates.get("num_images_used", 0)),
            total_input_images=int(updates.get("total_input_images", 0)),
            quality_rating=str(updates.get("quality_rating", "UNKNOWN")),
            quality_description=str(updates.get("quality_description", "")),
            quality_emoji=str(updates.get("quality_emoji", "")),
            recommendations=list(updates.get("recommendations", [])),
            calibration_mode=str(updates.get("calibration_mode", "FULL")),
        )


@dataclass(frozen=True)
class AlignmentAnalysisRequest:
    """Request for analyzing camera alignment from saved image files."""

    left_image_path: Path
    right_image_path: Path
    max_features: int = 1000

    def to_payload(self) -> dict[str, Any]:
        return {
            "left_image_path": str(self.left_image_path),
            "right_image_path": str(self.right_image_path),
            "max_features": self.max_features,
        }

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AlignmentAnalysisRequest":
        return cls(
            left_image_path=Path(payload["left_image_path"]),
            right_image_path=Path(payload["right_image_path"]),
            max_features=int(payload.get("max_features", 1000)),
        )


@dataclass(frozen=True)
class AlignmentAnalysisResult:
    """Alignment analysis plus calibration prediction."""

    alignment: dict[str, Any]
    prediction: dict[str, Any]

    def to_payload(self) -> dict[str, Any]:
        return {"alignment": self.alignment, "prediction": self.prediction}

    @classmethod
    def from_payload(cls, payload: dict[str, Any]) -> "AlignmentAnalysisResult":
        return cls(
            alignment=dict(payload["alignment"]),
            prediction=dict(payload["prediction"]),
        )
