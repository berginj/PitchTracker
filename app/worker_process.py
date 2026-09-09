"""Commands for source and frozen workers; never treat the GUI exe as Python."""

from pathlib import Path
import sys
from typing import Optional, List

WORKER_MODULES = {
    "camera_probe": "app.camera_probe_worker",
    "setup_capture": "app.services.capture.setup_worker_main",
    "tooling": "app.services.tooling.worker_main",
    "trajectory_fit": "app.trajectory_worker",
    "health": "app.worker_entrypoint",
}


def worker_command(task: str, *, python_executable: Optional[str] = None) -> List[str]:
    if task not in WORKER_MODULES:
        raise ValueError(f"Unknown worker task: {task}")
    executable = python_executable or sys.executable
    if getattr(sys, "frozen", False) and executable == sys.executable:
        worker = Path(sys.executable).with_name("PitchTrackerWorker.exe")
        if not worker.is_file():
            raise FileNotFoundError(f"Packaged worker missing: {worker}; reinstall the complete application")
        return [str(worker), task]
    command = [executable, "-m", WORKER_MODULES[task]]
    return [*command, "health"] if task == "health" else command
