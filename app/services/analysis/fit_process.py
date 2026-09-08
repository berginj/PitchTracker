"""Hard wall-clock deadlines around the native trajectory fitter."""

from dataclasses import replace
import json
import logging
import subprocess
from uuid import uuid4

from app.worker_process import worker_command
from trajectory.contracts import FailureCode, TrajectoryDiagnostics, TrajectoryFitRequest, TrajectoryFitResult
from trajectory.serialization import decode_result, encode_request
from trajectory.physics_estimation import stationary_track

logger = logging.getLogger(__name__)


def fit_in_process(request: TrajectoryFitRequest) -> TrajectoryFitResult:
    if stationary_track(request):
        return TrajectoryFitResult(
            request.mode,
            [],
            None,
            None,
            None,
            0.0,
            TrajectoryDiagnostics(failure_codes=[FailureCode.SPEED_UNIDENTIFIABLE]),
        )
    request = replace(request, correlation_id=request.correlation_id or uuid4().hex)
    try:
        result = subprocess.run(
            worker_command("trajectory_fit"),
            input=encode_request(request),
            capture_output=True,
            text=True,
            encoding="utf-8",
            timeout=request.deadline_seconds,
            check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        if result.returncode != 0:
            raise RuntimeError(f"fit worker exited {result.returncode}: {result.stderr[-2000:]}")
        response = json.loads(result.stdout)
        if response.get("correlation_id") != request.correlation_id:
            raise ValueError("fit worker response correlation mismatch")
        if not response.get("ok"):
            raise ValueError(response.get("error", "fit worker failed"))
        return decode_result(response["result"])
    except subprocess.TimeoutExpired:
        # subprocess.run kills and waits for its child before raising. A timed
        # out fit cannot keep running or publish a stale result into a new session.
        code = FailureCode.DEADLINE_EXCEEDED
        message = f"{request.mode} exceeded {request.deadline_seconds}s including worker startup"
        logger.warning("Fit deadline: correlation_id=%s %s", request.correlation_id, message)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as exc:
        code = FailureCode.INVALID_INPUT if isinstance(exc, ValueError) else FailureCode.OPT_DID_NOT_CONVERGE
        message = f"{type(exc).__name__}: {exc}"
        logger.error("Fit failed: correlation_id=%s %s", request.correlation_id, message, exc_info=True)
    return TrajectoryFitResult(
        request.mode, [], None, None, None, 0.0, TrajectoryDiagnostics(failure_codes=[code], notes=[message])
    )
