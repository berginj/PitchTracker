"""Documentation moves must preserve links across Windows and case-sensitive hosts."""

from datetime import date
import subprocess

from scripts import check_public_docs as docs


def test_git_inventory_includes_new_docs_but_excludes_ignored_local_material(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".gitignore").write_text("archive/local/\n", encoding="utf-8")
    (tmp_path / "AGENTS.md").write_text("Instructions", encoding="utf-8")
    for relative in ("docs/new.md", "archive/local/probe.md", "archive/docs/old.md", "docs/review/run.md"):
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("Content", encoding="utf-8")
    paths = docs.repository_files(tmp_path)
    assert "archive/local/probe.md" not in paths
    assert docs.maintained_markdown(paths) == ["AGENTS.md", "docs/new.md"]


def test_links_support_images_references_titles_fragments_and_encoded_spaces():
    text = """
[guide](../AGENTS.md#scope "Instructions")
![image](<images/empty view.png>)
[reference]: ../README.md "Overview"
[web](https://example.com/reference)
```markdown
[example](missing-example.md)
Last reviewed: 9999-12-31
```
~~~text
[also an example](missing.md)
~~~
Inline code: `[literal target](missing-inline-example.md)`.
"""
    paths = {"AGENTS.md", "README.md", "docs/images/empty view.png", "docs/guide.md"}
    for target in docs.link_targets(text):
        assert docs.link_error("docs/guide.md", target, paths) is None
    assert docs.link_error("docs/guide.md", "images/empty%20view.png", paths) is None
    assert docs.link_error("docs/guide.md", "#section", paths) is None


def test_case_sensitive_links_and_root_agent_name_are_checked_on_windows():
    paths = {"AGENTS.md", "docs/guide.md"}
    assert "case differs" in docs.link_error("docs/guide.md", "../agents.md", paths)
    assert docs.link_error("AGENTS.md", "docs/", paths) is None
    assert "case differs" in docs.link_error("AGENTS.md", "Docs/", paths)
    assert docs.instruction_errors(paths) == []
    assert docs.instruction_errors({"agents.md"})


def test_missing_and_outside_targets_fail_without_reading_local_private_files():
    paths = {"README.md", "docs/guide.md"}
    assert "missing" in docs.link_error("docs/guide.md", "missing.md", paths)
    assert "escapes" in docs.link_error("docs/guide.md", "../../private.md", paths)
    assert docs.link_error("docs/guide.md", "/", paths) is None


def test_archived_instructions_are_rejected_but_historical_prose_is_not_active():
    paths = {"AGENTS.md", "archive/docs/reference/AGENTS.md", docs.ARCHIVE_INDEX}
    assert len(docs.instruction_errors(paths)) == 1
    assert docs.maintained_markdown(paths) == ["AGENTS.md", docs.ARCHIVE_INDEX]


def test_document_reports_bad_dates_and_preserves_historical_examples(tmp_path):
    page = tmp_path / "README.md"
    page.write_text(
        "Last reviewed: 2026-02-30\nLast updated: 2027-01-01\n"
        "```text\nLast reviewed: 9999-12-31\n```\n",
        encoding="utf-8",
    )
    errors = docs.check_document(tmp_path, "README.md", {"README.md"}, date(2026, 10, 16))
    assert len(errors) == 2
    assert any("invalid review date" in error for error in errors)
    assert any("future review date" in error for error in errors)


def test_invalid_encoding_and_broken_links_return_actionable_errors(tmp_path):
    page = tmp_path / "README.md"
    page.write_bytes(b"old \x97 encoding")
    assert "UTF-8" in docs.check_document(tmp_path, "README.md", {"README.md"}, date(2026, 10, 16))[0]
    page.write_text("[missing](docs/missing.md)", encoding="utf-8")
    errors = docs.check_document(tmp_path, "README.md", {"README.md"}, date(2026, 10, 16))
    assert len(errors) == 1 and "docs/missing.md" in errors[0]


def test_main_fails_for_broken_new_nested_guide(tmp_path, monkeypatch, capsys):
    (tmp_path / "AGENTS.md").write_text("Instructions", encoding="utf-8")
    (tmp_path / "README.md").write_text("Overview", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs/new.md").write_text("[missing](missing.md)", encoding="utf-8")
    paths = {"AGENTS.md", "README.md", "docs/new.md"}
    monkeypatch.setattr(docs, "ROOT", tmp_path)
    monkeypatch.setattr(docs, "REQUIRED_FILES", ("AGENTS.md", "README.md"))
    monkeypatch.setattr(docs, "ISSUE_TEMPLATES", ())
    monkeypatch.setattr(docs, "repository_files", lambda root: paths)
    assert docs.main() == 1
    assert "docs/new.md -> missing.md" in capsys.readouterr().err
    (tmp_path / "docs/new.md").write_text("[instructions](../AGENTS.md)", encoding="utf-8")
    assert docs.main() == 0
