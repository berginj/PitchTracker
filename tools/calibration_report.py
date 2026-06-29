#!/usr/bin/env python
"""Generate a read-only stereo calibration report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from calib.calibration_report import build_calibration_report  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Report saved stereo calibration quality.")
    parser.add_argument("--calibration", type=Path, default=Path("calibration/stereo_calibration.npz"))
    parser.add_argument("--config", type=Path, default=Path("configs/default.yaml"))
    parser.add_argument("--measured-baseline-in", type=float, default=None)
    parser.add_argument("--max-rms-px", type=float, default=2.0)
    parser.add_argument("--baseline-tolerance-in", type=float, default=1.0)
    parser.add_argument("--output", type=Path, default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_calibration_report(
        calibration_path=args.calibration,
        config_path=args.config,
        measured_baseline_in=args.measured_baseline_in,
        max_rms_px=args.max_rms_px,
        baseline_tolerance_in=args.baseline_tolerance_in,
    )
    payload = json.dumps(report, indent=2, sort_keys=True)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)
    return 0 if report["status"] != "FAIL" else 2


if __name__ == "__main__":
    raise SystemExit(main())
