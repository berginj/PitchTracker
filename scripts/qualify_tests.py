"""Run pytest with explicit return/cleanup markers for Windows exit qualification.

This preserves pytest's exit code and does not retry tests. The calling shell
must also record the final process exit code: interpreter shutdown follows the
PYTEST_RETURN marker and can fail independently of the passing test summary.
"""

from __future__ import annotations

import faulthandler
import json
from pathlib import Path
import sys
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def marker(phase: str, exit_code: int) -> None:
    print(json.dumps({"qualification_phase": phase, "pytest_exit_code": int(exit_code),
                      "python_version": sys.version.split()[0],
                      "python_threads": [{"name": thread.name, "daemon": thread.daemon}
                                         for thread in threading.enumerate()]}), flush=True)


class Diagnostics:
    def pytest_sessionfinish(self, session, exitstatus) -> None:
        marker("pytest_sessionfinish", exitstatus)


def main() -> int:
    import pytest

    faulthandler.enable(all_threads=True)
    result = pytest.main(sys.argv[1:], plugins=[Diagnostics()])
    marker("pytest_return", result)
    return int(result)


if __name__ == "__main__":
    raise SystemExit(main())
