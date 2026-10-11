"""Enforce repository typing suppressions and mypy-configuration policy."""

from __future__ import annotations

import re
import configparser
import tomllib
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TYPE_IGNORE = re.compile(r"#\s*type:\s*ignore(?!\s*\[[^\]]+\])")
EXCLUDED_PARTS = {".git", ".venv", "venv", "archive", "build", "dist", "__pycache__"}
TEST_RELAXATIONS = {
    "arg-type",
    "attr-defined",
    "union-attr",
    "call-arg",
    "var-annotated",
    "operator",
    "index",
    "no-any-return",
    "method-assign",
    "comparison-overlap",
    "list-item",
    "return-value",
    "func-returns-value",
    "dict-item",
    "has-type",
    "misc",
    "call-overload",
    "import-not-found",
    "assignment",
}


def policy_violations(root: Path = ROOT) -> list[str]:
    violations: list[str] = []
    for config_name in ("mypy.ini", ".mypy.ini", "setup.cfg", "pyproject.toml"):
        path = root / config_name
        if not path.exists():
            continue
        try:
            if path.suffix == ".toml":
                mypy = tomllib.loads(path.read_text(encoding="utf-8")).get("tool", {}).get("mypy", {})
                sections = {"mypy": {key: value for key, value in mypy.items() if key != "overrides"}}
                for index, override in enumerate(mypy.get("overrides", [])):
                    modules = override.get("module", [])
                    name = "mypy-tests.*" if modules in ("tests.*", ["tests.*"]) else f"override-{index}"
                    sections[name] = override
            else:
                parser = configparser.ConfigParser(inline_comment_prefixes=("#", ";"))
                parser.read_string(path.read_text(encoding="utf-8"))
                sections = {name: dict(parser[name]) for name in parser.sections() if name.startswith("mypy")}
        except (ValueError, configparser.Error) as exc:
            violations.append(f"{config_name}: invalid configuration: {exc}")
            continue
        for section, options in sections.items():
            if str(options.get("ignore_errors", "false")).lower() in {"true", "1", "yes", "on"}:
                violations.append(f"{config_name}:{section}: blanket ignore_errors is forbidden")
            disabled = options.get("disable_error_code")
            if disabled is not None:
                codes = set(disabled) if isinstance(disabled, list) else {code.strip() for code in str(disabled).split(",")}
                if section != "mypy-tests.*" or codes != TEST_RELAXATIONS:
                    violations.append(
                        f"{config_name}:{section}: disable_error_code must match the fixed test-only policy"
                    )

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
