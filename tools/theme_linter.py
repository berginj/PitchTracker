"""Theme system compliance linter for PitchTracker UI files.

Scans all UI Python files and reports violations of the theme system standards:
- Missing theme imports
- Inline setStyleSheet() with hardcoded values
- Manual font operations (setFont, setPointSize)
- Hardcoded colors
- Missing layout helpers
- Missing input polishing

Usage:
    python tools/theme_linter.py                    # Lint all ui/ files
    python tools/theme_linter.py --strict           # Exit with error if violations found
    python tools/theme_linter.py --file ui/dialogs/checklist_dialog.py  # Lint single file
    python tools/theme_linter.py --report report.txt  # Save report to file
"""

import argparse
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict


@dataclass
class Violation:
    """Theme compliance violation."""

    file_path: Path
    line_num: int
    rule: str
    severity: str  # CRITICAL, HIGH, MEDIUM, LOW
    message: str
    code_snippet: str

    def __str__(self):
        return f"{self.file_path}:{self.line_num} [{self.severity}] {self.rule}: {self.message}"


class ThemeLinter:
    """Linter for theme system compliance."""

    # Violation rules with severity
    RULES = {
        "MISSING_THEME_IMPORT": ("HIGH", "File creates UI but doesn't import theme system"),
        "INLINE_SETSTYLESHEET": ("HIGH", "Inline setStyleSheet() with hardcoded values - use theme variants"),
        "MANUAL_FONT": ("MEDIUM", "Manual font operations - use style_label() variants"),
        "HARDCODED_COLOR": ("MEDIUM", "Hardcoded color value - use theme tokens"),
        "MISSING_LAYOUT_HELPER": ("MEDIUM", "Dialog should use apply_standard_layout()"),
        "MISSING_POLISH": ("MEDIUM", "Dialog with inputs should call polish_form_controls()"),
        "RAW_QMESSAGEBOX": ("LOW", "Use show_message_dialog() instead of QMessageBox"),
        "HARDCODED_MARGINS": ("LOW", "Manual margins - use apply_standard_layout()"),
        "HARDCODED_SPACING": ("LOW", "Manual spacing - use apply_standard_layout()"),
    }

    # Files to skip (theme system itself, utilities)
    SKIP_PATTERNS = [
        "__pycache__",
        "__init__.py",
        "ui/themes/",  # Theme system itself is allowed to have inline styles
        "ui/render.py",  # Graphics utilities
        "ui/drawing.py",
        "ui/geometry.py",
        "ui/preview.py",
        "ui/device_utils.py",
    ]

    def __init__(self):
        self.violations: List[Violation] = []

    def should_skip(self, file_path: Path) -> bool:
        """Check if file should be skipped."""
        file_str = str(file_path)
        return any(pattern in file_str for pattern in self.SKIP_PATTERNS)

    def lint_file(self, file_path: Path) -> List[Violation]:
        """Lint a single Python file for theme compliance."""
        if self.should_skip(file_path):
            return []

        violations = []

        try:
            with open(file_path, "r", encoding="utf-8") as f:
                lines = f.readlines()
                content = "".join(lines)
        except Exception as e:
            print(f"Warning: Could not read {file_path}: {e}")
            return []

        # Determine if this is a UI file
        is_ui_file = any(
            indicator in content
            for indicator in [
                "QtWidgets.QDialog",
                "QtWidgets.QWidget",
                "QtWidgets.QMainWindow",
                "_build_ui",
                "QVBoxLayout",
                "QHBoxLayout",
            ]
        )

        if not is_ui_file:
            return []  # Skip non-UI files

        # Rule 1: Check for theme imports
        has_theme_import = (
            "from ui.themes import" in content or "import ui.themes" in content or "get_style_manager" in content
        )

        if not has_theme_import:
            severity, description = self.RULES["MISSING_THEME_IMPORT"]
            violations.append(
                Violation(
                    file_path=file_path,
                    line_num=1,
                    rule="MISSING_THEME_IMPORT",
                    severity=severity,
                    message=description,
                    code_snippet="# No theme imports found",
                )
            )

        # Rule 2: Check for inline setStyleSheet()
        for i, line in enumerate(lines, 1):
            if ".setStyleSheet(" in line:
                # Extract the stylesheet content
                match = re.search(r"setStyleSheet\((.*?)\)", line)
                if match:
                    style_content = match.group(1)
                    # Check for hardcoded values (colors, fonts, sizes)
                    if re.search(r"#[0-9A-Fa-f]{6}|font-size:|background-color:|color:", style_content):
                        severity, description = self.RULES["INLINE_SETSTYLESHEET"]
                        violations.append(
                            Violation(
                                file_path=file_path,
                                line_num=i,
                                rule="INLINE_SETSTYLESHEET",
                                severity=severity,
                                message=description,
                                code_snippet=line.strip()[:80],
                            )
                        )

        # Rule 3: Check for manual font operations
        for i, line in enumerate(lines, 1):
            if re.search(r"\.(setFont|setPointSize|setPixelSize|setBold|setItalic)\s*\(", line):
                # Skip if in comment
                if line.strip().startswith("#"):
                    continue
                severity, description = self.RULES["MANUAL_FONT"]
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_num=i,
                        rule="MANUAL_FONT",
                        severity=severity,
                        message=description,
                        code_snippet=line.strip()[:80],
                    )
                )

        # Rule 4: Check for hardcoded colors
        for i, line in enumerate(lines, 1):
            # Find hex colors
            matches = re.finditer(r"#[0-9A-Fa-f]{6}", line)
            for match in matches:
                color = match.group()
                severity, description = self.RULES["HARDCODED_COLOR"]
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_num=i,
                        rule="HARDCODED_COLOR",
                        severity=severity,
                        message=f"{description} (found: {color})",
                        code_snippet=line.strip()[:80],
                    )
                )

        # Rule 5: Check for missing layout helpers (dialogs)
        if "QDialog" in content:
            if "apply_standard_layout" not in content:
                severity, description = self.RULES["MISSING_LAYOUT_HELPER"]
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_num=1,
                        rule="MISSING_LAYOUT_HELPER",
                        severity=severity,
                        message=description,
                        code_snippet="# Dialog class but no apply_standard_layout() call",
                    )
                )

        # Rule 6: Check for missing polish_form_controls
        has_inputs = any(
            widget in content for widget in ["QLineEdit", "QComboBox", "QSpinBox", "QDoubleSpinBox", "QTextEdit"]
        )
        if has_inputs and "QDialog" in content:
            if "polish_form_controls" not in content:
                severity, description = self.RULES["MISSING_POLISH"]
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_num=1,
                        rule="MISSING_POLISH",
                        severity=severity,
                        message=description,
                        code_snippet="# Has input widgets but no polish_form_controls()",
                    )
                )

        # Rule 7: Check for raw QMessageBox
        for i, line in enumerate(lines, 1):
            if "QMessageBox." in line and "show_message_dialog" not in content:
                # Skip imports
                if "import" in line:
                    continue
                severity, description = self.RULES["RAW_QMESSAGEBOX"]
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_num=i,
                        rule="RAW_QMESSAGEBOX",
                        severity=severity,
                        message=description,
                        code_snippet=line.strip()[:80],
                    )
                )

        # Rule 8: Check for hardcoded margins
        for i, line in enumerate(lines, 1):
            if "setContentsMargins(" in line:
                # Check if it's not (0,0,0,0) which is sometimes needed
                match = re.search(r"setContentsMargins\((.*?)\)", line)
                if match:
                    args = match.group(1)
                    if args.strip() != "0, 0, 0, 0":
                        severity, description = self.RULES["HARDCODED_MARGINS"]
                        violations.append(
                            Violation(
                                file_path=file_path,
                                line_num=i,
                                rule="HARDCODED_MARGINS",
                                severity=severity,
                                message=f"{description} (found: {args})",
                                code_snippet=line.strip()[:80],
                            )
                        )

        # Rule 9: Check for hardcoded spacing
        for i, line in enumerate(lines, 1):
            if re.search(r"\.setSpacing\(\s*\d+\s*\)", line):
                severity, description = self.RULES["HARDCODED_SPACING"]
                violations.append(
                    Violation(
                        file_path=file_path,
                        line_num=i,
                        rule="HARDCODED_SPACING",
                        severity=severity,
                        message=description,
                        code_snippet=line.strip()[:80],
                    )
                )

        return violations

    def lint_directory(self, directory: Path) -> Dict[Path, List[Violation]]:
        """Lint all Python files in directory."""
        results = {}

        for file_path in directory.rglob("*.py"):
            violations = self.lint_file(file_path)
            if violations:
                results[file_path] = violations
                self.violations.extend(violations)

        return results

    def generate_summary(self) -> str:
        """Generate summary statistics."""
        if not self.violations:
            return "[OK] No theme violations found! All UI files are compliant."

        total_files = len(set(v.file_path for v in self.violations))
        total_violations = len(self.violations)

        # Count by severity
        by_severity = {}
        for v in self.violations:
            by_severity[v.severity] = by_severity.get(v.severity, 0) + 1

        # Count by rule
        by_rule = {}
        for v in self.violations:
            by_rule[v.rule] = by_rule.get(v.rule, 0) + 1

        summary = []
        summary.append("=" * 70)
        summary.append("THEME COMPLIANCE AUDIT REPORT")
        summary.append("=" * 70)
        summary.append("")
        summary.append(f"Total files with violations: {total_files}")
        summary.append(f"Total violations: {total_violations}")
        summary.append("")

        summary.append("By Severity:")
        for severity in ["CRITICAL", "HIGH", "MEDIUM", "LOW"]:
            count = by_severity.get(severity, 0)
            if count > 0:
                summary.append(f"  {severity}: {count}")
        summary.append("")

        summary.append("By Rule:")
        for rule, count in sorted(by_rule.items(), key=lambda x: -x[1]):
            summary.append(f"  {rule}: {count}")
        summary.append("")

        return "\n".join(summary)

    def generate_detailed_report(self) -> str:
        """Generate detailed violation report."""
        if not self.violations:
            return self.generate_summary()

        report = [self.generate_summary()]
        report.append("=" * 70)
        report.append("DETAILED VIOLATIONS")
        report.append("=" * 70)
        report.append("")

        # Group by file
        by_file = {}
        for v in self.violations:
            by_file.setdefault(v.file_path, []).append(v)

        # Sort files by violation count (worst first)
        sorted_files = sorted(by_file.items(), key=lambda x: -len(x[1]))

        for file_path, file_violations in sorted_files:
            report.append("")
            report.append(f"FILE: {file_path} ({len(file_violations)} violations)")
            report.append("-" * 70)

            # Sort by line number
            for v in sorted(file_violations, key=lambda x: x.line_num):
                report.append(f"  Line {v.line_num:4d} [{v.severity:8s}] {v.rule}")
                report.append(f"           {v.message}")
                report.append(f"           {v.code_snippet}")
                report.append("")

        return "\n".join(report)

    def generate_priority_list(self) -> str:
        """Generate prioritized fix list."""
        report = []
        report.append("=" * 70)
        report.append("PRIORITY FIX LIST")
        report.append("=" * 70)
        report.append("")

        # Group by file and count severity
        file_scores = {}
        for v in self.violations:
            if v.file_path not in file_scores:
                file_scores[v.file_path] = {"CRITICAL": 0, "HIGH": 0, "MEDIUM": 0, "LOW": 0}
            file_scores[v.file_path][v.severity] += 1

        # Calculate priority score (CRITICAL=4, HIGH=3, MEDIUM=2, LOW=1)
        severity_weights = {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}

        file_priorities = []
        for file_path, severities in file_scores.items():
            score = sum(severities[sev] * severity_weights[sev] for sev in severities)
            total_violations = sum(severities.values())
            file_priorities.append((file_path, score, total_violations, severities))

        # Sort by score (highest first)
        file_priorities.sort(key=lambda x: -x[1])

        report.append("Priority | File | Score | Violations | C | H | M | L |")
        report.append("---------|------|-------|------------|---|---|---|---|")

        for i, (file_path, score, total, severities) in enumerate(file_priorities[:30], 1):
            relative_path = file_path.relative_to(Path.cwd()) if file_path.is_relative_to(Path.cwd()) else file_path
            report.append(
                f"{i:8d} | {str(relative_path):50s} | {score:5d} | {total:10d} | "
                f"{severities['CRITICAL']:1d} | {severities['HIGH']:1d} | "
                f"{severities['MEDIUM']:1d} | {severities['LOW']:1d} |"
            )

        report.append("")
        report.append("Legend: C=Critical, H=High, M=Medium, L=Low")
        report.append("")

        return "\n".join(report)


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Theme system compliance linter")
    parser.add_argument("--directory", default="ui", help="Directory to scan (default: ui)")
    parser.add_argument("--file", help="Lint single file instead of directory")
    parser.add_argument("--strict", action="store_true", help="Exit with error code if violations found")
    parser.add_argument("--report", help="Save report to file")
    parser.add_argument("--summary-only", action="store_true", help="Show summary only (no details)")
    parser.add_argument("--priority-only", action="store_true", help="Show priority list only")
    args = parser.parse_args()

    linter = ThemeLinter()

    # Lint files
    if args.file:
        file_path = Path(args.file)
        violations = linter.lint_file(file_path)
        linter.violations = violations
    else:
        directory = Path(args.directory)
        if not directory.exists():
            print(f"Error: Directory not found: {directory}")
            return 1

        results = linter.lint_directory(directory)

    # Generate report
    if args.priority_only:
        report = linter.generate_priority_list()
    elif args.summary_only:
        report = linter.generate_summary()
    else:
        report = linter.generate_detailed_report()
        report += "\n\n"
        report += linter.generate_priority_list()

    # Output report
    print(report)

    # Save to file if requested
    if args.report:
        with open(args.report, "w", encoding="utf-8") as f:
            f.write(report)
        print(f"\nReport saved to: {args.report}")

    # Exit with error if strict mode and violations found
    if args.strict and linter.violations:
        return 1

    return 0


if __name__ == "__main__":
    exit(main())
