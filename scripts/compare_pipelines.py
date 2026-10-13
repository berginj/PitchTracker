"""Compare optional detectors and stereo approaches on immutable local sessions."""

import argparse
import json
from pathlib import Path

from app.services.analysis.pipeline_comparison import run_pipeline_comparison
from contracts.pipeline_comparison import PipelineComparisonRequest, VARIANTS


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--bundle", type=Path)
    parser.add_argument("--variant", choices=VARIANTS, action="append")
    parser.add_argument("--monocular-assets", type=Path)
    parser.add_argument("--external-python", type=Path)
    parser.add_argument("--external-repository", type=Path)
    args = parser.parse_args()
    result = run_pipeline_comparison(
        PipelineComparisonRequest(
            args.dataset,
            args.output,
            args.bundle,
            tuple(args.variant or VARIANTS),
            args.monocular_assets,
            args.external_python,
            args.external_repository,
        )
    )
    print(
        json.dumps(
            {
                "status": result.report["status"],
                "report": str(result.report_path),
                "variants": len(result.report["results"]),
                "physical_claim_eligible": False,
            }
        )
    )
    raise SystemExit(0 if result.report["status"] == "completed" else 2)


if __name__ == "__main__":
    main()
