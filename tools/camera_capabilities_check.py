#!/usr/bin/env python
"""Interactively probe local cameras and write a capability report.

This is a hardware qualification aid. Its observations are not physical
validation and it does not transmit camera identities, frames, or reports.
"""

from __future__ import annotations

import logging
import sys
import time
from pathlib import Path
from typing import Any

import cv2

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.camera_capability_probes import (  # noqa: E402
    enumerate_cameras,
    test_camera_modes,
    test_dual_camera,
    test_memory_usage,
)
from ui.device_utils import is_arducam_device  # noqa: E402

logger = logging.getLogger(__name__)


def setup_logging(log_dir: Path) -> Path:
    """Configure detailed file logging and ASCII-safe console logging."""
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "capability_test.log"
    detailed = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    simple = logging.Formatter("%(levelname)s: %(message)s")
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(detailed)
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(simple)
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)
    logger.info("Logging initialized. Log file: %s", log_file)
    logger.debug("Python version: %s", sys.version)
    logger.debug("OpenCV version: %s", cv2.__version__)
    return log_file


def print_camera_enumeration(
    camera_info: dict[int, dict[str, Any]],
) -> None:
    """Print an ASCII-only camera identity table."""
    print("\n" + "=" * 100)
    print("CAMERA ENUMERATION")
    print("=" * 100)
    print(f"{'Index':<8} {'Available':<12} {'Backend':<20} " f"{'Manufacturer':<20} {'Name':<40}")
    print("-" * 100)
    arducam_count = 0
    for index in sorted(camera_info):
        info = camera_info[index]
        available = "Yes" if info["available"] else "No"
        name = str(info["name"])
        manufacturer = str(info.get("manufacturer", "Unknown"))[:18]
        if is_arducam_device(name):
            name = f"ArduCam: {name}"
            arducam_count += 1
        print(f"{index:<8} {available:<12} {info['backend']:<20} " f"{manufacturer:<20} {name:<40}")
    print("-" * 100)
    if arducam_count:
        print(f"Found {arducam_count} ArduCam device(s)")
    print("=" * 100)
    print()


def _append_enumeration_report(
    report_lines: list[str],
    camera_info: dict[int, dict[str, Any]],
) -> None:
    report_lines.extend(
        (
            "\n\nCAMERA ENUMERATION",
            "=" * 100,
            (f"{'Index':<8} {'Available':<12} {'Backend':<20} " f"{'Manufacturer':<20} {'Name':<40}"),
            "-" * 100,
        )
    )
    arducam_count = 0
    for index in sorted(camera_info):
        info = camera_info[index]
        name = str(info["name"])
        if is_arducam_device(name):
            arducam_count += 1
        if "serial" in info:
            name += f" (SN: {info['serial']})"
        report_lines.append(
            f"{index:<8} {'Yes' if info['available'] else 'No':<12} "
            f"{info['backend']:<20} "
            f"{info.get('manufacturer', 'Unknown'):<20} {name:<40}"
        )
    report_lines.append("-" * 100)
    if arducam_count:
        report_lines.append(f"ArduCam devices found: {arducam_count}")
    report_lines.append("=" * 100)


def _probe_backend(
    backend_name: str,
    backend: int,
    camera_info: dict[int, dict[str, Any]],
    report_lines: list[str],
) -> None:
    print(f"\n\n{'=' * 70}")
    print(f"Testing with {backend_name} backend")
    print("=" * 70)
    report_lines.extend((f"\n\n{'=' * 70}", f"Backend: {backend_name}", "=" * 70))
    supported_by_camera = {}
    for camera_index, info in camera_info.items():
        camera_name = str(info.get("name", f"Camera {camera_index}"))
        supported = test_camera_modes(
            camera_index,
            backend,
            camera_name=camera_name,
        )
        supported_by_camera[camera_index] = supported
        label = f"Camera {camera_index}"
        if camera_name != label:
            label = f"{label} ({camera_name})"
        report_lines.append(f"\n{label} Supported Modes ({len(supported)}):")
        report_lines.extend(f"  - {width}x{height}@{fps}fps" for width, height, fps in supported)

    common_modes = set(supported_by_camera.get(0, ())) & set(supported_by_camera.get(1, ()))
    report_lines.append(f"\nCommon Supported Modes ({len(common_modes)}):")
    for width, height, fps in sorted(common_modes):
        report_lines.append(f"\n{width}x{height}@{fps}fps:")
        memory = test_memory_usage(
            0,
            width,
            height,
            fps,
            duration_sec=5,
            backend=backend,
        )
        if memory["success"]:
            report_lines.append(f"  Memory: {memory['delta_mb']:.1f} MB")
            report_lines.append(f"  Effective FPS: {memory['effective_fps']:.1f}")
        dual = test_dual_camera(
            width,
            height,
            fps,
            duration_sec=5,
            backend=backend,
        )
        if dual["success"]:
            report_lines.append(
                "  Dual Camera: "
                f"LEFT={dual['effective_fps_left']:.1f}fps, "
                f"RIGHT={dual['effective_fps_right']:.1f}fps, "
                f"Errors={dual['errors']}"
            )


def main() -> int:
    """Run interactive local probes and write the same report artifacts."""
    print("=" * 70)
    print("Camera Capability Testing")
    print("=" * 70)
    output_dir = Path("camera_tests")
    output_dir.mkdir(exist_ok=True)
    log_file = setup_logging(output_dir)
    print("\nHow many cameras do you want to test? (default: 6 for cameras 0-5)")
    try:
        num_cameras = int(input("Enter number: ") or "6")
    except ValueError:
        num_cameras = 6
        print(f"Using default: {num_cameras} cameras")

    print("\nEnumerating cameras...")
    camera_info = enumerate_cameras(num_cameras)
    print_camera_enumeration(camera_info)
    report_lines = [
        "=" * 70,
        "CAMERA CAPABILITY TEST REPORT",
        f"Date: {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"Testing cameras: 0 to {num_cameras - 1}",
        "=" * 70,
    ]
    _append_enumeration_report(report_lines, camera_info)
    for backend_name, backend in (
        ("DirectShow", cv2.CAP_DSHOW),
        ("Media Foundation", cv2.CAP_MSMF),
    ):
        _probe_backend(
            backend_name,
            backend,
            camera_info,
            report_lines,
        )

    report_path = output_dir / "capability_report.txt"
    report_path.write_text("\n".join(report_lines), encoding="utf-8")
    logger.info("Camera Capability Testing Complete")
    logger.info("Report: %s", report_path)
    logger.info("Log file: %s", log_file)
    print(f"\n\n{'=' * 70}")
    print(f"Report saved to: {report_path}")
    print(f"Log file saved to: {log_file}")
    print("=" * 70)
    print("Hardware validation is manual; no result is physical validation.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
