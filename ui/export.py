"""Export functions for session data and reports."""

from __future__ import annotations

import json
import shutil
import time
import urllib.error
import urllib.request
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.services.tooling import get_tooling_service
from app.pipeline.recording.summary_csv import write_summary_csv
from configs.settings import AppConfig
from contracts.tooling import TrainingReportRequest
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from ui.themes import show_message_dialog
from ui.tooling_task import run_tooling_task
from app.services.tooling.export_artifacts import export_json, export_manifest_archive


def upload_session(
    parent: QtWidgets.QWidget,
    summary,
    config: AppConfig,
    session_dir: Optional[Path],
    pitcher_name: str,
    location_profile: str,
) -> None:
    """Upload session data to remote API.

    Args:
        parent: Parent widget for message boxes
        summary: Session summary data
        config: Application configuration
        session_dir: Session directory path
        pitcher_name: Current pitcher name
        location_profile: Current location profile name
    """
    if not config.upload.enabled:
        show_message_dialog(
            parent,
            "Upload Session",
            "Uploads are disabled. Enable upload in configs/default.yaml.",
            tone="info",
        )
        return
    api_base = config.upload.swa_api_base.rstrip("/")
    if not api_base:
        show_message_dialog(
            parent,
            "Upload Session",
            "Upload URL is not configured.",
            tone="warning",
        )
        return
    if not api_base.startswith("https://"):
        show_message_dialog(
            parent,
            "Upload Session",
            "Upload URL must use HTTPS to protect data in transit.",
            tone="warning",
        )
        return

    marker_spec = None
    if session_dir:
        marker_path = Path(session_dir) / "marker_spec.json"
        if marker_path.exists():
            marker_spec = json.loads(marker_path.read_text())

    payload = {
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "session": asdict(summary),
        "metadata": {
            "uploaded_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "pitcher": pitcher_name,
            "location_profile": location_profile,
            "rig_id": None,
            "source": "PitchTracker",
        },
        "marker_spec": marker_spec,
    }
    data = json.dumps(payload).encode("utf-8")
    url = f"{api_base}/sessions"
    headers = {"Content-Type": "application/json"}
    api_key = _resolve_api_key(config)
    if api_key:
        headers["x-api-key"] = api_key
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    # Show progress dialog during upload
    progress = QtWidgets.QProgressDialog(
        f"Uploading session to {api_base}...", "Cancel", 0, 0, parent  # Indeterminate progress
    )
    progress.setWindowTitle("Upload Progress")
    progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(0)  # Show immediately
    progress.setValue(0)
    QtWidgets.QApplication.processEvents()

    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            progress.setLabelText("Upload complete, processing response...")
            QtWidgets.QApplication.processEvents()

            if response.status >= 400:
                raise RuntimeError(f"Upload failed: HTTP {response.status}")

        progress.setValue(1)
        show_message_dialog(parent, "Upload Session", "Upload complete.", tone="success")
    except (urllib.error.URLError, RuntimeError) as exc:
        show_message_dialog(parent, "Upload Session", f"Upload failed: {exc}", tone="warning")
        return
    finally:
        progress.close()


def save_session_export(
    parent: QtWidgets.QWidget,
    summary,
    session_dir: Optional[Path],
    export_type: Optional[str],
    config_path: Path,
    roi_path: Path,
    pitcher_name: str,
    location_profile: str,
) -> None:
    """Save session export in specified format.

    Args:
        parent: Parent widget for message boxes
        summary: Session summary data
        session_dir: Session directory path
        export_type: Export format (summary_json, summary_csv, training_report, manifests_zip)
        config_path: Configuration file path
        roi_path: ROI configuration file path
        pitcher_name: Current pitcher name
        location_profile: Current location profile name
    """
    if session_dir is None:
        show_message_dialog(
            parent,
            "Save Session",
            "No session directory available for export.",
            tone="warning",
        )
        return
    if not export_type:
        show_message_dialog(
            parent,
            "Save Session",
            "Select an export type before saving.",
            tone="warning",
        )
        return

    try:
        if export_type == "summary_json":
            export_session_summary_json(parent, summary, session_dir)
        elif export_type == "summary_csv":
            export_session_summary_csv(parent, summary, session_dir)
        elif export_type == "training_report":
            export_training_report(
                parent,
                session_dir,
                config_path,
                roi_path,
                pitcher_name,
                location_profile,
            )
        elif export_type == "manifests_zip":
            export_manifests_zip(parent, session_dir)
        else:
            show_message_dialog(
                parent,
                "Save Session",
                f"Unknown export type: {export_type}",
                tone="warning",
            )
    except Exception as exc:  # noqa: BLE001 - surface export failures
        show_message_dialog(parent, "Save Session", str(exc), tone="warning")


