"""Controlled offline decoder; a blocked native call is killed by its supervisor."""

from concurrent.futures import CancelledError
import contextlib
import json
import sys
from threading import Event, Thread
from typing import Any


def main():
    from contracts.fit_jobs import FitBatchRequest
    from trajectory.serialization import encode_request
    from app.services.analysis.video_replay import replay

    request = FitBatchRequest.from_payload(json.loads(sys.stdin.readline()))
    paused, cancelled = Event(), Event()

    def control():
        for line in sys.stdin:
            command = json.loads(line).get("command")
            if command == "pause":
                paused.set()
            elif command == "resume":
                paused.clear()
            elif command == "cancel":
                cancelled.set()

    def check():
        while paused.is_set() and not cancelled.is_set():
            cancelled.wait(0.05)
        if cancelled.is_set():
            raise CancelledError()

    Thread(target=control, daemon=True).start()
    accounting: dict[str, Any] = {}
    try:
        with contextlib.redirect_stdout(sys.stderr):
            rows = list(replay(request.session_dirs[0], request, check, accounting))
        print(
            json.dumps(
                {
                    "ok": True,
                    "accounting": accounting,
                    "rows": [
                        {"pitch_id": pid, "request": json.loads(encode_request(fit)), "provenance": provenance}
                        for pid, fit, provenance in rows
                    ],
                },
                allow_nan=False,
            ),
            flush=True,
        )
    except Exception as exc:
        print(json.dumps({"ok": False, "error": f"{type(exc).__name__}: {exc}"}), flush=True)


if __name__ == "__main__":
    main()
