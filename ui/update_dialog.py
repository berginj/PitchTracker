"""Update dialog for PitchTracker auto-updater."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtWidgets

from log_config.logger import get_logger
from updater import download_update, get_current_version, install_update
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
        if self._downloading:
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
        self._download_thread.finished.connect(self._on_download_finished)
        self._download_thread.error.connect(self._on_download_error)
        self._download_thread.start()

    def _on_progress(self, bytes_downloaded: int, total_bytes: int) -> None:
        """Update progress bar."""
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
                QtWidgets.QApplication.quit()
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
            from pathlib import Path
            import json

            settings_file = Path("configs") / "update_settings.json"
            settings_file.parent.mkdir(exist_ok=True)

            settings = {}
            if settings_file.exists():
                with open(settings_file) as f:
                    settings = json.load(f)

            settings["skipped_version"] = self._update_info["version"]

            with open(settings_file, "w") as f:
                json.dump(settings, f, indent=2)

        except Exception:
            logger.exception("Failed to save skipped updater version")


class DownloadThread(QtCore.QThread):
    """Background thread for downloading update."""

    progress = QtCore.Signal(int, int)  # bytes_downloaded, total_bytes
    finished = QtCore.Signal(Path)  # installer_path
    error = QtCore.Signal(str)  # error_message

    def __init__(self, url: str, expected_sha256: Optional[str] = None):
        super().__init__()
        self._url = url
        self._expected_sha256 = expected_sha256

    def run(self) -> None:
        """Download update in background."""
        try:

            def progress_callback(downloaded, total):
                self.progress.emit(downloaded, total)

            installer_path = download_update(
                self._url,
                progress_callback=progress_callback,
                expected_sha256=self._expected_sha256,
                require_checksum=True,
            )

            if installer_path:
                self.finished.emit(installer_path)
            elif not self._expected_sha256:
                self.error.emit(
                    "Update aborted: this release has no SHA-256 checksum, so the "
                    "installer could not be verified. Please download it manually "
                    "from GitHub releases."
                )
            else:
                self.error.emit("Download failed or integrity verification failed")

        except Exception as e:
            self.error.emit(str(e))
