"""Reap an owned numerical worker, including a Windows one-file bootloader child."""

import logging
import os
from pathlib import Path
import subprocess

logger = logging.getLogger(__name__)


def terminate_worker(process: subprocess.Popen) -> None:
    if process.poll() is None:
        if os.name == "nt":
            taskkill = Path(os.environ.get("SystemRoot", r"C:\Windows")) / "System32" / "taskkill.exe"
            try:
                result = subprocess.run(
                    [str(taskkill), "/PID", str(process.pid), "/T", "/F"],
                    stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True, timeout=2,
                    creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                )
                if result.returncode and process.poll() is None:
                    logger.warning("Worker tree termination failed: pid=%s error=%s", process.pid, result.stderr.strip())
            except (OSError, subprocess.TimeoutExpired):
                logger.warning("Worker tree termination failed: pid=%s", process.pid, exc_info=True)
        if process.poll() is None:
            process.terminate()
    try:
        process.wait(timeout=1)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=1)
