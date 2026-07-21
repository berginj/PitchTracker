"""Bounded asynchronous session journal for high-rate decision evidence."""

from __future__ import annotations

import hashlib
import json
import queue
import threading
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

from app.pipeline.recording.evidence_package import _atomic_write_text


@dataclass(frozen=True)
class JournalSubmitResult:
    accepted: bool
    sequence: int


class SessionEvidenceJournal:
    """Append decisions without performing disk I/O on publisher threads."""

    def __init__(self, session_dir: Path, *, max_queue: int = 4096) -> None:
        self.root = Path(session_dir) / "evidence_journal"
        self.root.mkdir(parents=True, exist_ok=True)
        self.path = self.root / "decisions.jsonl"
        self.manifest_path = self.root / "manifest.json"
        self._queue: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=max_queue)
        self._lock = threading.Lock()
        self._sequence = 0
        self._offered = 0
        self._accepted = 0
        self._written = 0
        self._dropped_required = 0
        self._dropped_optional = 0
        self._write_error: str | None = None
        self._closed = False
        self._thread = threading.Thread(target=self._run, name="session-evidence-journal", daemon=True)
        self._thread.start()

    def submit(self, stream: str, payload: Any, *, required: bool = True) -> JournalSubmitResult:
        with self._lock:
            if self._closed:
                raise RuntimeError("evidence journal is closed")
            self._sequence += 1
            sequence = self._sequence
            self._offered += 1
            record = {
                "schema_version": "decision_journal.v1",
                "sequence": sequence,
                "stream": str(stream),
                "payload": _jsonable(payload),
                "required": bool(required),
            }
            try:
                self._queue.put_nowait(record)
            except queue.Full:
                if required:
                    self._dropped_required += 1
                else:
                    self._dropped_optional += 1
                return JournalSubmitResult(False, sequence)
            self._accepted += 1
        return JournalSubmitResult(True, sequence)

    def submit_event(self, event: Any, *, required: bool = True) -> JournalSubmitResult:
        return self.submit(type(event).__name__, event, required=required)

    def close(self, *, timeout: float = 10.0) -> Path:
        with self._lock:
            if self._closed:
                return self.manifest_path
            self._closed = True
        self._queue.put(None, timeout=timeout)
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            raise RuntimeError("evidence journal did not drain before deadline")
        digest = hashlib.sha256(self.path.read_bytes()).hexdigest() if self.path.exists() else hashlib.sha256(b"").hexdigest()
        stats = self.stats()
        manifest = {
            "schema_version": "decision_journal.v1",
            "file": self.path.name,
            "sha256": digest,
            "records": stats["written"],
            "stats": stats,
            "complete": (
                stats["dropped_required"] == 0
                and stats["write_error"] is None
                and stats["accepted"] == stats["written"]
            ),
        }
        _atomic_write_text(self.manifest_path, json.dumps(manifest, indent=2, sort_keys=True))
        return self.manifest_path

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {
                "offered": self._offered,
                "accepted": self._accepted,
                "written": self._written,
                "dropped_required": self._dropped_required,
                "dropped_optional": self._dropped_optional,
                "backlog": self._queue.qsize(),
                "write_error": self._write_error,
            }

    def _run(self) -> None:
        try:
            with self.path.open("w", encoding="utf-8", newline="") as handle:
                while True:
                    record = self._queue.get()
                    if record is None:
                        break
                    handle.write(json.dumps(record, sort_keys=True, default=_json_default) + "\n")
                    with self._lock:
                        self._written += 1
                handle.flush()
        except Exception as exc:  # pragma: no cover - exercised with injected writer failures
            with self._lock:
                self._write_error = f"{exc.__class__.__name__}: {exc}"


def load_session_evidence_journal(
    manifest_path: Path,
    *,
    require_complete: bool = True,
) -> list[dict[str, Any]]:
    manifest_path = Path(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if require_complete and not bool(manifest.get("complete")):
        raise ValueError("decision journal is incomplete")
    path = manifest_path.parent / str(manifest["file"])
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != manifest.get("sha256"):
        raise ValueError("decision journal integrity check failed")
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]
    if len(records) != int(manifest.get("records", -1)):
        raise ValueError("decision journal record count mismatch")
    sequences = [int(record["sequence"]) for record in records]
    if sequences != sorted(sequences) or len(sequences) != len(set(sequences)):
        raise ValueError("decision journal sequence is not strictly increasing")
    return records


def _jsonable(value: Any) -> Any:
    if is_dataclass(value):
        return {key: _jsonable(item) for key, item in asdict(value).items()}
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "item") and callable(value.item):
        return value.item()
    return value


def _json_default(value: Any) -> Any:
    converted = _jsonable(value)
    if converted is value:
        raise TypeError(f"Object of type {value.__class__.__name__} is not JSON serializable")
    return converted


__all__ = ["JournalSubmitResult", "SessionEvidenceJournal", "load_session_evidence_journal"]
