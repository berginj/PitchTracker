"""Check the public documentation map for broken local links and drift."""

from __future__ import annotations

import re
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PUBLIC_FILES = (
    "README.md",
    "README_INSTALL.md",
    "CONTRIBUTING.md",
    "SUPPORT.md",
    "SECURITY.md",
    "docs/README.md",
    "docs/QUICK_START.md",
    "docs/TESTING_NEEDED.md",
    "docs/GLOSSARY.md",
    "docs/CURRENT_STATUS.md",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/pilot_feedback.yml",
    ".github/ISSUE_TEMPLATE/validation_report.yml",
)
LINK_PATTERN = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
DATE_PATTERN = re.compile(r"(?:Last reviewed|Last Updated|Last updated):\**\s*(\d{4}-\d{2}-\d{2})")


def _check_links(path: Path) -> list[str]:
    errors: list[str] = []
    text = path.read_text(encoding="utf-8")
    for target in LINK_PATTERN.findall(text):
        target = target.strip()
        if target.startswith(("http://", "https://", "mailto:", "#")):
            continue
        local_target = target.split("#", 1)[0]
        if not local_target:
            continue
        resolved = (path.parent / local_target).resolve()
        if not resolved.is_file() and not resolved.is_dir():
            errors.append(f"{path.relative_to(ROOT)} -> {target}")
    return errors


def main() -> int:
    errors: list[str] = []
    for relative_path in PUBLIC_FILES:
        path = ROOT / relative_path
        if not path.is_file():
            errors.append(f"missing public documentation file: {relative_path}")
            continue
        errors.extend(_check_links(path))

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    if "PyQt6" in readme or "pyqt6" in readme.lower():
        errors.append("README.md uses PyQt6; the application uses PySide6")
    if "Python 3.11 or 3.12" in readme:
        errors.append("README.md contains the retired Python 3.11/3.12 requirement")

    current_status = (ROOT / "docs" / "CURRENT_STATUS.md").read_text(encoding="utf-8")
    status_match = DATE_PATTERN.search(current_status)
    if status_match is not None:
        current_date = status_match.group(1)
        for relative_path in PUBLIC_FILES:
            path = ROOT / relative_path
            if not path.is_file():
                continue
            for reviewed_date in DATE_PATTERN.findall(path.read_text(encoding="utf-8")):
                if reviewed_date != current_date:
                    errors.append(
                        f"{relative_path} was reviewed on {reviewed_date}; "
                        f"current status is {current_date}"
                    )

    if errors:
        print("Public documentation checks failed:", file=sys.stderr)
        print("\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Public documentation checks passed ({len(PUBLIC_FILES)} files).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
