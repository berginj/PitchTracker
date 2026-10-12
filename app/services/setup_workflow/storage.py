"""Atomic working-state persistence and recording admission for rig edits."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

import yaml

from app.services.rig_profile_persistence import atomic_write_text
from configs.validator import validate_config


CHECK_NAMES = ("images", "calibration", "field", "regions")


def configuration_file(root: Path, payload: dict[str, Any]) -> Path:
    validate_config(payload)
    text = yaml.safe_dump(payload, sort_keys=False)
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    path = root / f"config-{digest}.yaml"
    if not path.exists():
        atomic_write_text(path, text)
    return path


def contained(root: Path, filename: str) -> Path:
    path = (root / filename).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError("Setup artifact escapes its working directory")
    return path


def save_state(root: Path, state: dict[str, Any]) -> None:
    atomic_write_text(root / "state.json", json.dumps(state, indent=2, sort_keys=True, allow_nan=False))


def recording_blockers(base_dir: Path, profile_id: str | None) -> list[str]:
    """Pending edits cannot be bypassed by an already running capture."""
    blockers = []
    for path in (base_dir.parent / "setups").glob("*/state.json"):
        try:
            state = json.loads(path.read_text(encoding="utf-8"))
            relevant = profile_id in {state.get("base_profile_id"), state.get("published_profile_id")}
            if profile_id is None or profile_id == "legacy":
                relevant = not state.get("base_profile_id")
            if relevant and state.get("changed"):
                blockers.append("Saved rig changes need checks. Finish Setup before recording.")
        except (OSError, ValueError, TypeError):
            blockers.append("Saved setup state is unreadable. Open Setup to repair it before recording.")
    return blockers
