"""Explicit opt-in to an independently packaged numerical worker architecture."""

import os
from pathlib import Path

from app.worker_process import worker_command


def numerical_command():
    override = os.environ.get("PITCHTRACKER_NUMERICAL_WORKER")
    if override:
        path = Path(override).resolve()
        if not path.is_file():
            raise FileNotFoundError(f"Numerical worker missing: {path}")
        return [str(path)]
    return worker_command("trajectory_fit_persistent")
