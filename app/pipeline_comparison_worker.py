"""Console host for optional pipeline experiments; no Qt or camera acquisition."""

from dataclasses import asdict
import contextlib
import json
import sys


def main():
    from contracts.pipeline_comparison import PipelineComparisonRequest
    from app.services.analysis.pipeline_comparison import execute_pipeline_comparison

    try:
        request = PipelineComparisonRequest.from_payload(json.loads(sys.stdin.readline()))

        with contextlib.redirect_stdout(sys.stderr):
            # Keep progress on the original protocol stream while libraries log.
            protocol = sys.__stdout__
            assert protocol is not None

            def report_progress(value):
                protocol.write(json.dumps({"message_type": "progress", "payload": asdict(value)}) + "\n")
                protocol.flush()

            result = execute_pipeline_comparison(request, progress=report_progress)
        print(
            json.dumps({"message_type": "result", "job_id": request.job_id, "report_path": str(result.report_path)}),
            flush=True,
        )
    except Exception as exc:
        print(json.dumps({"message_type": "error", "error": f"{type(exc).__name__}: {exc}"}), flush=True)


if __name__ == "__main__":
    main()
