"""Alignment inspection and export helpers for the calibration step."""

from __future__ import annotations

from ui.setup.steps.calibration_step_mixin_host import CalibrationStepMixinHost

from pathlib import Path

from PySide6 import QtCore, QtGui, QtWidgets

from log_config.logger import get_logger
from ui.themes import (
    ask_confirmation,
    show_message_dialog,
)

logger = get_logger(__name__)


class CalibrationStepAlignmentReportsMixin(CalibrationStepMixinHost):
    def _show_feature_overlay(self) -> None:
        """Show visual overlay of matched features on camera previews."""
        if not self._left_camera or not self._right_camera:
            show_message_dialog(
                self,
                "Cameras Not Ready",
                "Cameras must be active to visualize features.",
                tone="warning",
            )
            return

        try:
            # Capture current frames
            left_frame = self._left_camera.read_frame(timeout_ms=1000)
            right_frame = self._right_camera.read_frame(timeout_ms=1000)

            # Create visualization
            from analysis.camera_alignment import visualize_features, _find_feature_matches

            pts1, pts2 = _find_feature_matches(left_frame.image, right_frame.image, max_features=1000)
            vis_img = visualize_features(left_frame.image, right_frame.image, pts1, pts2)

            # Convert to QPixmap for display
            height, width, channels = vis_img.shape
            bytes_per_line = channels * width
            q_image = QtGui.QImage(
                vis_img.data,
                width,
                height,
                bytes_per_line,
                QtGui.QImage.Format.Format_RGB888,
            )
            pixmap = QtGui.QPixmap.fromImage(q_image)

            # Create dialog to display
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Feature Matches Visualization")
            dialog.resize(1200, 500)

            layout = QtWidgets.QVBoxLayout()

            # Info label
            info_label = QtWidgets.QLabel(
                f"<b>{len(pts1)} matched features</b><br>"
                f"Green circles show corresponding points between cameras.<br>"
                f"Good feature distribution indicates proper alignment."
            )
            info_label.setWordWrap(True)
            layout.addWidget(info_label)

            # Image display
            image_label = QtWidgets.QLabel()
            scaled_pixmap = pixmap.scaled(
                1180, 440, QtCore.Qt.AspectRatioMode.KeepAspectRatio, QtCore.Qt.TransformationMode.SmoothTransformation
            )
            image_label.setPixmap(scaled_pixmap)
            layout.addWidget(image_label)

            # Close button
            close_btn = QtWidgets.QPushButton("Close")
            close_btn.clicked.connect(dialog.accept)
            layout.addWidget(close_btn)

            dialog.setLayout(layout)
            dialog.exec()

        except Exception as e:
            show_message_dialog(
                self,
                "Feature Visualization Error",
                f"Failed to visualize features:\n{str(e)}",
                tone="error",
            )

    def _show_alignment_details(self) -> None:
        """Show detailed alignment report dialog."""
        if not hasattr(self, "_alignment_results") or self._alignment_results is None:
            return

        results = self._alignment_results

        # Build detailed report
        report = (
            f"<h3>Camera Alignment Detailed Report</h3>"
            f"<p><b>Overall Quality:</b> {results.quality}</p>"
            f"<hr>"
            f"<h4>Vertical Alignment (Height)</h4>"
            f"<p><b>Status:</b> {results.vertical_status}<br>"
            f"<b>Mean offset:</b> {results.vertical_mean_px:.2f} px<br>"
            f"<b>Max offset:</b> {results.vertical_max_px:.2f} px</p>"
            f"<hr>"
            f"<h4>Horizontal Alignment (Toe-in/Convergence)</h4>"
            f"<p><b>Status:</b> {results.horizontal_status}<br>"
            f"<b>Disparity std dev:</b> {results.convergence_std_px:.2f} px<br>"
            f"<b>Position correlation:</b> {results.correlation:.3f}<br>"
            f"<i>(Should be >0.9 for parallel cameras)</i></p>"
            f"<hr>"
            f"<h4>Rotation Alignment (Roll)</h4>"
            f"<p><b>Status:</b> {results.rotation_status}<br>"
            f"<b>Rotation difference:</b> {results.rotation_deg:.2f}°</p>"
            f"<hr>"
            f"<h4>Focal Length / Scale</h4>"
            f"<p><b>Status:</b> {results.scale_status}<br>"
            f"<b>Scale difference:</b> {results.scale_difference_percent:.2f}%<br>"
            f"<i>(Indicates if one camera is more zoomed in than the other)</i></p>"
            f"<hr>"
            f"<h4>Feature Matches</h4>"
            f"<p><b>Matches found:</b> {results.num_matches}</p>"
        )

        if results.corrections_applied:
            report += "<hr><h4>Software Corrections Applied</h4><ul>"
            for correction in results.corrections_applied:
                report += f"<li>{correction}</li>"
            report += "</ul>"

        if results.warnings:
            report += "<hr><h4>Recommendations</h4><ul>"
            for warning in results.warnings:
                report += f"<li>{warning}</li>"
            report += "</ul>"

        # Show in dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Camera Alignment Details")
        dialog.resize(600, 500)

        layout = QtWidgets.QVBoxLayout()

        text = QtWidgets.QTextEdit()
        text.setReadOnly(True)
        text.setHtml(report)
        layout.addWidget(text)

        close_btn = QtWidgets.QPushButton("Close")
        close_btn.clicked.connect(dialog.accept)
        layout.addWidget(close_btn)

        dialog.setLayout(layout)
        dialog.exec()

    def _export_alignment_report(self) -> None:
        """Export alignment report as HTML file."""
        if not hasattr(self, "_alignment_results") or self._alignment_results is None:
            show_message_dialog(
                self,
                "No Report Available",
                "Run an alignment check first before exporting a report.",
                tone="warning",
            )
            return

        try:
            from datetime import datetime
            from analysis.camera_alignment import generate_html_report

            # Generate HTML report
            html = generate_html_report(
                self._alignment_results,
                str(self._left_serial or "Unknown"),
                str(self._right_serial or "Unknown"),
            )

            # Prompt user for save location
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_filename = f"alignment_report_{timestamp}.html"

            filename, _ = QtWidgets.QFileDialog.getSaveFileName(
                self,
                "Export Alignment Report",
                str(Path("alignment_checks") / default_filename),
                "HTML Files (*.html);;All Files (*.*)",
            )

            if filename:
                # Save HTML file
                Path(filename).parent.mkdir(parents=True, exist_ok=True)
                Path(filename).write_text(html, encoding="utf-8")

                # Ask if user wants to open the report
                if ask_confirmation(
                    self,
                    "Report Exported",
                    f"Alignment report exported successfully to:\n{filename}\n\n" f"Would you like to open it now?",
                    default_button=QtWidgets.QMessageBox.StandardButton.Yes,
                ):
                    # Open in default browser
                    import webbrowser

                    webbrowser.open(f"file:///{Path(filename).absolute()}")

        except Exception as e:
            show_message_dialog(
                self,
                "Export Failed",
                f"Failed to export alignment report:\n{str(e)}",
                tone="error",
            )
