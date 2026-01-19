"""Helper script to check for recordings and session data."""

import sys
from pathlib import Path
from datetime import datetime

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8')

def check_recordings():
    """Check for any recordings in the recordings directory."""
    record_dir = Path("recordings")

    print("=" * 80)
    print("PITCHTRACKER RECORDING CHECK")
    print("=" * 80)

    if not record_dir.exists():
        print("\n[X] NO RECORDINGS DIRECTORY FOUND")
        print(f"   Expected location: {record_dir.absolute()}")
        print("\n[NOTE] This means either:")
        print("   1. You haven't clicked 'Start Recording' yet")
        print("   2. The recording failed to start")
        print("\n[TIP] Steps to verify:")
        print("   - Open coaching app")
        print("   - Click 'Setup Session'")
        print("   - Select cameras and click OK")
        print("   - Click 'Start Recording' (not just setup)")
        print("   - Look for red '● Recording' indicator")
        return False

    # List all sessions
    sessions = sorted(record_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)

    if not sessions:
        print(f"\n[DIR] Recordings directory exists: {record_dir.absolute()}")
        print("   But NO SESSION FOLDERS found inside")
        print("\n[TIP] The directory was created but no recording was started")
        return False

    print(f"\n[OK] Found {len(sessions)} session(s) in: {record_dir.absolute()}")
    print("\n" + "=" * 80)

    for i, session_dir in enumerate(sessions[:5], 1):  # Show up to 5 most recent
        print(f"\nSession {i}: {session_dir.name}")
        print("-" * 80)

        # Check for video files
        left_video = session_dir / "session_left.avi"
        right_video = session_dir / "session_right.avi"

        if left_video.exists():
            size_mb = left_video.stat().st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(left_video.stat().st_mtime)
            print(f"   [+] Left camera:  {left_video.name} ({size_mb:.1f} MB)")
            print(f"     Modified:     {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"   [-] Left camera:  MISSING")

        if right_video.exists():
            size_mb = right_video.stat().st_size / (1024 * 1024)
            modified = datetime.fromtimestamp(right_video.stat().st_mtime)
            print(f"   [+] Right camera: {right_video.name} ({size_mb:.1f} MB)")
            print(f"     Modified:     {modified.strftime('%Y-%m-%d %H:%M:%S')}")
        else:
            print(f"   [-] Right camera: MISSING")

        # Check for CSV files
        left_csv = session_dir / "session_left_timestamps.csv"
        right_csv = session_dir / "session_right_timestamps.csv"

        if left_csv.exists():
            lines = len(left_csv.read_text().splitlines())
            print(f"   [+] Left CSV:     {lines} frames logged")

        if right_csv.exists():
            lines = len(right_csv.read_text().splitlines())
            print(f"   [+] Right CSV:    {lines} frames logged")

        # Check for manifest
        manifest = session_dir / "manifest.json"
        if manifest.exists():
            print(f"   [+] Manifest:     {manifest.name}")

        # List all files in session
        all_files = list(session_dir.iterdir())
        print(f"\n   Total files:    {len(all_files)}")

        # Check if video files are small (might indicate recording issue)
        if left_video.exists() and left_video.stat().st_size < 1024 * 1024:  # Less than 1MB
            print(f"\n   [!]  WARNING: Left video is very small ({left_video.stat().st_size / 1024:.1f} KB)")
            print(f"       This might indicate recording stopped early or failed")

        if right_video.exists() and right_video.stat().st_size < 1024 * 1024:  # Less than 1MB
            print(f"\n   [!]  WARNING: Right video is very small ({right_video.stat().st_size / 1024:.1f} KB)")
            print(f"       This might indicate recording stopped early or failed")

    print("\n" + "=" * 80)
    print("MOST RECENT SESSION LOCATION:")
    print(f"   {sessions[0].absolute()}")
    print("=" * 80)

    return True

if __name__ == "__main__":
    try:
        has_recordings = check_recordings()
        sys.exit(0 if has_recordings else 1)
    except Exception as e:
        print(f"\n[X] Error checking recordings: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(2)
