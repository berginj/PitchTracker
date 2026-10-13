"""Line-framed fit protocol; imports and solver state stay warm between jobs."""

import contextlib
import io
import json
import os
import sys
import sysconfig
from time import perf_counter


def main() -> None:
    with contextlib.redirect_stdout(io.StringIO()):
        from trajectory.registry import TrajectoryFitterRegistry
        from trajectory.serialization import decode_request, json_payload

        registry = TrajectoryFitterRegistry()
        from trajectory.native_kernel import native_module

        module = native_module()
        capabilities = {
            "native": module is not None,
            "cuda": module is not None and bool(getattr(module, "cuda_available", False)),
            "process_platform": sysconfig.get_platform(),
            "worker_pid": os.getpid(),
        }
        if capabilities["cuda"]:
            from trajectory.gpu_qualification import environment

            capabilities["gpu_environment"] = environment(module)
    print(
        json.dumps({"message_type": "ready", "schema_version": "trajectory_worker.v1", "capabilities": capabilities}),
        flush=True,
    )
    for line in sys.stdin:
        envelope = json.loads(line)
        response = {key: envelope.get(key) for key in ("correlation_id", "generation", "request_id")}
        try:
            started = perf_counter()
            with contextlib.redirect_stdout(io.StringIO()):
                if envelope.get("schema_version") == "trajectory_batch_worker.v1":
                    from trajectory.cuda_batch import fit_cuda_batch

                    results = fit_cuda_batch([decode_request(value) for value in envelope["requests"]])
                    response.update(ok=True, results=[json_payload(result.to_dict()) for result in results])
                    print(json.dumps(response, allow_nan=False), file=sys.__stdout__, flush=True)
                    continue
                request = decode_request(envelope)
                from trajectory.camera_model import cv2

                if request.mode.startswith("ray_") and cv2 is None:
                    from trajectory.contracts import FailureCode, TrajectoryDiagnostics, TrajectoryFitResult

                    result = TrajectoryFitResult(
                        request.mode,
                        [],
                        None,
                        None,
                        None,
                        0,
                        TrajectoryDiagnostics(
                            failure_codes=[FailureCode.CAMERA_MODEL_MISSING],
                            notes=["Numerical-only build lacks OpenCV distortion support"],
                        ),
                    )
                else:
                    result = registry.create(request.mode).fit_trajectory(request)
                result.diagnostics.performance["fit_ms"] = (perf_counter() - started) * 1000
            response.update(ok=True, result=json_payload(result.to_dict()))
        except Exception as exc:
            response.update(ok=False, error=f"{type(exc).__name__}: {exc}")
        print(json.dumps(response, allow_nan=False), flush=True)


if __name__ == "__main__":
    main()
