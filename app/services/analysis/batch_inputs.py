"""Verified recorded requests; legacy reconstruction is explicitly labelled."""

from dataclasses import fields, replace
import hashlib
from pathlib import Path
from uuid import uuid4

from app.pipeline.recording.evidence_journal import load_session_evidence_journal
from app.pipeline.recording.evidence_package import load_evidence_package
from contracts import StereoObservation
from trajectory.contracts import TrajectoryFitRequest
from trajectory.serialization import decode_request


def digest(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def recorded_requests(session: Path):
    if not session.is_dir():
        raise ValueError(f"Session directory missing: {session}")
    manifest = session / "evidence_journal" / "manifest.json"
    prepared = {}
    if manifest.is_file():
        records = load_session_evidence_journal(manifest)
        source_hash = digest(manifest)
        for record in records:
            if record["stream"] == "TrajectoryFitPreparedEvent":
                payload = record["payload"]
                request = decode_request(payload["request_envelope"])
                prepared[payload["pitch_id"], request.mode] = (
                    payload["pitch_id"],
                    request,
                    {"basis": "recorded_request", "manifest_sha256": source_hash},
                )
    if prepared:
        yield from prepared.values()
        return
    names = {field.name for field in fields(StereoObservation)}
    for evidence in sorted(session.glob("pitch_*/evidence/manifest.json")):
        package = load_evidence_package(evidence)
        observations = [
            StereoObservation(**{key: value for key, value in row.items() if key in names})
            for row in package["streams"].get("analysis_observations", [])
        ]
        if observations:
            yield package["manifest"]["pitch_id"], TrajectoryFitRequest(
                observations,
                plate_plane_z_ft=0.0,
                correlation_id=uuid4().hex,
            ), {
                "basis": "legacy_reconstructed",
                "manifest_sha256": digest(evidence),
                "assumptions": [
                    "Default fit settings and plate plane; original request was not recorded",
                    "Missing covariance uses the configured observation noise",
                ],
            }


OVERRIDES = frozenset(
    {
        "plate_plane_z_ft",
        "drag_k0",
        "drag_sigma",
        "drag_prior_enabled",
        "max_iter",
        "observation_sigma_ft",
        "max_speed_std_mph",
        "deadline_seconds",
        "wind_ft_s",
    }
)


def apply_overrides(request, overrides, backend):
    unknown = set(overrides) - OVERRIDES
    if unknown:
        raise ValueError(f"Unsupported fit overrides: {sorted(unknown)}")
    if "max_iter" in overrides and (type(overrides["max_iter"]) is not int or not 1 <= overrides["max_iter"] <= 10000):
        raise ValueError("max_iter must be an integer between 1 and 10000")
    wind = overrides.get("wind_ft_s")
    if wind is not None:
        import math

        if len(wind) != 3 or not all(math.isfinite(value) for value in wind):
            raise ValueError("wind_ft_s must contain three finite values")
    return replace(request, **overrides, compute_backend=backend)
