"""Cancelled exports preserve existing targets and remove only temporary files."""

from concurrent.futures import CancelledError
import json
from threading import Event
import zipfile

import pytest

from app.services.tooling.export_artifacts import export_json, export_manifest_archive


def test_precancelled_archive_preserves_existing_destination(tmp_path):
    root = tmp_path / "session"
    root.mkdir()
    (root / "manifest.json").write_text("{}")
    output = tmp_path / "export.zip"
    output.write_bytes(b"previous export")
    cancel = Event()
    cancel.set()
    with pytest.raises(CancelledError):
        export_manifest_archive(output, root, cancel)
    assert output.read_bytes() == b"previous export"


def test_cancel_inside_archive_cleans_partial_and_preserves_sources(tmp_path, monkeypatch):
    root = tmp_path / "session"
    root.mkdir()
    (root / "manifest.json").write_text("{}")
    output = tmp_path / "export.zip"
    output.write_bytes(b"previous")
    cancel = Event()
    original_open = zipfile.ZipFile.open

    def cancelling_open(self, *args, **kwargs):
        result = original_open(self, *args, **kwargs)
        cancel.set()
        return result

    monkeypatch.setattr(zipfile.ZipFile, "open", cancelling_open)
    with pytest.raises(CancelledError):
        export_manifest_archive(output, root, cancel)
    assert output.read_bytes() == b"previous"
    assert sorted(path.name for path in tmp_path.iterdir()) == ["export.zip", "session"]
    assert (root / "manifest.json").read_text() == "{}"


def test_archive_contains_only_selected_session_metadata(tmp_path):
    root = tmp_path / "session"
    root.mkdir()
    (root / "manifest.json").write_text("{}")
    (root / "athlete.avi").write_bytes(b"private")
    pitch = root / "pitch_00001"
    pitch.mkdir()
    (pitch / "manifest.json").write_text("{}")
    output = tmp_path / "export.zip"
    export_manifest_archive(output, root, Event())
    with zipfile.ZipFile(output) as archive:
        assert archive.namelist() == ["manifest.json", "pitch_00001/manifest.json"]


def test_json_export_rejects_source_overwrite_and_publishes_complete_output(tmp_path):
    root = tmp_path / "session"
    root.mkdir()
    with pytest.raises(ValueError, match="outside"):
        export_json(root / "manifest.json", {}, root, Event())
    output = tmp_path / "report.json"
    export_json(output, {"valid": True}, root, Event())
    assert json.loads(output.read_text()) == {"valid": True}
