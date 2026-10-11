"""Run or resume local refits without changing captured sessions."""

import argparse
import json
from pathlib import Path
import signal
from threading import Event

from app.services.analysis.fit_batch import run_fit_batch
from contracts.fit_jobs import FitBatchRequest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--session", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--backend", choices=("cpu", "auto", "cuda", "reference"), default="cpu")
    parser.add_argument("--workers", type=int, default=0)
    parser.add_argument("--workflow", choices=("observations", "videos"), default="observations")
    parser.add_argument("--overrides", type=Path)
    for name in ("config", "calibration", "roi", "field-transform"):
        parser.add_argument(f"--{name}", type=Path)
    args = parser.parse_args()
    cancel = Event()
    signal.signal(signal.SIGINT, lambda *_: cancel.set())
    request = FitBatchRequest(
        tuple(args.session),
        args.output,
        workflow=args.workflow,
        backend=args.backend,
        workers=args.workers,
        overrides=json.loads(args.overrides.read_text()) if args.overrides else {},
        config_path=args.config,
        calibration_path=args.calibration,
        roi_path=args.roi,
        field_transform_path=args.field_transform,
    )
    result = run_fit_batch(
        request,
        cancel,
        lambda value: print(
            f"{value.status}: {value.completed}/{value.total}",
            flush=True,
        ),
    )
    print(result.report["report_path"])


if __name__ == "__main__":
    main()
