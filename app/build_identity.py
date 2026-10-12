"""Identity of the running measurement build, including frozen applications."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys


def current_source_revision() -> tuple[str, bool | None]:
    override = os.environ.get("PITCHTRACKER_SOURCE_REVISION")
    if override:
        return override, None
    if getattr(sys, "frozen", False):
        from app.runtime_paths import resource_root
        try:
            payload = json.loads((resource_root() / "build_identity.json").read_text(encoding="utf-8"))
            return str(payload["source_revision"]), payload["working_tree_dirty"]
        except (OSError, ValueError, KeyError):
            return "UNAVAILABLE", None
    root = Path(__file__).resolve().parents[1]
    try:
        revision = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "HEAD"], capture_output=True, text=True, timeout=2, check=True,
        ).stdout.strip()
        dirty = bool(subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain", "--untracked-files=no"],
            capture_output=True, text=True, timeout=2, check=True,
        ).stdout.strip())
        return revision, dirty
    except (OSError, subprocess.SubprocessError):
        return "UNAVAILABLE", None
