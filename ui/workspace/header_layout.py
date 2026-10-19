"""Reachable global actions and complete, scrollable recovery information."""

from PySide6 import QtCore, QtWidgets


def arrange_actions(layout: QtWidgets.QGridLayout, buttons: tuple[QtWidgets.QPushButton, ...], *, compact: bool) -> None:
    while layout.count():
        layout.takeAt(0)
    for column in range(len(buttons) + 1):
        layout.setColumnStretch(column, 0)
    visible = [button for button in buttons if not button.isHidden()]
    for index, button in enumerate(visible):
        row, column = divmod(index, 2) if compact else (0, index)
        layout.addWidget(button, row, column)
        button.show()
    if compact:
        layout.setColumnStretch(0, 1)
        layout.setColumnStretch(1, 1)
    else:
        layout.setColumnStretch(len(visible), 1)
    if layout.parentWidget() is not None:
        layout.parentWidget().updateGeometry()


class RuntimeDetail(QtWidgets.QPlainTextEdit):
    """Small keyboard-readable status area; long failure details remain available."""

    def __init__(self) -> None:
        super().__init__()
        self.setReadOnly(True)
        self.setAccessibleName("Session progress and recovery details")
        self.setAccessibleDescription("Read the full message with the arrow keys or scroll; text can be selected and copied.")
        self.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Expanding, QtWidgets.QSizePolicy.Policy.Fixed)
        self.setFixedHeight(60)

    def setText(self, text: str) -> None:
        if text != self.toPlainText():
            self.setPlainText(text)

    def text(self) -> str:
        """Preserve the shell's internal text inspection API."""
        return self.toPlainText()
