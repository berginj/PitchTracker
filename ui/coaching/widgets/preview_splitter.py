"""Mouse and keyboard resizing for the feedback/preview split."""

from PySide6 import QtCore, QtGui, QtWidgets


class PreviewHandle(QtWidgets.QSplitterHandle):
    def __init__(self, orientation: QtCore.Qt.Orientation, parent: QtWidgets.QSplitter):
        super().__init__(orientation, parent)
        self.setFocusPolicy(QtCore.Qt.FocusPolicy.StrongFocus)
        self.setAccessibleName("Resize camera preview")
        self.setAccessibleDescription("Use Left and Right arrow keys to resize pitch feedback and preview.")

    def keyPressEvent(self, event: QtGui.QKeyEvent) -> None:
        if event.key() in (QtCore.Qt.Key.Key_Left, QtCore.Qt.Key.Key_Right):
            delta = -16 if event.key() == QtCore.Qt.Key.Key_Left else 16
            self.moveSplitter(self.x() + delta)
            event.accept()
        else:
            super().keyPressEvent(event)


class PreviewSplitter(QtWidgets.QSplitter):
    def createHandle(self) -> QtWidgets.QSplitterHandle:
        return PreviewHandle(self.orientation(), self)
