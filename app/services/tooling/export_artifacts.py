"""Cancellation-safe selected-session exports with atomic publication."""

from __future__ import annotations

from concurrent.futures import CancelledError
import json
import os
from pathlib import Path
from threading import Event
import tempfile
from typing import Any
import zipfile


def _check_cancel(cancel_event: Event) -> None:
    if cancel_event.is_set():
        raise CancelledError("Export cancelled")


def _target(path: Path, session_dir: Path) -> Path:
    target = path.resolve()
    if target.is_relative_to(session_dir.resolve()):
        raise ValueError("Export outside the recorded session to preserve source artifacts")
    return target


def export_json(path: Path, payload: dict[str, Any], session_dir: Path, cancel_event: Event) -> bool:
    target = _target(path, session_dir)
    text = json.dumps(payload, indent=2, allow_nan=False)
    temporary: Path | None = None
    try:
        _check_cancel(cancel_event)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(text)
        _check_cancel(cancel_event)
        os.replace(temporary, target)
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def export_manifest_archive(path: Path, session_dir: Path, cancel_event: Event) -> bool:
    target = _target(path, session_dir)
    root = session_dir.resolve(strict=True)
    files = [
        root / name
        for name in ("manifest.json", "session_summary.json", "session_summary.csv")
        if (root / name).is_file()
    ]
    files.extend(sorted(root.glob("pitch_*/manifest.json")))
    if not files:
        raise ValueError("No manifest files found to export")
    temporary: Path | None = None
    try:
        _check_cancel(cancel_event)
        with tempfile.NamedTemporaryFile(dir=target.parent, delete=False) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for source in files:
                if not source.resolve().is_relative_to(root):
                    raise ValueError("Export artifact escapes the selected session")
                _check_cancel(cancel_event)
                with source.open("rb") as incoming, archive.open(source.relative_to(root).as_posix(), "w") as outgoing:
                    while chunk := incoming.read(1024 * 1024):
                        _check_cancel(cancel_event)
                        outgoing.write(chunk)
        _check_cancel(cancel_event)
        os.replace(temporary, target)
        return True
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
