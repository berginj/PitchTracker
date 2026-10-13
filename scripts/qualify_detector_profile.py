"""Create a bound operational receipt after held-out and actual capture gates."""

import argparse
import json
from pathlib import Path
from app.services.analysis.comparison_qualification import qualify_profile
from configs.settings import load_config


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("report", "timing", "config", "bundle", "output"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--variant", required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Choose a new qualification receipt path")
    result = qualify_profile(args.report, args.timing, load_config(args.config), args.bundle, args.variant)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
    print(args.output)


if __name__ == "__main__":
    main()
