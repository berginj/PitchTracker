"""Read only explicit recorded labels; never infer attribution from folder names."""

from pathlib import Path
import logging

from app.review.session_artifacts import PITCH_MANIFEST_CANDIDATES, find_existing_path, load_json


def recorded_pitcher(manifest: dict) -> str | None:
    block = manifest.get("pitcher")
    value = block.get("name") if isinstance(block, dict) and block.get("schema_version") == "pitcher_attribution.v1" else manifest.get("pitcher_name")
    return value if isinstance(value, str) and value.strip() else None


def has_recorded_player(session_dir: Path, name: str) -> bool:
    for pitch in session_dir.glob("pitch_*"):
        if not pitch.is_dir():
            continue
        path = find_existing_path(pitch, PITCH_MANIFEST_CANDIDATES)
        if path:
            try:
                manifest = load_json(path, "pitch attribution")
                if isinstance(manifest, dict) and recorded_pitcher(manifest) == name:
                    return True
            except (OSError, ValueError):
                logging.getLogger(__name__).warning("Could not read historical pitcher attribution: %s", path, exc_info=True)
                continue  # Corrupt artifacts cannot establish a name match.
    return False
