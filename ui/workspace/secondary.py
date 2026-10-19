"""Bounded workspace settings and maintained, offline operator guidance."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import logging
import sys

from PySide6 import QtCore, QtWidgets

from ui.themes import apply_standard_layout, build_dialog_header, polish_form_controls

logger = logging.getLogger(__name__)

# This allowlist is also included in launcher.spec; no operator files are bundled.
GUIDES = (
    ("Daily session workflow", "OPERATOR_RUNBOOK.md"),
    ("Guided rig setup", "GUIDED_SETUP.md"),
    ("Recorded-session research", "MEASUREMENT_RESEARCH.md"),
    ("Troubleshooting", "user/TROUBLESHOOTING.md"),
)


class WorkspaceSettingsDialog(QtWidgets.QDialog):
    def __init__(self, parent: QtWidgets.QWidget, preferences: QtWidgets.QWidget,
                 open_setup: Callable[[], object]) -> None:
        super().__init__(parent)
        self.setWindowTitle("Workspace settings")
        self.resize(640, 400)
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)
        layout.addWidget(build_dialog_header("Settings", "Updates apply to this application; rig changes belong in Setup."))
        layout.addWidget(preferences)
        self.setup_button = QtWidgets.QPushButton("Open Rig Setup")
        self.setup_button.setAccessibleName("Open rig setup from settings")

        def navigate() -> None:
            self.accept()
            open_setup()

        self.setup_button.clicked.connect(navigate)
        layout.addWidget(self.setup_button)
        guidance = QtWidgets.QLabel("Stop runtime preview before editing the rig. Opening Setup does not stop capture.")
        guidance.setWordWrap(True)
        layout.addWidget(guidance)
        layout.addStretch()
        close = QtWidgets.QPushButton("Close")
        close.setAccessibleName("Close workspace settings")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        polish_form_controls(self)


class WorkspaceHelpDialog(QtWidgets.QDialog):
    """Read shipped Markdown locally, including a recoverable missing-guide state."""

    def __init__(self, parent: QtWidgets.QWidget | None = None, *, page: str = "live",
                 docs_root: Path | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("PitchTracker Help")
        self.resize(760, 600)
        root = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[2]))
        self._docs_root = docs_root or root / "docs"
        layout = QtWidgets.QVBoxLayout(self)
        apply_standard_layout(layout)
        layout.addWidget(build_dialog_header("Help", "Local operator guidance · select a topic to read"))
        self.topics = QtWidgets.QComboBox()
        self.topics.setAccessibleName("Operator help topic")
        for label, path in GUIDES:
            self.topics.addItem(label, path)
        layout.addWidget(self.topics)
        self.content = QtWidgets.QTextBrowser()
        self.content.setAccessibleName("Operator guidance")
        self.content.setOpenLinks(False)
        self.content.anchorClicked.connect(self._follow_link)
        layout.addWidget(self.content, 1)
        close = QtWidgets.QPushButton("Close")
        close.setAccessibleName("Close operator help")
        close.clicked.connect(self.accept)
        layout.addWidget(close)
        self.topics.currentIndexChanged.connect(self._load_topic)
        self.topics.setCurrentIndex({"setup": 1, "sessions": 2}.get(page, 0))
        self._load_topic()
        polish_form_controls(self)

    def _load_topic(self) -> None:
        path = self._docs_root / self.topics.currentData()
        self._show_file(path)

    def _show_file(self, path: Path) -> None:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            logger.warning("Help guide unavailable: %s", path, exc_info=True)
            self.content.setPlainText("Guide unavailable in this installation. Select another topic, "
                                      "or restore the documentation from your PitchTracker installation.")
            return
        self.content.document().setBaseUrl(QtCore.QUrl.fromLocalFile(str(path.resolve())))
        self.content.setMarkdown(text)
        self.content.moveCursor(self.content.textCursor().MoveOperation.Start)

    def _follow_link(self, url: QtCore.QUrl) -> None:
        target = self.content.document().baseUrl().resolved(url)
        if target.isLocalFile() and Path(target.toLocalFile()).suffix.lower() == ".md":
            self._show_file(Path(target.toLocalFile()))
            if target.hasFragment():
                self.content.scrollToAnchor(target.fragment())
        else:
            # Explicitly clicked public documentation links; no data is uploaded.
            from PySide6 import QtGui
            if target.scheme() in {"https", "http"}:
                QtGui.QDesktopServices.openUrl(target)
