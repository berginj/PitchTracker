"""Enforce repository typing suppressions and mypy-configuration policy."""

from __future__ import annotations

import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?!\s*\[[^\]]+\])")
IGNORE_ERRORS = re.compile(r"^\s*ignore_errors\s*=\s*(?:true|1|yes)\s*$", re.IGNORECASE)
EXCLUDED_PARTS = {".git", ".venv", "venv", "archive", "build", "dist", "__pycache__"}


def policy_violations(root: Path = ROOT) -> list[str]:
    violations: list[str] = []
    for config_name in ("mypy.ini", ".mypy.ini", "setup.cfg", "pyproject.toml"):
        path = root / config_name
        if not path.exists():
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if IGNORE_ERRORS.match(line):
                violations.append(f"{config_name}:{line_number}: blanket ignore_errors is forbidden")

    for path in root.rglob("*.py"):
        if any(part in EXCLUDED_PARTS for part in path.relative_to(root).parts):
            continue
        for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            if TYPE_IGNORE.search(line):
                relative = path.relative_to(root).as_posix()
                violations.append(
                    f"{relative}:{line_number}: type ignores require one or more error codes"
                )
    return violations


def main() -> int:
    violations = policy_violations()
    if violations:
        print("Typing policy violations:")
        print("\n".join(violations))
        return 1
    print("OK: typing suppressions and mypy configuration are scoped")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
