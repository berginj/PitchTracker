"""A dark Windows palette must not hide text on transparent hosted surfaces."""

from PySide6 import QtGui, QtWidgets

from ui.themes import get_style_manager


def _luminance(color):
    channels = [value / 255 for value in (color.red(), color.green(), color.blue())]
    linear = [value / 12.92 if value <= .04045 else ((value + .055) / 1.055) ** 2.4 for value in channels]
    return sum(value * weight for value, weight in zip(linear, (.2126, .7152, .0722)))


def test_transparent_hosted_surface_stays_readable_with_dark_system_palette(qtbot):
    app = QtWidgets.QApplication.instance()
    previous = app.palette()
    try:
        app.setPalette(QtGui.QPalette(QtGui.QColor("#202020")))
        get_style_manager().apply_to_app(app)
        surface = QtWidgets.QWidget()
        surface.setAutoFillBackground(True)
        surface.resize(300, 120)
        layout = QtWidgets.QVBoxLayout(surface)
        label = QtWidgets.QLabel("Speed: unavailable")
        layout.addWidget(label)
        qtbot.addWidget(surface)
        surface.show()
        qtbot.waitExposed(surface)
        background = surface.grab().toImage().pixelColor(2, 2)
        foreground = label.palette().color(QtGui.QPalette.ColorRole.WindowText)
        contrast = (max(_luminance(background), _luminance(foreground)) + .05) / (
            min(_luminance(background), _luminance(foreground)) + .05)
        assert background.lightness() > 200
        assert contrast >= 4.5
    finally:
        app.setPalette(previous)
