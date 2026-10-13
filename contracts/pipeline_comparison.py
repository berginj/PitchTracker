"""Typed optional-detector experiments with immutable local sources."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import uuid4

DETECTOR_PROFILES = ("classical_a", "classical_b", "baseballcv_box", "baseballcv_refined")
STEREO_PROFILES = ("greedy_v1", "global_v2", "global_v3")
VARIANTS = tuple(f"{detector}:{stereo}" for detector in DETECTOR_PROFILES for stereo in STEREO_PROFILES)


@dataclass(frozen=True)
class PipelineComparisonRequest:
    dataset_path: Path
    output_dir: Path
    bundle_path: Path | None = None
    variants: tuple[str, ...] = VARIANTS
    monocular_assets: Path | None = None
    external_python: Path | None = None
    external_repository: Path | None = None
    job_id: str = field(default_factory=lambda: uuid4().hex)

    def __post_init__(self):
        if (
            not self.variants
            or len(set(self.variants)) != len(self.variants)
            or any(v not in VARIANTS for v in self.variants)
        ):
            raise ValueError("Select known, distinct comparison variants")
        if not self.job_id or any(
            c not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-" for c in self.job_id
        ):
            raise ValueError("Invalid comparison job identity")
        if len(self.job_id) > 80 or self.dataset_path.resolve().is_relative_to(self.output_dir.resolve()):
            raise ValueError("Comparison output must be separate from the dataset manifest")
        if self.monocular_assets and (not self.external_python or not self.external_repository):
            raise ValueError("Monocular research requires an isolated Python and pinned repository")

    def to_payload(self) -> dict[str, Any]:
        return {
            "schema_version": "pipeline_comparison_request.v1",
            "job_id": self.job_id,
            "dataset_path": str(self.dataset_path),
            "output_dir": str(self.output_dir),
            "bundle_path": str(self.bundle_path) if self.bundle_path else None,
            "variants": list(self.variants),
            "monocular_assets": str(self.monocular_assets) if self.monocular_assets else None,
            "external_python": str(self.external_python) if self.external_python else None,
            "external_repository": str(self.external_repository) if self.external_repository else None,
        }

    @classmethod
    def from_payload(cls, data):
        if data.get("schema_version") != "pipeline_comparison_request.v1":
            raise ValueError("Unsupported comparison request")
        return cls(
            Path(data["dataset_path"]),
            Path(data["output_dir"]),
            Path(data["bundle_path"]) if data.get("bundle_path") else None,
            tuple(data["variants"]),
            Path(data["monocular_assets"]) if data.get("monocular_assets") else None,
            Path(data["external_python"]) if data.get("external_python") else None,
            Path(data["external_repository"]) if data.get("external_repository") else None,
            data["job_id"],
        )


@dataclass(frozen=True)
class PipelineComparisonProgress:
    job_id: str
    completed: int
    total: int
    status: str
    variant: str | None = None


@dataclass(frozen=True)
class PipelineComparisonResult:
    report: dict[str, Any]
    report_path: Path
