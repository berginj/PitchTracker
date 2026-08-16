"""Rig profile persistence, path resolution, and legacy fallback logic."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any, Optional, cast

from app.services.rig_profile_models import (
    RigProfile,
    utc_now_iso,
)
from contracts.physical_validation import (
    TrajectoryModeApprovalV2,
    payload_sha256,
)
from log_config.logger import get_logger

logger = get_logger(__name__)


def sha256_file(path: Path) -> str:
    """Compute SHA-256 hex digest of a file."""
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def atomic_write_text(path: Path, text: str) -> None:
    """Replace a small durable text artifact without exposing partial contents."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary_path, path)
    except Exception:
        temporary_path.unlink(missing_ok=True)
        raise


def first_existing(paths: tuple[Path, ...], *, default: Path) -> Path:
    """Return the first path that exists on disk, or the default."""
    for path in paths:
        if path.exists():
            return path
    return default


def load_legacy_quality_metrics() -> dict[str, Any]:
    """Load quality metrics from legacy calibration report."""
    report_path = Path("calibration/report.json")
    if not report_path.exists():
        return {}
    try:
        return cast(dict[str, Any], json.loads(report_path.read_text(encoding="utf-8")))
    except Exception:
        return {}


def resolve_profile_file(base_dir: Path, profile: RigProfile, raw_path: str) -> Path:
    """Resolve a profile-relative or absolute file path."""
    path = Path(raw_path)
    profile_dir = base_dir / profile.profile_id
    candidates = [path]
    if profile.profile_id != "legacy" and not path.is_absolute():
        candidates.insert(0, profile_dir / path)

    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve() if profile.profile_id != "legacy" else candidate

    if profile.profile_id != "legacy" and not path.is_absolute():
        return profile_dir / path
    return path


def save_profile(
    base_dir: Path,
    profile: RigProfile,
    *,
    calibration_path: Path,
    roi_path: Path,
    setup_snapshot_path: Path,
    profile_path: Path,
) -> RigProfile:
    """Persist a rig profile and compute artifact hashes."""
    (base_dir / profile.profile_id).mkdir(parents=True, exist_ok=True)
    hashes = dict(profile.artifact_hashes)
    for label, path in {
        "calibration": calibration_path,
        "roi": roi_path,
    }.items():
        if path.exists() and path.is_file():
            hashes[label] = sha256_file(path)
    if profile.field_transform:
        hashes["field_transform"] = payload_sha256(profile.field_transform)
    if profile.hardware_fingerprint:
        hashes["hardware_fingerprint"] = payload_sha256(profile.hardware_fingerprint)
    if profile.setup_snapshot:
        atomic_write_text(
            setup_snapshot_path,
            json.dumps(profile.setup_snapshot, indent=2, sort_keys=True),
        )
        hashes["setup_snapshot"] = sha256_file(setup_snapshot_path)
    for approval in profile.trajectory_mode_approvals:
        if isinstance(approval, TrajectoryModeApprovalV2):
            hashes[f"approval:{approval.approval_id}"] = payload_sha256(
                approval.to_payload()
            )
    saved = replace(profile, updated_utc=utc_now_iso(), artifact_hashes=hashes)
    atomic_write_text(profile_path, json.dumps(saved.to_dict(), indent=2))
    return saved


def activate_profile(active_marker: Path, profile_path: Path, profile_id: str) -> None:
    """Set the given profile as active after verifying it exists."""
    if not profile_path.exists():
        raise FileNotFoundError(f"Rig profile not found: {profile_id}")
    atomic_write_text(active_marker, profile_id)


def load_profile(path: Path) -> RigProfile:
    """Load a rig profile from its JSON path."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return RigProfile.from_dict(data)


def load_active_profile(active_marker: Path, base_dir: Path) -> Optional[RigProfile]:
    """Load the currently active rig profile, or None."""
    if not active_marker.exists():
        return None
    try:
        profile_id = active_marker.read_text(encoding="utf-8").strip()
        if not profile_id:
            return None
        return load_profile(base_dir / profile_id / "rig_profile.json")
    except Exception as exc:
        logger.warning(f"Active rig profile could not be loaded: {exc}")
        return None
