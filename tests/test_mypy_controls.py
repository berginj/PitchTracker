from __future__ import annotations

from pathlib import Path

from scripts.check_typing_policy import TEST_RELAXATIONS, policy_violations


def test_typing_policy_rejects_blanket_config_and_unqualified_ignore(tmp_path: Path) -> None:
    (tmp_path / "mypy.ini").write_text("[mypy-old.*]\nignore_errors = true\n", encoding="utf-8")
    unqualified_ignore = "# type:" + " ignore"
    (tmp_path / "bad.py").write_text(
        f"value = unknown  {unqualified_ignore}\n",
        encoding="utf-8",
    )

    violations = policy_violations(tmp_path)

    assert any("blanket ignore_errors" in violation for violation in violations)
    assert any("require one or more error codes" in violation for violation in violations)


def test_typing_policy_accepts_error_code_scoped_ignore(tmp_path: Path) -> None:
    (tmp_path / "good.py").write_text(
        "value = unknown  # type: ignore[name-defined]\n",
        encoding="utf-8",
    )

    assert policy_violations(tmp_path) == []


def test_typing_policy_rejects_unapproved_disable_error_code(tmp_path: Path) -> None:
    (tmp_path / "mypy.ini").write_text(
        "[mypy-app.*]\ndisable_error_code = attr-defined\n",
        encoding="utf-8",
    )

    violations = policy_violations(tmp_path)

    assert any("fixed test-only policy" in violation for violation in violations)


def test_typing_policy_accepts_fixed_test_relaxations(tmp_path: Path) -> None:
    codes = ", ".join(sorted(TEST_RELAXATIONS))
    (tmp_path / "mypy.ini").write_text(
        f"[mypy-tests.*]\ndisable_error_code = {codes}\n",
        encoding="utf-8",
    )

    assert policy_violations(tmp_path) == []
