"""Recording-owned persistence for delayed, non-primary trajectory diagnostics."""

import json
import logging

from app.pipeline.recording.evidence_package import _atomic_write_text

logger = logging.getLogger(__name__)


def persist_comparison(service, event):
    with service._lock:
        if event.metadata.session_id != service._session_name:
            logger.warning("Ignoring comparison from another session: pitch=%s", event.pitch_id)
            return
        recorder = service._session_recorder
        root = recorder.get_session_dir() if recorder is not None else None
    if root is None:
        logger.warning("Comparison has no recording session: pitch=%s", event.pitch_id)
        return
    service._on_decision_evidence(event)
    pitch_dir = (root / event.pitch_id).resolve()
    if pitch_dir.parent != root.resolve() or not pitch_dir.is_dir():
        logger.warning("Comparison pitch directory is unavailable: pitch=%s", event.pitch_id)
        return
    with service._pitch_artifact_lock:
        _atomic_write_text(
            pitch_dir / "trajectory_comparisons.json",
            json.dumps(
                {
                    "schema_version": "trajectory_comparisons.v1",
                    "pitch_id": event.pitch_id,
                    "metadata": event.metadata.to_dict(),
                    "results": event.results,
                },
                allow_nan=False,
                sort_keys=True,
                indent=2,
            ),
        )
