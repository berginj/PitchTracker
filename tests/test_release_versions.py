"""Release version alignment checks."""

from scripts.check_release_versions import main


def test_release_versions_are_aligned():
    assert main() == 0
