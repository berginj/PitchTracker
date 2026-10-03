"""Immutable application resources and writable operator state.

Source execution keeps workspace paths. Frozen applications keep operator state
under LOCALAPPDATA (or an explicitly selected PITCHTRACKER_DATA_DIR); configuration
paths chosen by an operator, including foreign absolute paths, are not rewritten.
"""

from __future__ import annotations

import os
from pathlib import Path
import sys

from app.runtime_migration import copy_file_once, migrate_legacy_state

DEFAULT_CONFIGS = ("default.yaml", "snapdragon.yaml")
STATE_DIRECTORIES = ("configs", "logs", "calibration", "rois", "data", "recordings")


def resource_root() -> Path:
    """Locate read-only bundled defaults/assets, or the source workspace."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)).resolve()
    return Path(__file__).resolve().parents[1]


def state_root() -> Path:
    """Return frozen per-user state or the caller's source working directory."""
    if not getattr(sys, "frozen", False):
        return Path.cwd().resolve()
    selected = os.environ.get("PITCHTRACKER_DATA_DIR")
    if selected:
        path = Path(selected)
        if not path.is_absolute():
            raise ValueError("PITCHTRACKER_DATA_DIR must be an absolute operator-selected path")
        return path.resolve()
    base = Path(os.environ.get("LOCALAPPDATA", str(Path.home() / "AppData" / "Local")))
    return (base / "PitchTracker").resolve()


def seed_default_configs(resources: Path, state: Path) -> None:
    """Copy only distributable defaults, preserving every existing operator file."""
    defaults = resources / "defaults" / "configs"
    if not defaults.is_dir():
        defaults = resources / "configs"
    for filename in DEFAULT_CONFIGS:
        copy_file_once(defaults / filename, state / "configs" / filename, state)


def prepare_frozen_runtime() -> None:
    """Prepare state before logging imports; source imports have no side effects."""
    if not getattr(sys, "frozen", False):
        return
    resources, state = resource_root(), state_root()
    install_root = Path(sys.executable).resolve().parent
    if state.is_relative_to(install_root) or state.is_relative_to(resources):
        raise ValueError("Operator state must be outside the immutable installation directory")
    state.mkdir(parents=True, exist_ok=True)
    for directory in STATE_DIRECTORIES:
        target = state / directory
        if target.is_symlink() or target.is_junction():
            raise ValueError(f"Operator state directory must not be a link: {target}")
        target.mkdir(parents=True, exist_ok=True)
    # An explicit state override is isolated, e.g. a smoke test or a new operator
    # workspace. Never import old/private installation state into that workspace.
    migration_marker = state / ".legacy-migration-v1-complete"
    if migration_marker.is_symlink() or migration_marker.is_junction():
        raise ValueError("Legacy migration marker must not be a link")
    if "PITCHTRACKER_DATA_DIR" not in os.environ and not migration_marker.exists():
        migrate_legacy_state((resources, install_root), state, STATE_DIRECTORIES)
        migration_marker.write_text("Legacy files copied without overwrites; external paths unchanged.\n", encoding="utf-8")
    seed_default_configs(resources, state)
    os.chdir(state)


def prepare_launcher_environment() -> None:
    """Keep source launches rooted in their checkout; frozen paths are prepared."""
    if getattr(sys, "frozen", False):
        prepare_frozen_runtime()
    else:
        root = resource_root()
        if not any(os.path.normcase(entry) == os.path.normcase(str(root)) for entry in sys.path):
            sys.path.insert(0, str(root))
        os.chdir(root)
