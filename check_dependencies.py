#!/usr/bin/env python3
"""Check if all required dependencies are installed."""

import sys
from importlib import import_module

REQUIRED_PACKAGES = [
    ('cv2', 'opencv-contrib-python'),
    ('numpy', 'numpy'),
    ('scipy', 'scipy'),
    ('yaml', 'PyYAML'),
    ('PySide6', 'PySide6'),
    ('PIL', 'Pillow'),
    ('sklearn', 'scikit-learn'),
    ('matplotlib', 'matplotlib'),
    ('loguru', 'loguru'),
    ('jsonschema', 'jsonschema'),
    ('psutil', 'psutil'),
]

def check_dependencies():
    """Check if all required packages are installed."""
    missing = []
    installed = []

    print("Checking dependencies...\n")

    for module_name, package_name in REQUIRED_PACKAGES:
        try:
            mod = import_module(module_name)
            version = getattr(mod, '__version__', 'unknown')
            installed.append((package_name, version))
            print(f"[OK] {package_name:25} {version}")
        except ImportError:
            missing.append(package_name)
            print(f"[MISSING] {package_name:25} NOT FOUND")

    print("\n" + "="*60)

    if missing:
        print(f"\n[ERROR] Missing {len(missing)} package(s):")
        for pkg in missing:
            print(f"   - {pkg}")
        print("\nInstall with:")
        print(f"   pip install {' '.join(missing)}")
        return False
    else:
        print(f"\n[SUCCESS] All {len(installed)} required packages are installed!")
        return True

if __name__ == "__main__":
    success = check_dependencies()
    sys.exit(0 if success else 1)
