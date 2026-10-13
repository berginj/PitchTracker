"""Estimate development localization errors without consuming held-out truth."""

import argparse
import json
from pathlib import Path
from app.services.analysis.localization_calibration import estimate_localization_models


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new localization model file")
    result = estimate_localization_models(args.report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
