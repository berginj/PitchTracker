"""End-to-end admission receipts bound to the installed numerical implementation."""

import hashlib
import json
import os
from pathlib import Path
import sysconfig
from functools import lru_cache


@lru_cache(maxsize=1)
def _environment(module):
    import numpy
    import scipy
    import trajectory
    import sys
    from contracts.versioning import APP_VERSION

    sources = hashlib.sha256()
    for source in sorted(Path(trajectory.__file__).parent.glob("*.py")):
        sources.update(source.name.encode())
        sources.update(source.read_bytes())
    if getattr(sys, "frozen", False):
        sources.update(Path(sys.executable).read_bytes())

    return {
        "device": module.cuda_device(),
        "native_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
        "scipy": scipy.__version__,
        "numpy": numpy.__version__,
        "process_platform": sysconfig.get_platform(),
        "source_sha256": sources.hexdigest(),
        "app_version": APP_VERSION,
    }


def environment(module):
    return dict(_environment(module))


def auto_admitted(module, sample_count, concurrency=1):
    path = os.environ.get("PITCHTRACKER_CUDA_QUALIFICATION")
    if not path:
        return False
    try:
        receipt = json.loads(Path(path).read_text(encoding="utf-8"))
        return (
            receipt.get("schema_version") == "cuda_qualification.v1"
            and receipt.get("environment") == environment(module)
            and receipt.get("fit_parity_passed") is True
            and receipt.get("throughput_speedup", 0) >= 1.5
            and receipt.get("workers") == concurrency
            and sample_count in receipt.get("sample_counts", [])
        )
    except (OSError, ValueError, RuntimeError, TypeError):
        return False
