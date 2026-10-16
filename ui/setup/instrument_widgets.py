"""Presentation components for camera and calibration setup; no capture ownership."""

from PySide6 import QtCore, QtGui, QtWidgets

from ui.themes import get_style_manager


class Disclosure(QtWidgets.QWidget):
    """Keep secondary controls available without filling the initial screen."""

    def __init__(self, title: str):
        super().__init__()
        self.toggle = QtWidgets.QToolButton()
        self.toggle.setText(title)
        self.toggle.setCheckable(True)
        self.toggle.setToolButtonStyle(QtCore.Qt.ToolButtonStyle.ToolButtonTextBesideIcon)
        self.toggle.setArrowType(QtCore.Qt.ArrowType.RightArrow)
        self.toggle.setAccessibleName(title)
        self.toggle.setObjectName("SetupDisclosure")
        self.content = QtWidgets.QWidget()
        self.content.setVisible(False)
        self.form = QtWidgets.QFormLayout(self.content)
        self.form.setRowWrapPolicy(QtWidgets.QFormLayout.RowWrapPolicy.WrapLongRows)
        self.form.setFieldGrowthPolicy(QtWidgets.QFormLayout.FieldGrowthPolicy.AllNonFixedFieldsGrow)
        self.form.setContentsMargins(0, 12, 0, 8)
        self.form.setSpacing(12)
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self.toggle, alignment=QtCore.Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.content)
        self.toggle.toggled.connect(self.set_expanded)

    def set_expanded(self, expanded: bool) -> None:
        self.content.setVisible(expanded)
        self.toggle.setArrowType(QtCore.Qt.ArrowType.DownArrow if expanded else QtCore.Qt.ArrowType.RightArrow)


class PreviewLabel(QtWidgets.QLabel):
    """Letterbox the original preview again whenever its view is resized."""

    def __init__(self):
        super().__init__("Preview not started")
        self.setObjectName("SetupPreview")
        self.setAlignment(QtCore.Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(140, 170)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Expanding)
        self._source = QtGui.QPixmap()

    def set_source_pixmap(self, pixmap: QtGui.QPixmap) -> None:
        self._source = QtGui.QPixmap(pixmap)
        self._render_source()

    def clear_source(self, text: str = "Preview not started") -> None:
        self._source = QtGui.QPixmap()
        self.setText(text)

    def _render_source(self) -> None:
        if not self._source.isNull():
            super().setPixmap(self._source.scaled(
                self.contentsRect().size(), QtCore.Qt.AspectRatioMode.KeepAspectRatio,
                QtCore.Qt.TransformationMode.SmoothTransformation,
            ))

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._render_source()


class PairedViews(QtWidgets.QWidget):
    """Two equally weighted views, stacked when the content area is narrow."""

    def __init__(self, selectors: tuple[QtWidgets.QComboBox, QtWidgets.QComboBox] | None = None):
        super().__init__()
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        self.previews: list[PreviewLabel] = []
        self.row = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.Direction.LeftToRight, self)
        self.row.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetNoConstraint)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(16)
        for index, side in enumerate(("Left", "Right")):
            column = QtWidgets.QWidget()
            layout = QtWidgets.QVBoxLayout(column)
            layout.setContentsMargins(0, 0, 0, 0)
            layout.setSpacing(8)
            label = QtWidgets.QLabel(f"{side.upper()} VIEW")
            get_style_manager().style_label(label, "eyebrow")
            layout.addWidget(label)
            preview = PreviewLabel()
            preview.setAccessibleName(f"{side} camera preview")
            self.previews.append(preview)
            layout.addWidget(preview, 1)
            if selectors:
                identity_label = QtWidgets.QLabel(f"{side} camera")
                identity_label.setBuddy(selectors[index])
                layout.addWidget(identity_label)
                layout.addWidget(selectors[index])
                selectors[index].setSizeAdjustPolicy(QtWidgets.QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
                selectors[index].setMinimumContentsLength(12)
                selectors[index].setMinimumWidth(0)
            self.row.addWidget(column, 1)

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        direction = (QtWidgets.QBoxLayout.Direction.TopToBottom if self.width() < 560
                     else QtWidgets.QBoxLayout.Direction.LeftToRight)
        self.row.setDirection(direction)


class ResponsiveActions(QtWidgets.QWidget):
    """Keep explicit actions reachable in a narrow setup window."""

    def __init__(self, buttons):
        super().__init__()
        self.buttons = tuple(buttons)
        self.setSizePolicy(QtWidgets.QSizePolicy.Policy.Ignored, QtWidgets.QSizePolicy.Policy.Preferred)
        self.row = QtWidgets.QBoxLayout(QtWidgets.QBoxLayout.Direction.LeftToRight, self)
        self.row.setSizeConstraint(QtWidgets.QLayout.SizeConstraint.SetNoConstraint)
        self.row.setContentsMargins(0, 0, 0, 0)
        self.row.setSpacing(8)
        for button in self.buttons:
            self.row.addWidget(button)
        self.row.addStretch()

    def resizeEvent(self, event: QtGui.QResizeEvent) -> None:
        super().resizeEvent(event)
        self._adapt()

    def event(self, event: QtCore.QEvent) -> bool:
        if event.type() == QtCore.QEvent.Type.LayoutRequest:
            self._adapt()
        return super().event(event)

    def _adapt(self) -> None:
        visible = [button for button in self.buttons if not button.isHidden()]
        required = sum(button.minimumSizeHint().width() for button in visible) + max(0, len(visible) - 1) * self.row.spacing()
        direction = (QtWidgets.QBoxLayout.Direction.TopToBottom if self.width() < max(620, required)
                     else QtWidgets.QBoxLayout.Direction.LeftToRight)
        if self.row.direction() != direction:
            self.row.setDirection(direction)


class StageStack(QtWidgets.QStackedWidget):
    """Hidden setup pages must not dictate the active page's scroll extent."""

    def __init__(self):
        super().__init__()
        self.currentChanged.connect(self.updateGeometry)

    def sizeHint(self) -> QtCore.QSize:
        current = self.currentWidget()
        return current.sizeHint() if current else super().sizeHint()

    def minimumSizeHint(self) -> QtCore.QSize:
        current = self.currentWidget()
        return current.minimumSizeHint() if current else super().minimumSizeHint()


def setup_button(text: str, callback, *, primary: bool = False) -> QtWidgets.QPushButton:
    button = QtWidgets.QPushButton(text)
    button.setMinimumHeight(40)
    get_style_manager().style_button(button, "primary" if primary else "default")
    button.clicked.connect(callback)
    return button


def stage_heading(stage, title: str, description: str) -> None:
    stage.layout_box.setContentsMargins(0, 0, 0, 0)
    stage.layout_box.setSpacing(12)
    stage.headline.setText(title)
    stage.headline.setProperty("role", "setupHeadline")
    stage.description = QtWidgets.QLabel(description)
    stage.description.setWordWrap(True)
    get_style_manager().style_label(stage.description, "muted")
    stage.layout_box.insertWidget(1, stage.description)
