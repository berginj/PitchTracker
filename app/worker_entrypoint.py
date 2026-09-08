"""Allowlisted console-worker dispatcher. No Qt application is constructed."""

import argparse
import importlib
import json
import os

from app.worker_process import WORKER_MODULES


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("task", choices=tuple(WORKER_MODULES))
    parser.add_argument("task_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    rest = args.task_args
    if args.task == "health":
        if rest:
            parser.error("unexpected arguments for health task")
        print(json.dumps({"schema_version": "worker_health.v1", "ok": True, "pid": os.getpid()}))
        return
    module = importlib.import_module(WORKER_MODULES[args.task])
    if args.task == "camera_probe":
        module.main(rest)
    elif rest:
        parser.error("unexpected arguments for worker task")
    else:
        module.main()


if __name__ == "__main__":
    main()
