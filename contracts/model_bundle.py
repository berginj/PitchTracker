"""Local, versioned ONNX detector assets; importing never downloads a model."""

from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
from typing import Any

Cov2 = tuple[tuple[float, float], tuple[float, float]]


def covariance2(value: Any) -> Cov2 | None:
    if value is None:
        return None
    if len(value) != 2 or any(len(row) != 2 for row in value):
        raise ValueError("Pixel covariance must be 2x2")
    a, b, c, d = (float(item) for row in value for item in row)
    if not all(math.isfinite(v) for v in (a, b, c, d)) or a <= 0 or d <= 0:
        raise ValueError("Pixel covariance must be finite and positive definite")
    if abs(b - c) > 1e-9 or a * d - b * c <= 0:
        raise ValueError("Pixel covariance must be symmetric and positive definite")
    return ((a, b), (c, d))


def file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True)
class ModelBundle:
    manifest_path: Path
    model_path: Path
    model_sha256: str
    bundle_sha256: str
    name: str
    class_names: tuple[str, ...]
    ball_class_id: int
    input_size: tuple[int, int]
    output_layout: str
    localization: str
    confidence_threshold: float
    nms_threshold: float
    max_candidates: int
    box_covariance_px2: Cov2 | None
    refined_covariance_px2: Cov2 | None
    source_revision: str
    licenses: dict[str, Any]

    @classmethod
    def load(cls, path: Path) -> "ModelBundle":
        path = Path(path).resolve()
        data = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_payload(data, path)

    @classmethod
    def from_payload(cls, data, path: Path, *, model_source: Path | None = None) -> "ModelBundle":
        """Validate an import before saving it; runtime loads always verify the saved model."""
        path = Path(path).resolve()
        if data.get("schema_version") != "detector_bundle.v1":
            raise ValueError("Unsupported detector bundle schema")
        model = (path.parent / data["model_file"]).resolve()
        if not model.is_relative_to(path.parent) or model.suffix.lower() != ".onnx":
            raise ValueError("Bundle model must be an ONNX file inside its directory")
        expected = data["model_sha256"]
        if not isinstance(expected, str) or len(expected) != 64 or file_hash(model_source or model) != expected:
            raise ValueError("Detector model hash mismatch")
        names = tuple(data["class_names"])
        ball_id = data["ball_class_id"]
        if not names or not all(isinstance(v, str) and v for v in names):
            raise ValueError("Declare model class names")
        if type(ball_id) is not int or not 0 <= ball_id < len(names):
            raise ValueError("Ball class does not match model classes")
        size = tuple(data.get("input_size", [640, 640]))
        if len(size) != 2 or any(type(v) is not int or not 128 <= v <= 2048 for v in size):
            raise ValueError("Invalid ONNX input dimensions")
        if data.get("preprocessing") != "rgb_letterbox_114_div255":
            raise ValueError("YOLO11 requires declared RGB letterbox preprocessing")
        layout = data.get("output_layout", "channels_first")
        localization = data.get("localization", "box")
        if layout not in {"channels_first", "rows"} or localization not in {"box", "refined"}:
            raise ValueError("Unsupported detector layout/localization")
        conf, nms = float(data.get("confidence_threshold", 0.25)), float(data.get("nms_threshold", 0.45))
        if not all(math.isfinite(v) and 0 < v < 1 for v in (conf, nms)):
            raise ValueError("Detector thresholds must lie between zero and one")
        cap = data.get("max_candidates", 20)
        if type(cap) is not int or not 1 <= cap <= 20:
            raise ValueError("Candidate cap must be between 1 and 20")
        licenses = data.get("licenses", {})
        if not isinstance(licenses, dict) or not all(licenses.get(k) for k in ("code", "weights", "data")):
            raise ValueError("Declare code, weight and data licensing; unknown is allowed for local research")
        manifest_hash = (
            file_hash(path)
            if path.exists()
            else hashlib.sha256(json.dumps(data, indent=2, allow_nan=False).encode()).hexdigest()
        )
        return cls(
            path,
            model,
            expected,
            manifest_hash,
            str(data["name"]),
            names,
            ball_id,
            (size[0], size[1]),
            layout,
            localization,
            conf,
            nms,
            cap,
            covariance2(data.get("box_covariance_px2")),
            covariance2(data.get("refined_covariance_px2")),
            str(data["source_revision"]),
            licenses,
        )

    def identity(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "bundle_sha256": self.bundle_sha256,
            "model_sha256": self.model_sha256,
            "source_revision": self.source_revision,
            "licenses": self.licenses,
        }
