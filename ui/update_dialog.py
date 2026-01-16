"""Update dialog for PitchTracker auto-updater."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets

from updater import download_update, get_current_version, install_update


class UpdateDialog(QtWidgets.QDialog):
    """Dialog showing available update with download/install options."""

    def __init__(
        self,
        update_info: dict,
        parent: Optional[QtWidgets.QWidget] = None
    ):
        super().__init__(parent)
        self.setWindowTitle("Update Available")
        self.resize(600, 500)

        self._update_info = update_info
        self._download_path: Optional[Path] = None
        self._downloading = False

        self._build_ui()

    def _build_ui(self) -> None:
        """Build update dialog UI."""
        layout = QtWidgets.QVBoxLayout()

        # Header with icon and title
        header = self._build_header()
        layout.addWidget(header)

        # Version information
        version_info = self._build_version_info()
        layout.addWidget(version_info)

        # Release notes
        notes_label = QtWidgets.QLabel("Release Notes:")
        notes_label.setStyleSheet("font-weight: bold; margin-top: 10px;")
        layout.addWidget(notes_label)

        self._release_notes = QtWidgets.QTextEdit()
        self._release_notes.setReadOnly(True)
        self._release_notes.setMarkdown(self._update_info['release_notes'])
        self._release_notes.setMaximumHeight(200)
        layout.addWidget(self._release_notes)

        # Progress bar (hidden initially)
        self._progress_bar = QtWidgets.QProgressBar()
        self._progress_bar.setVisible(False)
        layout.addWidget(self._progress_bar)

        # Status label
        self._status_label = QtWidgets.QLabel("")
        self._status_label.setStyleSheet("color: #666; font-size: 9pt;")
        layout.addWidget(self._status_label)

        # Buttons
        buttons = self._build_buttons()
        layout.addWidget(buttons)

        self.setLayout(layout)

    def _build_header(self) -> QtWidgets.QWidget:
        """Build header section with icon and title."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QHBoxLayout()

        # Icon (using standard info icon)
        icon_label = QtWidgets.QLabel()
        icon = self.style().standardIcon(QtWidgets.QStyle.StandardPixmap.SP_MessageBoxInformation)
        pixmap = icon.pixmap(64, 64)
        icon_label.setPixmap(pixmap)
        layout.addWidget(icon_label)

        # Title and message
        text_layout = QtWidgets.QVBoxLayout()

        title = QtWidgets.QLabel("Update Available")
        title.setStyleSheet("font-size: 16pt; font-weight: bold;")
        text_layout.addWidget(title)

        message = QtWidgets.QLabel(
            "A new version of PitchTracker is available.\n"
            "Click 'Download and Install' to update now."
        )
        text_layout.addWidget(message)

        text_layout.addStretch()

        layout.addLayout(text_layout, 1)
        widget.setLayout(layout)

        return widget

    def _build_version_info(self) -> QtWidgets.QWidget:
        """Build version comparison section."""
        widget = QtWidgets.QWidget()
        layout = QtWidgets.QGridLayout()

        # Current version
        current_label = QtWidgets.QLabel("Current Version:")
        current_label.setStyleSheet("font-weight: bold;")
        current_version = QtWidgets.QLabel(f"v{get_current_version()}")
        layout.addWidget(current_label, 0, 0)
        layout.addWidget(current_version, 0, 1)

        # Latest version
        latest_label = QtWidgets.QLabel("Latest Version:")
        latest_label.setStyleSheet("font-weight: bold;")
        latest_version = QtWidgets.QLabel(f"v{self._update_info['version']}")
        latest_version.setStyleSheet("color: #4CAF50; font-weight: bold;")
        layout.addWidget(latest_label, 1, 0)
        layout.addWidget(latest_version, 1, 1)

        # Release date
        if self._update_info['release_date']:
            date_label = QtWidgets.QLabel("Released:")
            date_label.setStyleSheet("font-weight: bold;")
            # Parse ISO 8601 date
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(self._update_info['release_date'].replace('Z', '+00:00'))
                date_str = dt.strftime("%B %d, %Y")
            except Exception:
                date_str = self._update_info['release_date']
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

        # Download and Install button
        self._download_button = QtWidgets.QPushButton("Download and Install")
        self._download_button.setStyleSheet(
            "font-size: 11pt; padding: 10px 20px; "
            "background-color: #4CAF50; color: white; font-weight: bold;"
        )
        self._download_button.clicked.connect(self._download_and_install)

        # Remind Me Later button
        remind_button = QtWidgets.QPushButton("Remind Me Later")
        remind_button.clicked.connect(self.reject)

        # Skip This Version button
        skip_button = QtWidgets.QPushButton("Skip This Version")
        skip_button.clicked.connect(self._skip_version)
        skip_button.setStyleSheet("color: #999;")

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
        self._status_label.setText("Downloading update...")

        # Download in background thread
        self._download_thread = DownloadThread(
            self._update_info['download_url']
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
            self._status_label.setText(
                f"Downloading... {mb_downloaded:.1f} MB / {mb_total:.1f} MB"
            )

    def _on_download_finished(self, installer_path: Path) -> None:
        """Download completed successfully."""
        self._download_path = installer_path
        self._status_label.setText("Download complete!")

        # Ask user to install now
        reply = QtWidgets.QMessageBox.question(
            self,
            "Install Update",
            "Download complete. Install update now?\n\n"
            "The application will close and the installer will launch.",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
            # Launch installer
            if install_update(installer_path):
                # Close application to allow installer to replace files
                self.accept()
                QtWidgets.QApplication.quit()
            else:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Install Error",
                    "Failed to launch installer. Please run it manually:\n" +
                    str(installer_path)
                )
        else:
            QtWidgets.QMessageBox.information(
                self,
                "Install Later",
                f"Installer saved to:\n{installer_path}\n\n"
                "Run it when you're ready to update."
            )
            self.accept()

    def _on_download_error(self, error_msg: str) -> None:
        """Download failed."""
        self._downloading = False
        self._download_button.setEnabled(True)
        self._progress_bar.setVisible(False)
        self._status_label.setText("")

        QtWidgets.QMessageBox.critical(
            self,
            "Download Error",
            f"Failed to download update:\n{error_msg}\n\n"
            "Please download manually from GitHub releases."
        )

    def _skip_version(self) -> None:
        """Skip this version."""
        reply = QtWidgets.QMessageBox.question(
            self,
            "Skip Version",
            f"Skip version v{self._update_info['version']}?\n\n"
            "You won't be notified about this version again.",
            QtWidgets.QMessageBox.StandardButton.Yes |
            QtWidgets.QMessageBox.StandardButton.No
        )

        if reply == QtWidgets.QMessageBox.StandardButton.Yes:
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

            settings['skipped_version'] = self._update_info['version']

            with open(settings_file, 'w') as f:
                json.dump(settings, f, indent=2)

        except Exception as e:
            print(f"Failed to save skipped version: {e}")


class DownloadThread(QtCore.QThread):
    """Background thread for downloading update."""

    progress = QtCore.Signal(int, int)  # bytes_downloaded, total_bytes
    finished = QtCore.Signal(Path)      # installer_path
    error = QtCore.Signal(str)          # error_message

    def __init__(self, url: str):
        super().__init__()
        self._url = url

    def run(self) -> None:
        """Download update in background."""
        try:
            def progress_callback(downloaded, total):
                self.progress.emit(downloaded, total)

            installer_path = download_update(
                self._url,
                progress_callback=progress_callback
            )

            if installer_path:
                self.finished.emit(installer_path)
            else:
                self.error.emit("Download failed")

        except Exception as e:
            self.error.emit(str(e))
