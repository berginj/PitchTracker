"""Automated screenshot capture for CoachWindow UI documentation.

This script launches the CoachWindow application and systematically captures
screenshots of all screens, dialogs, and modes for documentation purposes.
"""

import sys
import time
from pathlib import Path
from datetime import datetime

from PySide6 import QtCore, QtGui, QtWidgets

from ui.coaching.coach_window import CoachWindow
from ui.coaching.dialogs import SessionStartDialog
from ui.coaching.dialogs.settings_dialog import SettingsDialog
from ui.coaching.dialogs.lane_adjust_dialog import LaneAdjustDialog


class ScreenshotCapture:
    """Automated screenshot capture manager."""

    def __init__(self, output_dir: Path = None):
        """Initialize screenshot capture.

        Args:
            output_dir: Directory to save screenshots (default: screenshots/)
        """
        if output_dir is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_dir = Path(f"screenshots/coaching_{timestamp}")

        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        self.screenshot_count = 0
        print(f"Screenshots will be saved to: {self.output_dir}")

    def capture(self, widget: QtWidgets.QWidget, name: str, description: str = "") -> None:
        """Capture screenshot of a widget.

        Args:
            widget: Widget to capture
            name: Base filename (without extension)
            description: Optional description for the screenshot
        """
        # Ensure widget is visible and rendered
        QtWidgets.QApplication.processEvents()
        time.sleep(0.5)  # Allow time for rendering
        QtWidgets.QApplication.processEvents()

        # Capture screenshot
        pixmap = widget.grab()

        # Save with counter prefix for ordering
        self.screenshot_count += 1
        filename = f"{self.screenshot_count:02d}_{name}.png"
        filepath = self.output_dir / filename

        pixmap.save(str(filepath))

        print(f"[OK] Captured: {filename}")
        if description:
            print(f"  Description: {description}")

        # Save description to metadata file
        metadata_file = self.output_dir / "screenshots_metadata.txt"
        with open(metadata_file, 'a', encoding='utf-8') as f:
            f.write(f"{filename}: {description}\n")

    def wait(self, seconds: float = 1.0) -> None:
        """Wait for specified time with event processing."""
        end_time = time.time() + seconds
        while time.time() < end_time:
            QtWidgets.QApplication.processEvents()
            time.sleep(0.1)


def capture_coach_window_screenshots(backend: str = "sim"):
    """Capture all CoachWindow screenshots.

    Args:
        backend: Backend to use ("sim" for simulated cameras, "uvc" for real cameras)
    """
    app = QtWidgets.QApplication.instance()
    if app is None:
        app = QtWidgets.QApplication(sys.argv)

    capturer = ScreenshotCapture()

    print("\n" + "="*60)
    print("Starting CoachWindow Screenshot Capture")
    print("="*60 + "\n")

    # Create main window with simulated backend (no cameras needed)
    print("Launching CoachWindow...")
    window = CoachWindow(backend=backend)
    window.show()

    capturer.wait(1.5)

    # 1. Main dashboard (initial state)
    capturer.capture(
        window,
        "main_dashboard_initial",
        "Main coaching dashboard - Initial state (no session active)"
    )

    # 2. Try to capture session start dialog
    try:
        print("\nOpening Session Start Dialog...")
        session_dialog = SessionStartDialog(config=window._config, parent=window)
        session_dialog.show()
        capturer.wait(1.0)

        capturer.capture(
            session_dialog,
            "session_start_dialog",
            "Session Start Dialog - Configure new session with pitcher selection"
        )

        session_dialog.close()
        capturer.wait(0.5)
    except Exception as e:
        print(f"  [WARNING] Could not capture Session Start Dialog: {e}")

    # 3. Try to capture settings dialog
    try:
        print("\nOpening Settings Dialog...")
        settings_dialog = SettingsDialog(window._config, parent=window)
        settings_dialog.show()
        capturer.wait(1.0)

        capturer.capture(
            settings_dialog,
            "settings_dialog",
            "Settings Dialog - Application configuration and camera settings"
        )

        settings_dialog.close()
        capturer.wait(0.5)
    except Exception as e:
        print(f"  [WARNING] Could not capture Settings Dialog: {e}")

    # 4. Try to capture lane adjust dialog
    try:
        print("\nOpening Lane Adjust Dialog...")
        lane_dialog = LaneAdjustDialog(parent=window)
        lane_dialog.show()
        capturer.wait(1.0)

        capturer.capture(
            lane_dialog,
            "lane_adjust_dialog",
            "Lane Adjust Dialog - Configure camera positioning and ROI"
        )

        lane_dialog.close()
        capturer.wait(0.5)
    except Exception as e:
        print(f"  [WARNING] Could not capture Lane Adjust Dialog: {e}")

    # 5. Capture main window menus (if they exist)
    print("\nCapturing main window state...")

    # Try to access different viewing modes if available
    try:
        # Check if window has mode widgets
        if hasattr(window, '_mode_stack'):
            print("\nCapturing different viewing modes...")

            # Broadcast View
            if hasattr(window, '_broadcast_mode'):
                window._mode_stack.setCurrentWidget(window._broadcast_mode)
                capturer.wait(0.8)
                capturer.capture(
                    window,
                    "broadcast_view",
                    "Broadcast View - Spectator-friendly display mode"
                )

            # Session Progression View
            if hasattr(window, '_progression_mode'):
                window._mode_stack.setCurrentWidget(window._progression_mode)
                capturer.wait(0.8)
                capturer.capture(
                    window,
                    "session_progression_view",
                    "Session Progression View - Track pitch count and progress"
                )

            # Game Mode View
            if hasattr(window, '_game_mode'):
                window._mode_stack.setCurrentWidget(window._game_mode)
                capturer.wait(0.8)
                capturer.capture(
                    window,
                    "game_mode_view",
                    "Game Mode View - Interactive pitching games"
                )

                # Try to capture individual games
                if hasattr(window._game_mode, '_game_selector'):
                    games = [
                        ("Around the World", "around_world"),
                        ("Speed Challenge", "speed_challenge"),
                        ("Target Scoring", "target_scoring"),
                        ("Tic Tac Toe", "tic_tac_toe")
                    ]
                    for i, (game_title, game_name) in enumerate(games):
                        try:
                            # Select game from combo box
                            window._game_mode._game_selector.setCurrentIndex(i)
                            capturer.wait(0.8)
                            capturer.capture(
                                window,
                                f"game_{game_name}",
                                f"Game: {game_title}"
                            )
                        except Exception as game_err:
                            print(f"  [WARNING] Could not capture {game_title}: {game_err}")
    except Exception as e:
        print(f"  [WARNING] Could not capture mode views: {e}")

    # 6. Capture widgets individually (heat map, trajectory, etc.)
    print("\nCapturing individual widgets...")

    try:
        if hasattr(window, '_heat_map'):
            capturer.capture(
                window._heat_map,
                "widget_heatmap",
                "Heat Map Widget - Shows pitch location distribution"
            )
    except Exception as e:
        print(f"  [WARNING] Could not capture heat map: {e}")

    try:
        if hasattr(window, '_trajectory_widget'):
            capturer.capture(
                window._trajectory_widget,
                "widget_trajectory",
                "Trajectory Widget - Shows 3D pitch path visualization"
            )
    except Exception as e:
        print(f"  [WARNING] Could not capture trajectory widget: {e}")

    # 7. Final main window capture
    capturer.capture(
        window,
        "main_dashboard_final",
        "Main coaching dashboard - Final state"
    )

    print("\n" + "="*60)
    print(f"Screenshot capture complete!")
    print(f"Total screenshots: {capturer.screenshot_count}")
    print(f"Saved to: {capturer.output_dir}")
    print("="*60 + "\n")

    # Close window
    window.close()

    # Generate index HTML for easy viewing
    generate_screenshot_index(capturer.output_dir)

    return capturer.output_dir


