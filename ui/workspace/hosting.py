"""Public Qt hosting operations; hiding a page never tears down its services."""

from PySide6 import QtCore, QtWidgets


def embed_window(window: QtWidgets.QMainWindow, parent: QtWidgets.QWidget,
                 *, scroll_content: bool = False) -> None:
    window.setParent(parent, QtCore.Qt.WindowType.Widget)
    window.setAttribute(QtCore.Qt.WidgetAttribute.WA_DeleteOnClose, False)
    window.setMinimumSize(0, 0)
    window.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Ignored)
    if scroll_content:
        content = window.takeCentralWidget()
        scroll = QtWidgets.QScrollArea(window)
        scroll.setWidgetResizable(True)
        scroll.setMinimumSize(0, 0)
        scroll.setFrameShape(QtWidgets.QFrame.Shape.NoFrame)
        scroll.setAccessibleName("Workspace page content")
        scroll.setWidget(content)
        window.setCentralWidget(scroll)
