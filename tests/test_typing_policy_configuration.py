"""Typing policy interprets effective settings, including inline comments."""

import pytest

from scripts.check_typing_policy import policy_violations


@pytest.mark.parametrize(
    "name,text",
    [
        ("mypy.ini", "[mypy]\nignore_errors = true # bypass\n"),
        ("setup.cfg", "[mypy]\nignore_errors = yes ; bypass\n"),
        ("pyproject.toml", "[tool.mypy]\nignore_errors = true # bypass\n"),
        ("pyproject.toml", '[[tool.mypy.overrides]]\nmodule = "app.*"\nignore_errors = true\n'),
    ],
)
def test_effective_blanket_suppression_is_rejected(tmp_path, name, text):
    (tmp_path / name).write_text(text)
    assert any("blanket" in item for item in policy_violations(tmp_path))


def test_comment_only_settings_and_unrelated_tools_are_not_suppressions(tmp_path):
    (tmp_path / "setup.cfg").write_text("[mypy]\n# ignore_errors = true\n[other]\nignore_errors = true\n")
    assert policy_violations(tmp_path) == []
