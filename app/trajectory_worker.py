"""One-shot fit worker without service/UI imports; native work dies with it."""

import contextlib
import io
import json
import sys


def main() -> None:
    envelope = json.load(sys.stdin)
    correlation_id = envelope.get("correlation_id")
    try:
        # Imports and numerical diagnostics must not corrupt the response stream.
        with contextlib.redirect_stdout(io.StringIO()):
            from trajectory.registry import TrajectoryFitterRegistry
            from trajectory.serialization import decode_request, json_payload

            request = decode_request(envelope)
            result = TrajectoryFitterRegistry().create(request.mode).fit_trajectory(request)
        response = {"ok": True, "correlation_id": correlation_id, "result": json_payload(result.to_dict())}
    except Exception as exc:
        response = {"ok": False, "correlation_id": correlation_id, "error": f"{type(exc).__name__}: {exc}"}
    print(json.dumps(response, allow_nan=False))


if __name__ == "__main__":
    main()
