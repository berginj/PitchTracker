"""System and shell methods extracted from MainWindow."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtGui

from app.config import ResourceLimits, set_resource_limits
from app.events import get_error_bus
from app.events.recovery import get_recovery_manager
from app.lifecycle import get_cleanup_manager
from app.monitoring import get_resource_monitor
from app.validation import ConfigValidator
from configs.settings import load_config
from log_config.logger import get_logger
from ui.themes import ask_confirmation, get_style_manager, show_message_dialog

logger = get_logger(__name__)


class MainWindowSystemMixin:
    def _apply_modern_styles(self) -> None:
        """Apply the centralized design system to the main app shell."""
        sm = get_style_manager()

        for button in (
            self._start_button,
            self._restart_button,
            self._replay_button,
            self._enter_button,
            self._profile_load,
            self._apply_detector,
        ):
            sm.style_button(button, "primary")

        for button in (
            self._record_button,
            self._training_button,
            self._profile_save,
            self._pitcher_add,
            self._save_strike_button,
            self._save_roi_button,
        ):
            sm.style_button(button, "success")

        for button in (
            self._stop_button,
            self._stop_record_button,
        ):
            sm.style_button(button, "danger")

        for button in (
            self._refresh_button,
            self._pause_button,
            self._step_button,
            self._record_settings_button,
            self._strike_settings_button,
            self._detector_settings_button,
            self._low_perf_button,
            self._cue_card_button,
            self._checklist_button,
            self._output_browse,
            self._lane_button,
            self._lane_right_button,
            self._plate_button,
            self._clear_lane_button,
            self._clear_plate_button,
            self._load_roi_button,
            self._guide_button,
            self._quick_cal_button,
            self._plate_cal_button,
        ):
            sm.style_button(button, "default")

        for widget in (
            self._left_input,
            self._right_input,
            self._session_name,
            self._profile_combo,
            self._profile_name,
            self._pitcher_combo,
            self._pitcher_name_input,
            self._output_dir,
            self._manual_speed,
            self._ball_combo,
            self._batter_height,
            self._top_ratio,
            self._bottom_ratio,
            self._mode_combo,
            self._frame_diff,
            self._bg_diff,
            self._bg_alpha,
            self._edge_thresh,
            self._blob_thresh,
            self._min_area,
            self._min_circ,
        ):
            sm.style_input(widget)

        self._controls_widget.setProperty("surface", "toolbar")
        sm.polish(self._controls_widget)
        self._plate_widget.setProperty("surface", "card")
        sm.polish(self._plate_widget)
        self._left_view.setProperty("surface", "preview")
        self._right_view.setProperty("surface", "preview")
        sm.polish(self._left_view)
        sm.polish(self._right_view)
        sm.style_status_indicator(self._status_label, "info")

    def _get_git_commit(self) -> Optional[str]:
        """Get current git commit hash (short form)."""
        try:
            import subprocess

            result = subprocess.run(
                ["git", "rev-parse", "--short", "HEAD"],
                capture_output=True,
                text=True,
                timeout=1.0,
                check=False,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception:
            pass
        return None

    def _config_path(self) -> Path:
        return self._config_path_value

    def _validate_config_at_startup(self, config_path: Path) -> None:
        """Validate configuration at startup."""
        try:
            config = load_config(config_path)
            validator = ConfigValidator()
            is_valid, issues = validator.validate(config)

            errors = [item for item in issues if item.severity == "error"]
            if errors:
                error_text = "\n".join(f"• {item.field}: {item.message}" for item in errors)
                show_message_dialog(
                    None,
                    "Configuration Error",
                    f"Configuration validation failed:\n\n{error_text}\n\n"
                    f"Please fix these errors in {config_path}",
                    tone="error",
                )
                import sys

                sys.exit(1)

            warnings = [item for item in issues if item.severity == "warning"]
            if warnings:
                warning_text = "\n".join(
                    f"• {item.field}: {item.message}" for item in warnings
                )
                show_message_dialog(
                    None,
                    "Configuration Warnings",
                    f"Configuration has warnings:\n\n{warning_text}\n\n"
                    "The application will continue, but you may want to review these.",
                    tone="warning",
                )
        except Exception as exc:
            show_message_dialog(
                None,
                "Configuration Error",
                f"Failed to validate configuration:\n\n{exc}",
                tone="error",
            )
            import sys

            sys.exit(1)

    def _init_error_handling(self) -> None:
        """Initialize error handling system."""
        self._error_bus = get_error_bus()
        self._recovery_manager = get_recovery_manager()
        self._recovery_manager.register_handler(
            "stop_session", lambda event: self._stop_recording()
        )
        self._recovery_manager.register_handler("shutdown", lambda event: self.close())
        self._recovery_manager.start()
        logger.info("Error handling system initialized")

    def _init_resource_monitoring(self) -> None:
        """Start resource monitoring."""
        self._resource_monitor = get_resource_monitor()
        self._resource_monitor.start()
        logger.info("Resource monitoring started")

    def _init_resource_limits(self) -> None:
        """Configure resource limits."""
        limits = ResourceLimits(
            max_memory_mb=6000.0,
            warning_memory_mb=3000.0,
            max_cpu_percent=90.0,
            warning_cpu_percent=75.0,
            critical_disk_gb=10.0,
            warning_disk_gb=30.0,
            recommended_disk_gb=100.0,
            detection_queue_size=10,
            recording_queue_size=30,
            camera_open_timeout=15.0,
            shutdown_timeout=60.0,
        )
        set_resource_limits(limits)
        logger.info("Resource limits configured")

    def _register_cleanup_tasks(self) -> None:
        """Register cleanup tasks for graceful shutdown."""
        self._cleanup_manager = get_cleanup_manager()
        self._cleanup_manager.register_cleanup(
            "stop_capture",
            self._service.stop_capture,
            timeout=10.0,
            critical=True,
        )
        self._cleanup_manager.register_cleanup(
            "stop_recording",
            lambda: self._service.stop_recording()
            if hasattr(self, "_service")
            else None,
            timeout=10.0,
            critical=True,
        )
        self._cleanup_manager.register_cleanup(
            "stop_monitoring",
            lambda: self._resource_monitor.stop(),
            timeout=2.0,
            critical=False,
        )
        self._cleanup_manager.register_cleanup(
            "stop_recovery",
            lambda: self._recovery_manager.stop(),
            timeout=2.0,
            critical=False,
        )
        logger.info("Cleanup tasks registered")

    def closeEvent(self, event: QtGui.QCloseEvent) -> None:
        """Handle application close with graceful shutdown."""
        if not hasattr(self, "_cleanup_manager"):
            self._register_cleanup_tasks()

        logger.info("Performing graceful shutdown...")
        success = self._cleanup_manager.cleanup()

        if success:
            logger.info("Shutdown completed successfully")
            event.accept()
            return

        logger.warning("Some critical cleanup tasks failed")
        if ask_confirmation(
            self,
            "Shutdown Warning",
            "Some critical cleanup tasks failed. Force quit anyway?",
            confirm_variant="danger",
        ):
            event.accept()
        else:
            event.ignore()