def export_session_summary_json(
    parent: QtWidgets.QWidget,
    summary,
    session_dir: Path,
) -> None:
    """Export session summary as JSON file.

    Args:
        parent: Parent widget for file dialog
        summary: Session summary data
        session_dir: Session directory path
    """
    default_name = "session_summary.json"
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent,
        "Save Session Summary (JSON)",
        default_name,
        "JSON files (*.json)",
    )
    if not path:
        return
    src = session_dir / "session_summary.json"
    if src.exists():
        shutil.copyfile(src, path)
        return
    payload = asdict(summary)
    payload["schema_version"] = SCHEMA_VERSION
    payload["app_version"] = APP_VERSION
    Path(path).write_text(json.dumps(payload, indent=2))


def export_session_summary_csv(
    parent: QtWidgets.QWidget,
    summary,
    session_dir: Path,
) -> None:
    """Export session summary as CSV file.

    Args:
        parent: Parent widget for file dialog
        summary: Session summary data
        session_dir: Session directory path
    """
    default_name = "session_summary.csv"
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent,
        "Save Session Summary (CSV)",
        default_name,
        "CSV files (*.csv)",
    )
    if not path:
        return
    # Rebuild old recordings' exports with explicit semantics; leave the stored
    # artifact unchanged. The loaded summary preserves unavailable legacy fields.
    write_session_summary_csv(Path(path), summary)


def write_session_summary_csv(path: Path, summary) -> None:
    """Write compatible pitch columns and explicit measurement provenance."""
    write_summary_csv(path, summary)


def export_training_report(
    parent: QtWidgets.QWidget,
    session_dir: Path,
    config_path: Path,
    roi_path: Path,
    pitcher_name: str,
    location_profile: str,
) -> None:
    """Export training report JSON for ML training.

    Args:
        parent: Parent widget for file dialog
        session_dir: Session directory path
        config_path: Configuration file path
        roi_path: ROI configuration file path
        pitcher_name: Current pitcher name
        location_profile: Current location profile name
    """
    default_name = "training_report.json"
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent,
        "Save Training Report",
        default_name,
        "JSON files (*.json)",
    )
    if not path:
        return
    tooling = get_tooling_service()
    request = TrainingReportRequest(
        session_dir=session_dir,
        config_path=config_path,
        roi_path=roi_path,
        source={
            "app": "PitchTracker",
            "rig_id": None,
            "pitcher": pitcher_name,
            "location_profile": location_profile,
            "operator": None,
            "host": None,
        },
    )

    def operation(cancel_event):
        result = tooling.build_training_report_with_cancellation(request, cancel_event)
        return export_json(Path(path), result.payload, session_dir, cancel_event)

    run_tooling_task(parent, "Export training report", operation)


def export_manifests_zip(
    parent: QtWidgets.QWidget,
    session_dir: Path,
) -> None:
    """Export session manifest files as ZIP archive.

    Args:
        parent: Parent widget for file dialog
        session_dir: Session directory path
    """
    default_name = "session_manifests.zip"
    path, _ = QtWidgets.QFileDialog.getSaveFileName(
        parent,
        "Save Session Manifests",
        default_name,
        "Zip files (*.zip)",
    )
    if not path:
        return

    run_tooling_task(parent, "Export manifests", lambda cancel_event: export_manifest_archive(
        Path(path), session_dir, cancel_event,
    ))


def _resolve_api_key(config: AppConfig) -> str:
    """Resolve API key from OS credential store, falling back to config file.

    Checks the OS keyring first (Windows Credential Manager / macOS Keychain).
    Falls back to the plaintext api_key in config if keyring is unavailable.

    Returns:
        API key string, or empty string if none configured.
    """
    try:
        import keyring

        stored = keyring.get_password("PitchTracker", "upload_api_key")
        if stored:
            return str(stored)
    except Exception:
        pass
    return config.upload.api_key


__all__ = [
    "upload_session",
    "save_session_export",
    "export_session_summary_json",
    "export_session_summary_csv",
    "write_session_summary_csv",
    "export_training_report",
    "export_manifests_zip",
]
