#!/usr/bin/env python3
"""Complete setup validation for PitchTracker.

Checks Python version, dependencies, config files, camera access,
and write permissions before first use.

Usage:
    python setup_validator.py
"""

import sys
from pathlib import Path
from typing import Dict, List, Tuple


class Colors:
    """ANSI color codes for terminal output (disabled on Windows by default)."""
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BLUE = '\033[94m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

    @staticmethod
    def disable():
        """Disable colors (for Windows or when piping output)."""
        Colors.GREEN = ''
        Colors.YELLOW = ''
        Colors.RED = ''
        Colors.BLUE = ''
        Colors.RESET = ''
        Colors.BOLD = ''


# Disable colors on Windows (unless ANSICON is set)
if sys.platform == 'win32' and 'ANSICON' not in sys.platform:
    Colors.disable()


class ValidationCheck:
    """Result of a validation check."""

    def __init__(self, name: str, passed: bool, message: str, fix: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.fix = fix

    def __repr__(self):
        status = f"{Colors.GREEN}✓ PASS{Colors.RESET}" if self.passed else f"{Colors.RED}✗ FAIL{Colors.RESET}"
        return f"{status} - {self.name}: {self.message}"


def check_python_version() -> ValidationCheck:
    """Check if Python version is 3.10 or later."""
    version = sys.version_info
    version_str = f"{version.major}.{version.minor}.{version.micro}"

    if version.major == 3 and version.minor >= 10:
        return ValidationCheck(
            "Python Version",
            True,
            f"Python {version_str} (meets minimum 3.10 requirement)"
        )
    else:
        return ValidationCheck(
            "Python Version",
            False,
            f"Python {version_str} (minimum 3.10 required)",
            "Download Python 3.10+ from https://www.python.org/downloads/"
        )


def check_dependencies() -> ValidationCheck:
    """Check if all required dependencies are installed."""
    try:
        # Import the dependency checker
        sys.path.insert(0, str(Path(__file__).parent))
        from scripts.check_dependencies import check_dependencies as check_deps

        all_installed, missing, installed = check_deps(verbose=False)

        if all_installed:
            return ValidationCheck(
                "Dependencies",
                True,
                f"All {len(installed)} required packages installed"
            )
        else:
            missing_names = [pkg for pkg, _ in missing]
            return ValidationCheck(
                "Dependencies",
                False,
                f"Missing {len(missing)} packages: {', '.join(missing_names[:3])}{'...' if len(missing) > 3 else ''}",
                "Run: pip install -r requirements.txt"
            )
    except Exception as e:
        return ValidationCheck(
            "Dependencies",
            False,
            f"Could not check dependencies: {e}",
            "Run: pip install -r requirements.txt"
        )


def check_config_directory() -> ValidationCheck:
    """Check if config directory exists and is writable."""
    config_dir = Path("configs")

    if not config_dir.exists():
        try:
            config_dir.mkdir(parents=True, exist_ok=True)
            return ValidationCheck(
                "Config Directory",
                True,
                f"Created config directory: {config_dir.absolute()}"
            )
        except Exception as e:
            return ValidationCheck(
                "Config Directory",
                False,
                f"Could not create config directory: {e}",
                "Check write permissions in PitchTracker directory"
            )

    # Check if writable
    test_file = config_dir / ".write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        return ValidationCheck(
            "Config Directory",
            True,
            f"Config directory exists and is writable: {config_dir.absolute()}"
        )
    except Exception as e:
        return ValidationCheck(
            "Config Directory",
            False,
            f"Config directory is not writable: {e}",
            "Check write permissions in configs/ directory"
        )


def check_default_config() -> ValidationCheck:
    """Check if default.yaml exists."""
    config_file = Path("configs/default.yaml")

    if config_file.exists():
        return ValidationCheck(
            "Default Config",
            True,
            f"Found default configuration: {config_file.absolute()}"
        )
    else:
        return ValidationCheck(
            "Default Config",
            False,
            "Default configuration not found (will be created on first run)",
            "Run Setup Wizard: python launcher.py"
        )


def check_camera_access() -> ValidationCheck:
    """Check if cameras can be accessed."""
    try:
        import cv2

        # Try to open camera 0
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()

            if ret and frame is not None:
                h, w = frame.shape[:2]

                # Check for more cameras
                camera_indices = [0]
                for i in range(1, 5):
                    cap2 = cv2.VideoCapture(i)
                    if cap2.isOpened():
                        camera_indices.append(i)
                        cap2.release()

                if len(camera_indices) >= 2:
                    return ValidationCheck(
                        "Camera Access",
                        True,
                        f"Found {len(camera_indices)} cameras at indices: {camera_indices}"
                    )
                else:
                    return ValidationCheck(
                        "Camera Access",
                        False,
                        f"Only found 1 camera (need 2 for stereo tracking)",
                        "Connect a second USB camera"
                    )
            else:
                return ValidationCheck(
                    "Camera Access",
                    False,
                    "Camera opened but could not read frame",
                    "Check camera drivers and USB connection"
                )
        else:
            return ValidationCheck(
                "Camera Access",
                False,
                "Could not open camera 0",
                "Check camera connections and close other apps using cameras (Zoom, Skype, etc.)"
            )
    except ImportError:
        return ValidationCheck(
            "Camera Access",
            False,
            "OpenCV not installed (cannot test cameras)",
            "Install OpenCV: pip install opencv-contrib-python"
        )
    except Exception as e:
        return ValidationCheck(
            "Camera Access",
            False,
            f"Error accessing cameras: {e}",
            "Check camera drivers and permissions"
        )


