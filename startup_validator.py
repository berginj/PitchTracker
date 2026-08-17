"""Startup validation for PitchTracker.

Checks system requirements and configuration before launching the application.
"""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Optional

from loguru import logger


def _load_dependency_checker():
    """Load scripts/check_dependencies.py without namespace-package imports."""
    checker_path = Path(__file__).resolve().parent / "scripts" / "check_dependencies.py"
    spec = importlib.util.spec_from_file_location("_pitchtracker_check_dependencies", checker_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load dependency checker from {checker_path}")

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _find_missing_dependency_packages() -> list[str]:
    """Return missing packages using import spec lookup without importing them."""
    required_packages = {
        "cv2": "opencv-contrib-python",
        "numpy": "numpy",
        "scipy": "scipy",
        "yaml": "PyYAML",
        "PySide6": "PySide6",
        "sklearn": "scikit-learn",
        "matplotlib": "matplotlib",
        "loguru": "loguru",
        "jsonschema": "jsonschema",
        "psutil": "psutil",
    }

    missing_packages: list[str] = []
    for module_name, package_name in required_packages.items():
        if importlib.util.find_spec(module_name) is None:
            missing_packages.append(package_name)

    return missing_packages


def validate_python_version() -> tuple[bool, Optional[str]]:
    """Check if Python version meets requirements.

    Returns:
        Tuple of (is_valid, error_message)
    """
    required_major = 3
    required_minor = 13

    current_major = sys.version_info.major
    current_minor = sys.version_info.minor

    if current_major < required_major or (current_major == required_major and current_minor < required_minor):
        return False, (
            f"Python {required_major}.{required_minor}+ is required.\n"
            f"Current version: Python {current_major}.{current_minor}\n\n"
            "Please upgrade Python or reinstall PitchTracker."
        )

    return True, None


def validate_dependencies() -> tuple[bool, Optional[str]]:
    """Check if required Python packages are installed.

    Returns:
        Tuple of (is_valid, error_message)
    """
    try:
        # Use a lightweight probe during startup. Importing the full dependency
        # stack here can trigger expensive or fragile import side effects before
        # the GUI is even visible.
        missing_packages = _find_missing_dependency_packages()
        if not missing_packages:
            return True, None

        # Build helpful error message
        packages_str = ", ".join(missing_packages[:5])
        if len(missing_packages) > 5:
            packages_str += f" (and {len(missing_packages) - 5} more)"

        error_msg = (
            f"Missing required packages: {packages_str}\n\n"
            "Please install dependencies:\n"
            "  pip install -r requirements.txt\n\n"
            "Or install individually:\n"
        )
        for pkg in missing_packages[:3]:
            error_msg += f"  pip install {pkg}\n"

        error_msg += "\nFor detailed setup instructions, see: docs/INSTALLATION.md"

        return False, error_msg

    except Exception as e:
        # Fallback to the same lightweight probe if something unexpected occurs.
        logger.warning(f"Could not complete dependency probe cleanly: {e}")
        missing_packages = _find_missing_dependency_packages()

        if missing_packages:
            packages_str = ", ".join(missing_packages)
            return False, (
                f"Missing required packages: {packages_str}\n\n"
                "Please install dependencies:\n"
                "  pip install -r requirements.txt\n\n"
                "For detailed setup instructions, see: docs/INSTALLATION.md"
            )

        return True, None


def check_cameras() -> tuple[list[str], list[str]]:
    """Check for available cameras.

    Returns:
        Tuple of (warnings, info_messages)
    """
    warnings: list[str] = []
    info = []

    try:
        import cv2

        # Try to open a camera
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            info.append("At least one camera detected")
            cap.release()
        else:
            warnings.append(
                "No cameras detected.\n\n"
                "Please connect your cameras before starting a session.\n"
                "USB 3.0 ports recommended for best performance."
            )

    except Exception as e:
        logger.warning(f"Camera check failed: {e}")
        warnings.append(
            "Could not check for cameras.\n\n" "This may not be an issue, but verify cameras are connected."
        )

    return warnings, info


def check_configuration() -> tuple[list[str], list[str]]:
    """Check for required configuration files.

    Returns:
        Tuple of (warnings, info_messages)
    """
    warnings = []
    info = []

    # Check main config file
    config_path = Path("configs/default.yaml")
    if not config_path.exists():
        warnings.append(
            "Configuration file missing: configs/default.yaml\n\n" "Run the Setup Wizard to configure the system."
        )
    else:
        info.append(f"Configuration found: {config_path}")

    # Check calibration and quality
    from calib.quick_calibrate import load_calibration_quality

    calib_path = Path("calibration/stereo_calibration.npz")
    if not calib_path.exists():
        warnings.append(
            "Calibration data missing: calibration/stereo_calibration.npz\n\n"
            "Run the Setup Wizard to calibrate your cameras."
        )
    else:
        quality = load_calibration_quality()
        if quality:
            rating = quality["rating"]
            rms = quality["rms_error_px"]
            if rating == "POOR":
                warnings.append(
                    f"Calibration quality is POOR (RMS: {rms:.3f} px)\n\n"
                    f"{quality['description']}\n\n"
                    "Re-calibrate for accurate measurements."
                )
            elif rating == "ACCEPTABLE":
                info.append(f"Calibration found: {calib_path} (Quality: {rating}, RMS: {rms:.3f} px)")
                info.append("⚠ Consider re-calibrating for better accuracy")
            else:  # EXCELLENT or GOOD
                info.append(f"Calibration found: {calib_path} (Quality: {rating}, RMS: {rms:.3f} px)")
        else:
            info.append(f"Calibration found: {calib_path} (Quality: Unknown - re-calibrate to get metrics)")

    # Check ROIs
    roi_path = Path("rois/shared_rois.json")
    if not roi_path.exists():
        warnings.append(
            "ROI configuration missing: rois/shared_rois.json\n\n"
            "Run the Setup Wizard to configure regions of interest."
        )
    else:
        info.append(f"ROIs found: {roi_path}")

    return warnings, info


def validate_environment() -> tuple[list[str], list[str]]:
    """Validate complete environment before launching.

    Returns:
        Tuple of (errors, warnings)
        - errors: Critical issues that prevent launching
        - warnings: Non-critical issues that should be addressed
    """
    errors: list[str] = []
    warnings: list[str] = []

    logger.info("Validating startup environment...")

    # Check Python version (critical)
    is_valid, error_msg = validate_python_version()
    if not is_valid:
        if error_msg is not None:
            errors.append(error_msg)
        return errors, warnings  # Stop here if Python version is wrong

    logger.debug("Python version: OK")

    # Check dependencies (critical)
    is_valid, error_msg = validate_dependencies()
    if not is_valid:
        if error_msg is not None:
            errors.append(error_msg)
        return errors, warnings  # Stop here if dependencies missing

    logger.debug("Dependencies: OK")

    # Check cameras (warning only)
    camera_warnings, camera_info = check_cameras()
    warnings.extend(camera_warnings)
    for msg in camera_info:
        logger.debug(msg)

    # Check configuration (warning only - can run Setup Wizard)
    config_warnings, config_info = check_configuration()
    warnings.extend(config_warnings)
    for msg in config_info:
        logger.debug(msg)

    if not errors and not warnings:
        logger.info("Environment validation: PASSED (all checks OK)")
    elif not errors:
        logger.info(f"Environment validation: PASSED ({len(warnings)} warnings)")
    else:
        logger.error(f"Environment validation: FAILED ({len(errors)} errors)")

    return errors, warnings


def create_required_directories() -> None:
    """Create required directories if they don't exist."""
    required_dirs = [
        "configs",
        "data",
        "data/sessions",
        "logs",
        "calibration",
        "rois",
    ]

    for dir_path in required_dirs:
        Path(dir_path).mkdir(parents=True, exist_ok=True)
        logger.debug(f"Ensured directory exists: {dir_path}")


# For testing
if __name__ == "__main__":
    print("PitchTracker Startup Validation")
    print("=" * 50)
    print()

    errors, warnings = validate_environment()

    if errors:
        print("ERRORS (critical):")
        for i, error in enumerate(errors, 1):
            print(f"\n{i}. {error}")
        print()
        print("Cannot start PitchTracker.")
        sys.exit(1)

    if warnings:
        print("WARNINGS (non-critical):")
        for i, warning in enumerate(warnings, 1):
            print(f"\n{i}. {warning}")
        print()
        print("You can continue, but please address these issues.")
    else:
        print("All checks passed!")
        print("PitchTracker is ready to launch.")
