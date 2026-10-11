"""Supervise offline video preparation independently from the UI and live work."""

from concurrent.futures import CancelledError
from dataclasses import replace
import json
import logging
import queue
import subprocess
from threading import Thread
from time import monotonic
from hashlib import sha256
from app.pipeline.recording.evidence_package import _atomic_write_text

from app.services.analysis.research_priority import capture_active
from app.worker_process import worker_command
from trajectory.serialization import decode_request

logger = logging.getLogger(__name__)


def replay_requests(session, request, cancel):
    while capture_active():
        if cancel.wait(0.05):
            raise CancelledError()
    process = subprocess.Popen(
        worker_command("video_replay"),
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )
    output: queue.Queue[str | None] = queue.Queue()
    assert process.stdin is not None and process.stdout is not None and process.stderr is not None
    stdin, stdout, stderr = process.stdin, process.stdout, process.stderr

    def read():
        try:
            output.put(stdout.readline())
        finally:
            output.put(None)

    def errors():
        for line in stderr:
            logger.debug("Video replay: %s", line.rstrip()[:2000])

    readers = [Thread(target=read, daemon=True), Thread(target=errors, daemon=True)]
    try:
        stdin.write(json.dumps(replace(request, session_dirs=(session,)).to_payload()) + "\n")
        stdin.flush()
        for reader in readers:
            reader.start()
        paused = False
        active_seconds, previous = 0.0, monotonic()
        while True:
            if cancel.is_set():
                raise CancelledError()
            now = monotonic()
            if not paused:
                active_seconds += now - previous
            previous = now
            if active_seconds > 3600:
                raise ValueError("Video preparation exceeded its one-hour active deadline")
            active = capture_active()
            if active != paused:
                stdin.write(json.dumps({"command": "pause" if active else "resume"}) + "\n")
                stdin.flush()
                paused = active
            try:
                line = output.get(timeout=0.05)
            except queue.Empty:
                continue
            if not line:
                raise ValueError("Video worker exited without a result")
            response = json.loads(line)
            if not response.get("ok"):
                raise ValueError(response.get("error", "Video replay failed"))
            stdin.close()
            process.wait(timeout=2)
            accounting = response.get("accounting", {})
            key = sha256(json.dumps(accounting, sort_keys=True).encode()).hexdigest()
            artifact = request.output_dir / "replays" / f"{key}.json"
            artifact.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(
                artifact, json.dumps({"schema_version": "video_replay.v1", "accounting": accounting}, sort_keys=True)
            )
            if not response["rows"]:
                raise ValueError(
                    f"No accepted pitches; processed {accounting.get('frames_processed', 0)} frames; accounting: {artifact}"
                )
            for row in response["rows"]:
                yield row["pitch_id"], decode_request(row["request"]), row["provenance"]
            break
    finally:
        if process.poll() is None:
            process.kill()
        process.wait(timeout=2)
        for reader in readers:
            if reader.ident is not None:
                reader.join(timeout=2)
        for pipe in (stdin, stdout, stderr):
            pipe.close()