def check_recordings_directory() -> ValidationCheck:
    """Check if recordings directory can be created."""
    recordings_dir = Path("recordings")

    if not recordings_dir.exists():
        try:
            recordings_dir.mkdir(parents=True, exist_ok=True)
            return ValidationCheck(
                "Recordings Directory",
                True,
                f"Created recordings directory: {recordings_dir.absolute()}"
            )
        except Exception as e:
            return ValidationCheck(
                "Recordings Directory",
                False,
                f"Could not create recordings directory: {e}",
                "Check write permissions in PitchTracker directory"
            )

    # Check if writable
    test_file = recordings_dir / ".write_test"
    try:
        test_file.write_text("test")
        test_file.unlink()
        return ValidationCheck(
            "Recordings Directory",
            True,
            f"Recordings directory exists and is writable: {recordings_dir.absolute()}"
        )
    except Exception as e:
        return ValidationCheck(
            "Recordings Directory",
            False,
            f"Recordings directory is not writable: {e}",
            "Check write permissions in recordings/ directory"
        )


def check_disk_space() -> ValidationCheck:
    """Check available disk space."""
    try:
        import psutil

        disk = psutil.disk_usage('.')
        free_gb = disk.free / (1024**3)

        if free_gb >= 10:
            return ValidationCheck(
                "Disk Space",
                True,
                f"{free_gb:.1f} GB available (sufficient for recordings)"
            )
        elif free_gb >= 1:
            return ValidationCheck(
                "Disk Space",
                True,
                f"{free_gb:.1f} GB available (limited - consider freeing space for recordings)"
            )
        else:
            return ValidationCheck(
                "Disk Space",
                False,
                f"Only {free_gb:.1f} GB available (may run out during recording)",
                "Free up disk space (recommend 10+ GB for recordings)"
            )
    except ImportError:
        return ValidationCheck(
            "Disk Space",
            True,
            "Could not check (psutil not installed - not critical)"
        )
    except Exception as e:
        return ValidationCheck(
            "Disk Space",
            True,
            f"Could not check: {e} (not critical)"
        )


def print_header():
    """Print validation header."""
    print()
    print("=" * 70)
    print(f"{Colors.BOLD}PitchTracker Setup Validator{Colors.RESET}")
    print("=" * 70)
    print()


def print_results(checks: List[ValidationCheck]):
    """Print validation results."""
    passed = [c for c in checks if c.passed]
    failed = [c for c in checks if not c.passed]

    print()
    print("-" * 70)
    print("Results:")
    print("-" * 70)
    print()

    for check in checks:
        print(check)

    print()
    print("=" * 70)

    if failed:
        print(f"{Colors.RED}✗ {len(failed)} checks failed{Colors.RESET}")
        print("=" * 70)
        print()
        print("Issues that need fixing:")
        print()
        for check in failed:
            print(f"  {Colors.YELLOW}⚠{Colors.RESET}  {check.name}")
            print(f"      Problem: {check.message}")
            if check.fix:
                print(f"      Fix: {Colors.BLUE}{check.fix}{Colors.RESET}")
            print()
    else:
        print(f"{Colors.GREEN}✓ All {len(passed)} checks passed!{Colors.RESET}")
        print("=" * 70)
        print()
        print("You're ready to use PitchTracker!")
        print()
        print("Next steps:")
        print(f"  1. Run Setup Wizard: {Colors.BLUE}python launcher.py{Colors.RESET}")
        print(f"  2. Or run main app: {Colors.BLUE}python main_window.py{Colors.RESET}")
        print()

    print("=" * 70)
    print()


def main():
    """Run all validation checks."""
    print_header()

    print("Running validation checks...")
    print()

    checks = []

    # Check 1: Python version
    print("  [1/7] Checking Python version...")
    checks.append(check_python_version())

    # Check 2: Dependencies
    print("  [2/7] Checking dependencies...")
    checks.append(check_dependencies())

    # Check 3: Config directory
    print("  [3/7] Checking config directory...")
    checks.append(check_config_directory())

    # Check 4: Default config
    print("  [4/7] Checking default configuration...")
    checks.append(check_default_config())

    # Check 5: Camera access
    print("  [5/7] Checking camera access...")
    checks.append(check_camera_access())

    # Check 6: Recordings directory
    print("  [6/7] Checking recordings directory...")
    checks.append(check_recordings_directory())

    # Check 7: Disk space
    print("  [7/7] Checking disk space...")
    checks.append(check_disk_space())

    # Print results
    print_results(checks)

    # Return exit code
    failed = [c for c in checks if not c.passed]
    return 0 if len(failed) == 0 else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        print("\n\nInterrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n{Colors.RED}FATAL ERROR:{Colors.RESET} {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