def generate_screenshot_index(screenshot_dir: Path):
    """Generate HTML index for viewing screenshots.

    Args:
        screenshot_dir: Directory containing screenshots
    """
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>PitchTracker CoachWindow Screenshots</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1200px;
            margin: 40px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        h1 {{
            color: #333;
            border-bottom: 3px solid #2196F3;
            padding-bottom: 10px;
        }}
        .screenshot {{
            background: white;
            padding: 20px;
            margin: 20px 0;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        .screenshot h2 {{
            color: #2196F3;
            margin-top: 0;
        }}
        .screenshot img {{
            max-width: 100%;
            border: 1px solid #ddd;
            border-radius: 4px;
        }}
        .description {{
            color: #666;
            font-style: italic;
            margin: 10px 0;
        }}
        .metadata {{
            font-size: 12px;
            color: #999;
        }}
    </style>
</head>
<body>
    <h1>🎾 PitchTracker CoachWindow Screenshots</h1>
    <p><strong>Generated:</strong> {timestamp}</p>
    <p><strong>Total Screenshots:</strong> {count}</p>
"""

    # Read metadata
    metadata_file = screenshot_dir / "screenshots_metadata.txt"
    metadata = {}
    if metadata_file.exists():
        with open(metadata_file, 'r', encoding='utf-8') as f:
            for line in f:
                if ':' in line:
                    filename, description = line.strip().split(':', 1)
                    metadata[filename.strip()] = description.strip()

    # Get all PNG files
    screenshots = sorted(screenshot_dir.glob("*.png"))

    for screenshot in screenshots:
        filename = screenshot.name
        description = metadata.get(filename, "No description available")

        # Clean up filename for display title
        title = filename.replace('.png', '').replace('_', ' ').title()
        # Remove number prefix
        if ' ' in title:
            parts = title.split(' ', 1)
            if parts[0].isdigit():
                title = parts[1]

        html_content += f"""
    <div class="screenshot">
        <h2>{title}</h2>
        <p class="description">{description}</p>
        <img src="{filename}" alt="{title}">
        <p class="metadata">File: {filename}</p>
    </div>
"""

    html_content += """
</body>
</html>
"""

    # Write HTML file
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    html_content = html_content.format(
        timestamp=timestamp,
        count=len(screenshots)
    )

    index_file = screenshot_dir / "index.html"
    with open(index_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f"\n[OK] Generated screenshot index: {index_file}")
    print(f"  Open in browser to view all screenshots")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Capture CoachWindow screenshots")
    parser.add_argument(
        "--backend",
        default="sim",
        choices=["sim", "opencv", "uvc"],
        help="Backend to use (sim=simulated, opencv=webcam, uvc=USB cameras)"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output directory for screenshots"
    )

    args = parser.parse_args()

    output_dir = Path(args.output) if args.output else None

    try:
        screenshot_dir = capture_coach_window_screenshots(
            backend=args.backend
        )

        print(f"\n[OK] Success! Open {screenshot_dir / 'index.html'} in your browser")

    except Exception as e:
        print(f"\n[ERROR] Error during screenshot capture: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
