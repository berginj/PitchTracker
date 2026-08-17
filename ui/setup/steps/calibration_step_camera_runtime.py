"""Camera runtime and persistence helpers for the calibration step."""

from __future__ import annotations

from ui.setup.steps.calibration_step_mixin_host import CalibrationStepMixinHost

import time

from PySide6 import QtCore

from log_config.logger import get_logger
from ui.themes import (
    show_message_dialog,
)

logger = get_logger(__name__)


class CalibrationStepCameraRuntimeMixin(CalibrationStepMixinHost):
    def _load_camera_history(self) -> dict[str, str]:
        """Load historical camera position assignments.

        Returns:
            Dict mapping serial -> 'left' or 'right'
        """
        import json

        if not self._camera_history_file.exists():
            return {}

        try:
            with open(self._camera_history_file, "r") as f:
                payload = json.load(f)
            if not isinstance(payload, dict):
                return {}
            return {
                str(key): str(value)
                for key, value in payload.items()
                if isinstance(key, str) and isinstance(value, str)
            }
        except Exception:
            return {}

    def _save_camera_history(self) -> None:
        """Save current camera assignments to history."""
        import json

        history = self._load_camera_history()

        # Update with current assignments
        if self._left_serial:
            history[str(self._left_serial)] = "left"
        if self._right_serial:
            history[str(self._right_serial)] = "right"

        # Save
        try:
            self._camera_history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self._camera_history_file, "w") as f:
                json.dump(history, f, indent=2)
            logger.debug(
                "Saved camera history with left_serial={!r} and right_serial={!r}",
                self._left_serial,
                self._right_serial,
            )
        except Exception as e:
            logger.warning("Failed to save camera history: {}", e)

    def _check_camera_history(self) -> bool:
        """Check if current cameras match historical assignments.

        Returns:
            True if cameras need swapping based on history
        """
        history = self._load_camera_history()

        if not history or not self._left_serial or not self._right_serial:
            return False

        # Check if serials are in history
        left_history = history.get(str(self._left_serial))
        right_history = history.get(str(self._right_serial))

        # If both cameras have history, check if they're swapped
        if left_history and right_history:
            if left_history == "right" and right_history == "left":
                logger.info(
                    "Camera history indicates swapped positions: left_serial={!r} was previously right, right_serial={!r} was previously left",
                    self._left_serial,
                    self._right_serial,
                )
                return True

        return False

    def _swap_left_right(self, save_to_history: bool = True) -> None:
        """Swap left and right camera assignments.

        Args:
            save_to_history: Whether to save the new assignment to history
        """
        import yaml

        # Swap the serial numbers
        self._left_serial, self._right_serial = self._right_serial, self._left_serial

        logger.info(
            "Swapped camera assignments: left_serial={!r}, right_serial={!r}",
            self._left_serial,
            self._right_serial,
        )

        # Save to history
        if save_to_history:
            self._save_camera_history()

        # Swap flip button states (flip settings follow the camera, not the position)
        config_data = yaml.safe_load(self._config_path.read_text())
        flip_left = config_data.get("camera", {}).get("flip_left", False)
        flip_right = config_data.get("camera", {}).get("flip_right", False)

        # Update config with swapped flip states
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("camera", {})
        data["camera"]["flip_left"] = flip_right
        data["camera"]["flip_right"] = flip_left
        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Update button states to reflect swapped config
        self._flip_left_btn.setChecked(flip_right)
        self._flip_right_btn.setChecked(flip_left)

        # Restart cameras if open to apply swap
        if self._left_camera is not None or self._right_camera is not None:
            # Stop preview
            self._preview_timer.stop()

            # Close cameras
            self._close_cameras()

            # Reopen with swapped assignments after short delay
            QtCore.QTimer.singleShot(300, self._restart_cameras_after_swap)

    def _restart_cameras_after_swap(self) -> None:
        """Reopen cameras and restart preview after L/R swap."""
        try:
            self._open_cameras()

            # Restart preview if cameras opened successfully
            if self._left_camera and self._right_camera:
                self._preview_timer.start(33)  # ~30 FPS
                logger.info("Restarted cameras after swapping left/right assignments")
        except Exception:
            logger.exception("Failed to restart cameras after swapping assignments")

    def _update_baseline(self, value_ft: float) -> None:
        """Update baseline distance in config.

        Args:
            value_ft: Baseline distance in feet
        """
        import yaml

        # Update config file
        data = yaml.safe_load(self._config_path.read_text())
        data.setdefault("stereo", {})
        data["stereo"]["baseline_ft"] = float(value_ft)
        self._config_path.write_text(yaml.safe_dump(data, sort_keys=False))

        # Update inches label and status
        baseline_inches = value_ft * 12
        if hasattr(self, "_baseline_inches_label"):
            # User is manually entering, so mark as manual (orange)
            self._baseline_inches_label.setText(f"({baseline_inches:.1f} in) ✏️ Manual")
            self._set_baseline_state(
                f"{baseline_inches:.1f} in · Manual",
                "warning",
                "This is a manually entered value. Run calibration to get a precise measurement.",
            )

    def _clear_temp_images(self) -> None:
        """Clear old calibration images from temp directory."""

        if self._temp_dir.exists():
            # Remove all files in temp directory
            for file in self._temp_dir.glob("*.png"):
                try:
                    file.unlink()
                except Exception:
                    pass
        else:
            # Create temp directory if it doesn't exist
            self._temp_dir.mkdir(parents=True, exist_ok=True)

    def _open_cameras(self) -> None:
        """Open camera devices."""
        try:
            logger.debug(
                "Opening calibration cameras with backend={!r}, left_serial={!r}, right_serial={!r}",
                self._backend,
                self._left_serial,
                self._right_serial,
            )

            if not self._left_serial or not self._right_serial:
                raise ValueError("Camera serials not set. Please select cameras in Step 1.")

            # Read camera settings from config
            import yaml

            config_data = yaml.safe_load(self._config_path.read_text())

            # Resolution and framerate from config
            camera_config = config_data.get("camera", {})
            width = camera_config.get("width", 1280)
            height = camera_config.get("height", 720)
            fps = camera_config.get("fps", 60)
            pixfmt = camera_config.get("pixfmt", "GRAY8")

            # Flip and rotation settings
            flip_left = camera_config.get("flip_left", False)
            flip_right = camera_config.get("flip_right", False)
            rotation_left = camera_config.get("rotation_left", 0.0)
            rotation_right = camera_config.get("rotation_right", 0.0)

            if self._backend == "opencv":
                from capture.opencv_backend import OpenCVCamera

                logger.debug(
                    "Extracting OpenCV camera indices from left_serial={!r} ({}), right_serial={!r} ({})",
                    self._left_serial,
                    type(self._left_serial).__name__,
                    self._right_serial,
                    type(self._right_serial).__name__,
                )

                # Ensure serials are strings (they might be ints from some code paths)
                left_serial_str = str(self._left_serial)
                right_serial_str = str(self._right_serial)

                # Extract index from "Camera N" format or use serial directly if it's a number
                # Convert to integer for OpenCV
                if left_serial_str.isdigit():
                    left_index = int(left_serial_str)
                else:
                    left_index = int(left_serial_str.split()[-1])

                if right_serial_str.isdigit():
                    right_index = int(right_serial_str)
                else:
                    right_index = int(right_serial_str.split()[-1])

                logger.debug(
                    "Resolved OpenCV camera indices: left_index={} ({}), right_index={} ({})",
                    left_index,
                    type(left_index).__name__,
                    right_index,
                    type(right_index).__name__,
                )

                self._left_camera = OpenCVCamera()
                self._right_camera = OpenCVCamera()

                # Open left camera
                try:
                    logger.debug("Opening left OpenCV camera index={} flip={}", left_index, flip_left)
                    self._left_camera.open(left_index)
                    logger.debug("Opened left OpenCV camera successfully")
                except Exception as e:
                    logger.exception("Failed to open left OpenCV camera at index {}", left_index)
                    raise RuntimeError(f"Failed to open left camera at index {left_index}: {e}")

                # Open right camera
                try:
                    logger.debug("Opening right OpenCV camera index={} flip={}", right_index, flip_right)
                    self._right_camera.open(right_index)
                    logger.debug("Opened right OpenCV camera successfully")
                except Exception as e:
                    logger.exception("Failed to open right OpenCV camera at index {}", right_index)
                    raise RuntimeError(f"Failed to open right camera at index {right_index}: {e}")

                # Configure cameras with settings from config including flip and rotation correction
                try:
                    logger.debug(
                        "Configuring left OpenCV camera width={} height={} fps={} pixfmt={!r}",
                        width,
                        height,
                        fps,
                        pixfmt,
                    )
                    self._left_camera.set_mode(
                        width, height, fps, pixfmt, flip_180=flip_left, rotation_correction=rotation_left
                    )
                    logger.debug("Configured left OpenCV camera successfully")
                except Exception as e:
                    logger.exception("Failed to configure left OpenCV camera")
                    raise RuntimeError(f"Failed to configure left camera: {e}")

                try:
                    logger.debug(
                        "Configuring right OpenCV camera width={} height={} fps={} pixfmt={!r}",
                        width,
                        height,
                        fps,
                        pixfmt,
                    )
                    self._right_camera.set_mode(
                        width, height, fps, pixfmt, flip_180=flip_right, rotation_correction=rotation_right
                    )
                    logger.debug("Configured right OpenCV camera successfully")
                except Exception as e:
                    logger.exception("Failed to configure right OpenCV camera")
                    raise RuntimeError(f"Failed to configure right camera: {e}")

            else:  # uvc
                from capture import UvcCamera

                self._left_camera = UvcCamera()
                self._right_camera = UvcCamera()

                # Open cameras with their serials - retry with delays if needed
                logger.debug("Opening left UVC camera serial={!r} flip={}", self._left_serial, flip_left)
                for attempt in range(3):
                    try:
                        self._left_camera.open(self._left_serial)
                        break
                    except Exception:
                        if attempt < 2:
                            logger.warning(
                                "Left UVC camera open attempt {} failed; retrying",
                                attempt + 1,
                            )
                            time.sleep(1.0)
                        else:
                            raise

                logger.debug("Opening right UVC camera serial={!r} flip={}", self._right_serial, flip_right)
                for attempt in range(3):
                    try:
                        self._right_camera.open(self._right_serial)
                        break
                    except Exception:
                        if attempt < 2:
                            logger.warning(
                                "Right UVC camera open attempt {} failed; retrying",
                                attempt + 1,
                            )
                            time.sleep(1.0)
                        else:
                            raise

                # Configure cameras with settings from config including flip and rotation correction
                self._left_camera.set_mode(
                    width, height, fps, pixfmt, flip_180=flip_left, rotation_correction=rotation_left
                )
                self._right_camera.set_mode(
                    width, height, fps, pixfmt, flip_180=flip_right, rotation_correction=rotation_right
                )

            # Update status labels to show which camera is assigned to which position
            self._left_status.setText(f"● {self._left_serial}")
            self._set_detection_status(self._left_status, detected=True)
            self._right_status.setText(f"● {self._right_serial}")
            self._set_detection_status(self._right_status, detected=True)

            logger.info(
                "Opened calibration cameras successfully: left_serial={!r}, right_serial={!r}",
                self._left_serial,
                self._right_serial,
            )

            # NEW: Wait for cameras to warm up, then run alignment check
            QtCore.QTimer.singleShot(1000, self._wait_for_camera_warmup)

        except Exception as e:
            # Clean up any partially opened cameras
            self._close_cameras()

            error_msg = (
                f"Failed to open cameras:\n{str(e)}\n\n"
                f"Left Camera: {self._left_serial}\n"
                f"Right Camera: {self._right_serial}\n\n"
                "Common causes:\n"
                "• Cameras are in use by another application (close other apps)\n"
                "• Cameras were not properly released (try going back to Step 1)\n"
                "• Incorrect permissions or driver issues\n"
                "• Cameras disconnected"
            )

            show_message_dialog(
                self,
                "Camera Error",
                error_msg,
                tone="error",
            )

    def _close_cameras(self) -> None:
        """Close camera devices."""
        if self._left_camera:
            try:
                self._left_camera.close()
            except Exception:
                pass
            finally:
                self._left_camera = None

        if self._right_camera:
            try:
                self._right_camera.close()
            except Exception:
                pass
            finally:
                self._right_camera = None

        # Reset status labels
        self._left_status.setText("● Waiting...")
        self._set_detection_status(self._left_status, detected=False)
        self._right_status.setText("● Waiting...")
        self._set_detection_status(self._right_status, detected=False)

        # Force garbage collection to release any lingering handles
        import gc

        gc.collect()

    def _force_release_cameras(self) -> None:
        """Aggressively release camera resources (for when cameras get stuck)."""
        import gc
        import cv2

        # Stop preview timer first
        self._preview_timer.stop()

        # Try normal close
        self._close_cameras()

        # Get list of camera device names
        from capture.uvc_backend import list_uvc_devices

        devices = list_uvc_devices()

        # Build list of device friendly names to try
        device_names = []
        for device in devices:
            serial = device.get("serial", "")
            friendly = device.get("friendly_name", "")
            if serial in [self._left_serial, self._right_serial]:
                device_names.append(friendly)

        # Try to open and immediately close using cv2 directly to force DirectShow release
        for device_name in device_names:
            for attempt in range(3):
                cap = None
                try:
                    # Try to open with DirectShow
                    cap = cv2.VideoCapture(f"video={device_name}", cv2.CAP_DSHOW)
                    if cap.isOpened():
                        cap.read()  # Try to read one frame
                except Exception:
                    pass
                finally:
                    if cap is not None:
                        try:
                            cap.release()
                        except Exception:
                            pass
                    del cap

                time.sleep(0.3)
                gc.collect()

        # Final aggressive cleanup
        time.sleep(1.0)
        gc.collect()

        show_message_dialog(
            self,
            "Cameras Released",
            "Camera resources have been forcibly released.\n\n"
            "You can now try opening the cameras again by going back to Step 1 "
            "and then returning to Step 2.",
            tone="success",
        )
