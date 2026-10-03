"""Update dialog for PitchTracker auto-updater."""

from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Optional

from PySide6 import QtCore, QtWidgets

from log_config.logger import get_logger
from updater import (
    download_update, get_current_version, install_update,
    _read_update_settings, _write_update_settings,
)
from ui.themes import (
    apply_standard_layout,
    ask_confirmation,
    build_dialog_header,
    get_style_manager,
    polish_form_controls,
    show_message_dialog,
    style_message_panel,
    style_progress_bar,
    style_status_label,
)

logger = get_logger(__name__)


class UpdateDialog(QtWidgets.QDialog):
    """Dialog showing available update with download/install options."""

    def __init__(self, update_info: dict, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self._style_manager = get_style_manager()
        self.setWindowTitle("Update Available")
        self.resize(600, 500)

        self._update_info = update_info
        self._download_path: Optional[Path] = None
        self._downloading = False
        self._download_thread: DownloadThread | None = None
        self._pending_close: int | None = None
        self._closing = False
        self._download_result: Path | None = None
        self._download_error: str | None = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build update dialog UI."""
        layout = QtWidgets.QVBoxLayout()
        apply_standard_layout(layout)

        header = build_dialog_header(
            "Update Available",
            "A new version of PitchTracker is ready to download.",
            eyebrow="Updater",
        )
        layout.addWidget(header)

        # Version information
        version_info = self._build_version_info()
        layout.addWidget(version_info)

        # Release notes
        notes_label = QtWidgets.QLabel("Release Notes:")
        self._style_manager.style_label(notes_label, "sectionTitle")
        layout.addWidget(notes_label)

        self._release_notes = QtWidgets.QTextEdit()
        self._release_notes.setReadOnly(True)
        self._release_notes.setMarkdown(self._update_info["release_notes"])
        self._release_notes.setMaximumHeight(200)
        style_message_panel(self._release_notes, "info")
        layout.addWidget(self._release_notes)

        # Progress bar (hidden initially)
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setVisible(False)
        style_progress_bar(self._progress_bar, "success")
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QtWidgets.QLabel("")
        style_status_label(self._status_label, "info", "Ready to download the latest release.")
        layout.addWidget(self._status_label)

        # Buttons
        buttons = self._build_buttons()
        layout.addWidget(buttons)

        self.setLayout(layout)
        polish_form_controls(self)

    def _build_version_info(self) -> QtWidgets.QWidget:
        """Build version comparison section."""
        widget = QtWidgets.QWidget()
        self._style_manager.style_panel(widget, "normal")
        layout = QtWidgets.QGridLayout()

        # Current version
        current_label = QtWidgets.QLabel("Current Version:")
        self._style_manager.style_label(current_label, "muted")
        current_version = QtWidgets.QLabel(f"v{get_current_version()}")
        self._style_manager.style_label(current_version, "default")
        layout.addWidget(current_label, 0, 0)
        layout.addWidget(current_version, 0, 1)

        # Latest version
        latest_label = QtWidgets.QLabel("Latest Version:")
        self._style_manager.style_label(latest_label, "muted")
        latest_version = QtWidgets.QLabel(f"v{self._update_info['version']}")
        self._style_manager.style_label(latest_version, "accent")
        layout.addWidget(latest_label, 1, 0)
        layout.addWidget(latest_version, 1, 1)

        # Release date
        if self._update_info["release_date"]:
            date_label = QtWidgets.QLabel("Released:")
            self._style_manager.style_label(date_label, "muted")
            # Parse ISO 8601 date
            try:
                from datetime import datetime

                dt = datetime.fromisoformat(self._update_info["release_date"].replace("Z", "+00:00"))
                date_str = dt.strftime("%B %d, %Y")
            except Exception:
                date_str = self._update_info["release_date"]
            date_value = QtWidgets.QLabel(date_str)
            layout.addWidget(date_label, 2, 0)
            layout.addWidget(date_value, 2, 1)

        layout.setColumnStretch(1, 1)
        widget.setLayout(layout)

        return widget

    def _build_buttons(self) -> QtWidgets.QWidget:
        """Build button bar."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()
        layout.setContentsMargins(0, 4, 0, 0)

        # Download and Install button
        self._download_button = QtWidgets.QPushButton("Download and Install")
        self._style_manager.style_button(self._download_button, "primary")
        self._download_button.clicked.connect(self._download_and_install)

        # Remind Me Later button
        remind_button = QtWidgets.QPushButton("Remind Me Later")
        self._style_manager.style_button(remind_button, "ghost")
        remind_button.clicked.connect(self.reject)

        # Skip This Version button
        skip_button = QtWidgets.QPushButton("Skip This Version")
        skip_button.clicked.connect(self._skip_version)
        self._style_manager.style_button(skip_button, "ghost")

        layout.addWidget(self._download_button)
        layout.addWidget(remind_button)
        layout.addStretch()
        layout.addWidget(skip_button)

        widget.setLayout(layout)

        return widget

    def _download_and_install(self) -> None:
        """Download update and launch installer."""
        if self._download_thread is not None or self._closing:
            return

        self._downloading = True
        self._download_button.setEnabled(False)
        self._progress_bar.setVisible(True)
        style_status_label(self._status_label, "warning", "Downloading update...")

        # Download in background thread
        self._download_thread = DownloadThread(
            self._update_info["download_url"],
            expected_sha256=self._update_info.get("expected_sha256"),
        )
        self._download_thread.progress.connect(self._on_progress)
        self._download_result = None
        self._download_error = None
        self._download_thread.downloaded.connect(self._on_download_finished)
        self._download_thread.error.connect(self._on_download_error)
        self._download_thread.finished.connect(self._on_download_thread_finished)
        self._download_thread.start()

    def _on_progress(self, bytes_downloaded: int, total_bytes: int) -> None:
        """Update progress bar."""
        if self._pending_close is not None:
            return
        if total_bytes > 0:
            progress = int((bytes_downloaded / total_bytes) * 100)
            self._progress_bar.setValue(progress)

            # Update status text
            mb_downloaded = bytes_downloaded / (1024 * 1024)
            mb_total = total_bytes / (1024 * 1024)
            self._status_label.setText(f"Downloading... {mb_downloaded:.1f} MB / {mb_total:.1f} MB")
            style_status_label(
                self._status_label,
                "warning",
                f"Downloading... {mb_downloaded:.1f} MB / {mb_total:.1f} MB",
            )

    def _on_download_finished(self, installer_path: Path) -> None:
        """Retain the result until the worker's native terminal signal arrives."""
        if self._pending_close is None:
            self._download_result = installer_path

    def _on_download_thread_finished(self) -> None:
        """Release worker ownership only after run() has fully returned."""
        thread = self._download_thread
        if thread is not None:
            thread.wait()
            self._download_thread = None
            thread.deleteLater()
        self._downloading = False
        if self._pending_close is not None:
            result = self._pending_close
            self._pending_close = None
            super().done(result)
        elif self._download_result is not None:
            self._present_download(self._download_result)
        elif self._download_error is not None:
            self._present_download_error(self._download_error)

    def done(self, result: int) -> None:
        """Defer accept/reject until the owned download has terminated."""
        self._closing = True
        if self._download_thread is not None:
            self._pending_close = result
            self._download_thread.cancel()
            style_status_label(self._status_label, "warning", "Cancelling update download...")
            return
        super().done(result)

    def reject(self) -> None:
        self.done(int(QtWidgets.QDialog.DialogCode.Rejected))

    def accept(self) -> None:
        self.done(int(QtWidgets.QDialog.DialogCode.Accepted))

    def closeEvent(self, event) -> None:
        if self._download_thread is not None:
            event.ignore()
            self.reject()
        else:
            super().closeEvent(event)

    def _present_download(self, installer_path: Path) -> None:
        """Download completed successfully."""
        self._download_path = installer_path
        style_status_label(self._status_label, "success", "Download complete!")

        # Ask user to install now
        install_now = ask_confirmation(
            self,
            "Install Update",
            "Download complete. Install update now?",
            informative_text="The application will close and the installer will launch.",
        )

        if install_now:
            # Launch installer
            if install_update(installer_path):
                # Close application to allow installer to replace files
                self.accept()
                parent = self.parentWidget()
                if parent is not None:
                    parent.close()
            else:
                show_message_dialog(
                    self,
                    "Install Error",
                    "Failed to launch installer.",
                    tone="error",
                    informative_text=f"Please run it manually:\n{installer_path}",
                )
        else:
            show_message_dialog(
                self,
                "Install Later",
                f"Installer saved to:\n{installer_path}\n\n" "Run it when you're ready to update.",
                tone="info",
            )
            self.accept()

    def _on_download_error(self, error_msg: str) -> None:
        """Retain failure until the worker is terminal; retries then become safe."""
        if self._pending_close is None:
            self._download_error = error_msg

    def _present_download_error(self, error_msg: str) -> None:
        """Download failed."""
        self._downloading = False
        self._download_button.setEnabled(True)
        self._progress_bar.setVisible(False)
        style_status_label(self._status_label, "error", "Download failed.")

        show_message_dialog(
            self,
            "Download Error",
            f"Failed to download update:\n{error_msg}",
            tone="error",
            informative_text="Please download manually from GitHub releases.",
        )

    def _skip_version(self) -> None:
        """Skip this version."""
        should_skip = ask_confirmation(
            self,
            "Skip Version",
            f"Skip version v{self._update_info['version']}?",
            informative_text="You won't be notified about this version again.",
        )

        if should_skip:
            # Save skipped version to settings
            self._save_skipped_version()
            self.reject()

    def _save_skipped_version(self) -> None:
        """Save skipped version to settings file."""
        try:
            settings = _read_update_settings()
            settings["skipped_version"] = self._update_info["version"]

            _write_update_settings(settings)

        except Exception:
            logger.exception("Failed to save skipped updater version")


class DownloadThread(QtCore.QThread):
    """Background thread for downloading update."""

    progress = QtCore.Signal(int, int)  # bytes_downloaded, total_bytes
    downloaded = QtCore.Signal(object)  # installer_path; native finished remains terminal
    error = QtCore.Signal(str)  # error_message

    def __init__(self, url: str, expected_sha256: Optional[str] = None):
        super().__init__()
        self._url = url
        self._expected_sha256 = expected_sha256
        self._cancel_event = Event()

    def cancel(self) -> None:
        self._cancel_event.set()
        self.requestInterruption()

    def run(self) -> None:
        """Download update in background."""
        try:
            if self._cancel_event.is_set():
                return

            def progress_callback(downloaded, total):
                self.progress.emit(downloaded, total)

            installer_path = download_update(
                self._url,
                progress_callback=progress_callback,
                expected_sha256=self._expected_sha256,
                require_checksum=True,
                cancel_event=self._cancel_event,
            )

            if self._cancel_event.is_set():
                return
            if installer_path:
                self.downloaded.emit(installer_path)
            elif not self._expected_sha256:
                self.error.emit(
                    "Update aborted: this release has no SHA-256 checksum, so the "
                    "installer could not be verified. Please download it manually "
                    "from GitHub releases."
                )
            else:
                self.error.emit("Download failed or integrity verification failed")

        except Exception as e:
            logger.exception("Update download worker failed")
            if not self._cancel_event.is_set():
                self.error.emit(str(e))
