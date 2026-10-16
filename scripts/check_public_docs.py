"""Validate maintained Markdown, instruction filenames and documentation entry points."""

from __future__ import annotations

import posixpath
import re
import subprocess
import sys
from datetime import date
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
REQUIRED_FILES = (
    "AGENTS.md", "README.md", "README_INSTALL.md", "README_LAUNCHER.md",
    "CONTRIBUTING.md", "SUPPORT.md", "SECURITY.md", "docs/README.md",
    "docs/DOCUMENTATION.md", "docs/QUICK_START.md", "docs/TESTING_NEEDED.md",
    "docs/GLOSSARY.md", "docs/CURRENT_STATUS.md", "docs/ROADMAP.md",
    "docs/FAQ.md", "docs/SETUP_DOCTOR.md", "docs/TEST_SUITE_DOCUMENTATION.md",
    "docs/user/CALIBRATION_TIPS.md", "docs/user/TROUBLESHOOTING.md",
    "docs/architecture/agent-contracts.md", "archive/docs/ARCHIVE_INDEX.md",
)
ISSUE_TEMPLATES = (
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/pilot_feedback.yml",
    ".github/ISSUE_TEMPLATE/validation_report.yml",
)
HISTORICAL_PREFIXES = ("archive/", "docs/review/")
ARCHIVE_INDEX = "archive/docs/ARCHIVE_INDEX.md"
LINK_PATTERN = re.compile(
    r"""!?\[[^\]\n]*\]\(\s*(?:<(?P<angle>[^>\n]+)>|(?P<bare>[^\s)]+))"""
    r"""(?:\s+["'][^\n]*["'])?\s*\)"""
)
REFERENCE_PATTERN = re.compile(r"(?m)^ {0,3}\[[^\]]+\]:\s*(?:<([^>\n]+)>|(\S+))")
DATE_PATTERN = re.compile(r"(?:Last reviewed|Last Updated|Last updated):\**\s*(\d{4}-\d{2}-\d{2})")


def repository_files(root: Path) -> set[str]:
    """Include tracked files and new reviewable files, excluding ignored local data."""
    result = subprocess.run(
        ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
        cwd=root, capture_output=True, text=True, encoding="utf-8", check=True,
    )
    return {name for name in result.stdout.split("\0") if name and (root / name).is_file()}


def maintained_markdown(paths: set[str]) -> list[str]:
    """Keep dated evidence and historical prose outside current-guidance checks."""
    return sorted(
        path for path in paths
        if path.lower().endswith(".md")
        and (path == ARCHIVE_INDEX or not path.startswith(HISTORICAL_PREFIXES))
    )


def prose(text: str) -> str:
    """Remove fenced examples and inline code before interpreting prose links/dates."""
    lines: list[str] = []
    fence = ""
    for line in text.splitlines():
        marker = re.match(r"^ {0,3}(\x60{3,}|~{3,})", line)
        if marker:
            token = marker.group(1)
            if not fence:
                fence = token
            elif token[0] == fence[0] and len(token) >= len(fence):
                fence = ""
            lines.append("")
        else:
            lines.append("" if fence else line)
    return re.sub(r"\x60+.*?\x60+", "", "\n".join(lines))


def link_targets(text: str) -> list[str]:
    """Read inline/image destinations and reference-link definitions."""
    content = prose(text)
    inline = [match.group("angle") or match.group("bare") for match in LINK_PATTERN.finditer(content)]
    references = [match.group(1) or match.group(2) for match in REFERENCE_PATTERN.finditer(content)]
    return inline + references


def link_error(source: str, target: str, paths: set[str]) -> str | None:
    """Resolve repository paths without accepting wrong-case or private local targets."""
    if target.startswith(("#", "//")) or re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target):
        return None
    target_path = unquote(target.split("#", 1)[0])
    if not target_path:
        return None
    relative = posixpath.normpath(
        target_path.lstrip("/") if target_path.startswith("/")
        else posixpath.join(posixpath.dirname(source), target_path)
    )
    if relative == ".." or relative.startswith("../"):
        return "target escapes the repository"
    prefix = relative.rstrip("/") + "/"
    if relative == "." or relative in paths or any(path.startswith(prefix) for path in paths):
        return None
    for path in paths:
        if path.casefold() == relative.casefold():
            return f"filename case differs; use {path}"
        if path.casefold().startswith(prefix.casefold()):
            return f"filename case differs; use {path[:len(relative)]}"
    return "target is missing or is not a version-controlled/reviewable file"


def check_document(root: Path, name: str, paths: set[str], today: date) -> list[str]:
    """Check a maintained document while reporting malformed input as a useful failure."""
    try:
        text = (root / name).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeError) as exc:
        return [f"{name}: cannot read UTF-8 documentation: {exc}"]
    errors = []
    for target in link_targets(text):
        reason = link_error(name, target, paths)
        if reason:
            errors.append(f"{name} -> {target}: {reason}")
    for value in DATE_PATTERN.findall(prose(text)):
        try:
            if date.fromisoformat(value) > today:
                errors.append(f"{name}: future review date: {value}")
        except ValueError:
            errors.append(f"{name}: invalid review date: {value}")
    return errors


def instruction_errors(paths: set[str]) -> list[str]:
    """Keep current instructions discoverable and obsolete notes non-executable as policy."""
    errors = []
    if "AGENTS.md" not in paths:
        errors.append("missing exact-case root AGENTS.md")
    if "agents.md" in paths:
        errors.append("root agents.md must be renamed to AGENTS.md")
    for path in sorted(paths):
        if path.startswith("archive/") and Path(path).name in {"AGENTS.md", "AGENTS.override.md"}:
            errors.append(f"{path}: rename historical agent notes so they are not discovered as instructions")
    return errors


def main() -> int:
    try:
        paths = repository_files(ROOT)
    except (OSError, subprocess.SubprocessError) as exc:
        print(f"Documentation inventory failed: {exc}", file=sys.stderr)
        return 1
    errors = instruction_errors(paths)
    errors.extend(f"missing documentation entry point: {name}" for name in REQUIRED_FILES + ISSUE_TEMPLATES if name not in paths)
    documents = maintained_markdown(paths)
    for name in documents + [name for name in ISSUE_TEMPLATES if name in paths]:
        errors.extend(check_document(ROOT, name, paths, date.today()))
    if "README.md" in paths:
        readme = (ROOT / "README.md").read_text(encoding="utf-8-sig", errors="replace")
        if "pyqt6" in readme.lower():
            errors.append("README.md uses PyQt6; the application uses PySide6")
        if "Python 3.11 or 3.12" in readme:
            errors.append("README.md contains the retired Python 3.11/3.12 requirement")
    if errors:
        print("Documentation checks failed:\n" + "\n".join(f"- {error}" for error in errors), file=sys.stderr)
        return 1
    print(f"Documentation checks passed ({len(documents)} maintained Markdown files; {len(ISSUE_TEMPLATES)} issue templates).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
