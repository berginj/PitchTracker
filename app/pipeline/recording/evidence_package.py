"""Replayable pitch evidence package with integrity verification."""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class EvidencePackageWriter:
    root: Path
    pitch_id: str
    metadata: dict[str, Any]
    _streams: dict[str, list[dict[str, Any]]] = field(default_factory=dict)
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _write_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)

    def add(self, stream: str, payload: dict[str, Any]) -> None:
        if not re.fullmatch(r"[A-Za-z0-9_-]+", stream):
            raise ValueError(f"invalid evidence stream name: {stream!r}")
        with self._lock:
            self._streams.setdefault(stream, []).append(dict(payload))

    def write(self) -> Path:
        # Serialize complete package generations. Stream files are immutable and
        # content-addressed; the manifest is replaced last, so a concurrent
        # reader sees either the complete old generation or the complete new one.
        with self._write_lock:
            package_dir = Path(self.root) / "evidence"
            package_dir.mkdir(parents=True, exist_ok=True)
            files: dict[str, dict[str, Any]] = {}
            with self._lock:
                streams = {name: [dict(item) for item in records] for name, records in self._streams.items()}
                metadata = dict(self.metadata)
            for stream, records in sorted(streams.items()):
                content = "".join(
                    json.dumps(item, sort_keys=True, default=_json_default) + "\n" for item in records
                )
                digest = hashlib.sha256(content.encode("utf-8")).hexdigest()
                path = package_dir / f"{stream}.{digest}.jsonl"
                if not path.exists() or _sha256(path) != digest:
                    _atomic_write_text(path, content)
                files[path.name] = {"stream": stream, "records": len(records), "sha256": digest}
            manifest = {
                "schema_version": "evidence_package.v2",
                "pitch_id": self.pitch_id,
                "metadata": metadata,
                "files": files,
            }
            manifest_path = package_dir / "manifest.json"
            _atomic_write_text(
                manifest_path,
                json.dumps(manifest, indent=2, sort_keys=True, default=_json_default),
            )
            return manifest_path


def load_evidence_package(manifest_path: Path) -> dict[str, Any]:
    manifest_path = Path(manifest_path)
    root = manifest_path.parent.resolve()
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    streams: dict[str, list[dict[str, Any]]] = {}
    for filename, descriptor in manifest.get("files", {}).items():
        path = (root / filename).resolve()
        if path.parent != root:
            raise ValueError(f"evidence path escapes package: {filename}")
        if _sha256(path) != descriptor.get("sha256"):
            raise ValueError(f"evidence integrity check failed: {filename}")
        records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
        if len(records) != descriptor.get("records"):
            raise ValueError(f"evidence record count mismatch: {filename}")
        stream = descriptor.get("stream") or path.stem
        streams[str(stream)] = records
    return {"manifest": manifest, "streams": streams}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_default(value: Any) -> Any:
    if hasattr(value, "item") and callable(value.item):
        return value.item()
    raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")


def _atomic_write_text(path: Path, content: str) -> None:
    """Durably replace one file without exposing partially written JSON."""
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            newline="",
            dir=path.parent,
            prefix=f".{path.name}.",
            suffix=".tmp",
            delete=False,
        ) as handle:
            temporary_path = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        for attempt in range(5):
            try:
                os.replace(temporary_path, path)
                temporary_path = None
                break
            except PermissionError:
                if attempt == 4:
                    raise
                # Windows scanners/codecs can briefly hold a just-created file.
                time.sleep(0.02 * (attempt + 1))
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)


__all__ = ["EvidencePackageWriter", "load_evidence_package"]
