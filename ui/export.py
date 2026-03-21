"""Export functions for session data and reports."""

from __future__ import annotations

import csv
import json
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from app.services.tooling import get_tooling_service
from configs.settings import AppConfig
from contracts.tooling import TrainingReportRequest
from contracts.versioning import APP_VERSION, SCHEMA_VERSION
from ui.themes import show_message_dialog


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
    if config.upload.api_key:
        headers["x-api-key"] = config.upload.api_key
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")

    # Show progress dialog during upload
    progress = QtWidgets.QProgressDialog(
        f"Uploading session to {api_base}...",
        "Cancel",
        0,
        0,  # Indeterminate progress
        parent
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

    # Create progress dialog for longer exports
    progress = None
    if export_type in ("training_report", "manifests_zip"):
        progress = QtWidgets.QProgressDialog(
            f"Exporting {export_type.replace('_', ' ')}...",
            None,  # No cancel button for now
            0,
            0,  # Indeterminate
            parent
        )
        progress.setWindowTitle("Export Progress")
        progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
        progress.setMinimumDuration(250)  # Show if takes > 250ms
        progress.setValue(0)
        QtWidgets.QApplication.processEvents()

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
    finally:
        if progress:
            progress.close()


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
    src = session_dir / "session_summary.csv"
    if src.exists():
        shutil.copyfile(src, path)
        return
    write_session_summary_csv(Path(path), summary)


def write_session_summary_csv(path: Path, summary) -> None:
    """Write session summary to CSV file.

    Args:
        path: Output CSV file path
        summary: Session summary data with pitches list
    """
    with path.open("w", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(
            [
                "pitch_id",
                "t_start_ns",
                "t_end_ns",
                "is_strike",
                "zone_row",
                "zone_col",
                "run_in",
                "rise_in",
                "speed_mph",
                "rotation_rpm",
                "sample_count",
                "trajectory_plate_x_ft",
                "trajectory_plate_y_ft",
                "trajectory_plate_z_ft",
                "trajectory_plate_t_ns",
                "trajectory_model",
                "trajectory_expected_error_ft",
                "trajectory_confidence",
            ]
        )
        for pitch in summary.pitches:
            writer.writerow(
                [
                    pitch.pitch_id,
                    pitch.t_start_ns,
                    pitch.t_end_ns,
                    int(pitch.is_strike),
                    pitch.zone_row if pitch.zone_row is not None else "",
                    pitch.zone_col if pitch.zone_col is not None else "",
                    f"{pitch.run_in:.3f}",
                    f"{pitch.rise_in:.3f}",
                    f"{pitch.speed_mph:.3f}" if pitch.speed_mph is not None else "",
                    f"{pitch.rotation_rpm:.3f}" if pitch.rotation_rpm is not None else "",
                    pitch.sample_count,
                    f"{pitch.trajectory_plate_x_ft:.4f}" if getattr(pitch, "trajectory_plate_x_ft", None) is not None else "",
                    f"{pitch.trajectory_plate_y_ft:.4f}" if getattr(pitch, "trajectory_plate_y_ft", None) is not None else "",
                    f"{pitch.trajectory_plate_z_ft:.4f}" if getattr(pitch, "trajectory_plate_z_ft", None) is not None else "",
                    getattr(pitch, "trajectory_plate_t_ns", "") if getattr(pitch, "trajectory_plate_t_ns", None) is not None else "",
                    getattr(pitch, "trajectory_model", "") if getattr(pitch, "trajectory_model", None) is not None else "",
                    f"{getattr(pitch, 'trajectory_expected_error_ft', None):.4f}" if getattr(pitch, "trajectory_expected_error_ft", None) is not None else "",
                    f"{getattr(pitch, 'trajectory_confidence', None):.3f}" if getattr(pitch, "trajectory_confidence", None) is not None else "",
                ]
            )


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
    result = tooling.build_training_report(request)
    Path(path).write_text(json.dumps(result.payload, indent=2))


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

    # Collect files to export
    files: list[Path] = []
    manifest = session_dir / "manifest.json"
    summary_json = session_dir / "session_summary.json"
    summary_csv = session_dir / "session_summary.csv"
    if manifest.exists():
        files.append(manifest)
    if summary_json.exists():
        files.append(summary_json)
    if summary_csv.exists():
        files.append(summary_csv)
    files.extend(session_dir.rglob("*/manifest.json"))

    if not files:
        raise RuntimeError("No manifest files found to export.")

    # Show progress dialog for larger exports
    progress = QtWidgets.QProgressDialog(
        "Exporting manifest files...",
        "Cancel",
        0,
        len(files),
        parent
    )
    progress.setWindowTitle("Export Progress")
    progress.setWindowModality(QtCore.Qt.WindowModality.WindowModal)
    progress.setMinimumDuration(500)  # Only show if takes > 500ms

    try:
        with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for i, file_path in enumerate(files):
                if progress.wasCanceled():
                    # Clean up partial zip file
                    Path(path).unlink(missing_ok=True)
                    return

                progress.setValue(i)
                progress.setLabelText(f"Adding {file_path.name}... ({i+1}/{len(files)})")
                QtWidgets.QApplication.processEvents()

                archive.write(file_path, file_path.relative_to(session_dir))

            progress.setValue(len(files))
    finally:
        progress.close()


__all__ = [
    "upload_session",
    "save_session_export",
    "export_session_summary_json",
    "export_session_summary_csv",
    "write_session_summary_csv",
    "export_training_report",
    "export_manifests_zip",
]
