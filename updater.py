"""Auto-update mechanism for PitchTracker.

Checks GitHub Releases for newer versions and provides download/install functionality.
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib.error import URLError
from urllib.request import urlopen

from loguru import logger

# Version information
CURRENT_VERSION = "1.0.0"
GITHUB_REPO = "berginj/PitchTracker"  # Update to actual repository
UPDATE_CHECK_URL = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"


def parse_version(version_str: str) -> tuple[int, ...]:
    """Parse version string into tuple for comparison.

    Args:
        version_str: Version string (e.g., "1.0.0" or "v1.0.0")

    Returns:
        Tuple of version numbers (e.g., (1, 0, 0))
    """
    # Remove 'v' prefix if present
    version_str = version_str.lstrip('v')

    # Split on dots and convert to integers
    try:
        return tuple(int(x) for x in version_str.split('.'))
    except ValueError:
        logger.warning(f"Invalid version string: {version_str}")
        return (0, 0, 0)


def is_newer_version(latest: str, current: str) -> bool:
    """Check if latest version is newer than current.

    Args:
        latest: Latest version string
        current: Current version string

    Returns:
        True if latest is newer than current
    """
    latest_tuple = parse_version(latest)
    current_tuple = parse_version(current)
    return latest_tuple > current_tuple


def check_for_updates(timeout: int = 5) -> dict:
    """Check GitHub Releases for newer version.

    Args:
        timeout: Request timeout in seconds

    Returns:
        Dictionary with update information:
        {
            'available': bool,
            'version': str,           # Latest version (if available)
            'download_url': str,      # Installer download URL
            'release_notes': str,     # Markdown release notes
            'release_date': str,      # ISO 8601 date
        }
    """
    result = {
        'available': False,
        'version': None,
        'download_url': None,
        'release_notes': None,
        'release_date': None,
    }

    try:
        logger.debug(f"Checking for updates at: {UPDATE_CHECK_URL}")

        # Fetch latest release info from GitHub API
        with urlopen(UPDATE_CHECK_URL, timeout=timeout) as response:
            if response.status != 200:
                logger.warning(f"Update check returned status {response.status}")
                return result

            data = json.loads(response.read().decode('utf-8'))

        # Extract version information
        latest_version = data.get('tag_name', '').lstrip('v')
        if not latest_version:
            logger.warning("No version tag found in latest release")
            return result

        logger.debug(f"Latest version: {latest_version}, Current: {CURRENT_VERSION}")

        # Check if newer version is available
        if not is_newer_version(latest_version, CURRENT_VERSION):
            logger.debug("Current version is up to date")
            return result

        # Find installer asset
        assets = data.get('assets', [])
        installer_asset = None

        for asset in assets:
            name = asset.get('name', '')
            if name.endswith('.exe') and 'Setup' in name:
                installer_asset = asset
                break

        if not installer_asset:
            logger.warning("No installer found in latest release")
            return result

        # Update available!
        result['available'] = True
        result['version'] = latest_version
        result['download_url'] = installer_asset.get('browser_download_url')
        result['release_notes'] = data.get('body', 'No release notes available.')
        result['release_date'] = data.get('published_at', '')

        logger.info(f"Update available: v{latest_version}")
        return result

    except URLError as e:
        logger.debug(f"Update check failed (network): {e}")
        # Fail silently if offline
        return result

    except json.JSONDecodeError as e:
        logger.warning(f"Update check failed (invalid JSON): {e}")
        return result

    except Exception as e:
        logger.error(f"Update check failed: {e}", exc_info=True)
        return result


def download_update(
    url: str,
    dest_path: Optional[Path] = None,
    progress_callback: Optional[callable] = None
) -> Optional[Path]:
    """Download update installer.

    Args:
        url: Download URL
        dest_path: Destination file path (default: temp file)
        progress_callback: Callback(bytes_downloaded, total_bytes)

    Returns:
        Path to downloaded file, or None if download failed
    """
    try:
        # Use temp file if no destination specified
        if dest_path is None:
            temp_file = tempfile.NamedTemporaryFile(
                mode='wb',
                suffix='.exe',
                prefix='PitchTracker-Setup-',
                delete=False
            )
            dest_path = Path(temp_file.name)
            temp_file.close()

        logger.info(f"Downloading update from: {url}")
        logger.debug(f"Destination: {dest_path}")

        # Download with progress tracking
        with urlopen(url, timeout=30) as response:
            total_size = int(response.headers.get('Content-Length', 0))
            bytes_downloaded = 0

            with open(dest_path, 'wb') as f:
                chunk_size = 8192
                while True:
                    chunk = response.read(chunk_size)
                    if not chunk:
                        break

                    f.write(chunk)
                    bytes_downloaded += len(chunk)

                    if progress_callback:
                        progress_callback(bytes_downloaded, total_size)

        logger.info(f"Update downloaded: {dest_path} ({bytes_downloaded} bytes)")
        return dest_path

    except Exception as e:
        logger.error(f"Download failed: {e}", exc_info=True)
        if dest_path and dest_path.exists():
            dest_path.unlink()  # Clean up partial download
        return None


def install_update(installer_path: Path, silent: bool = False) -> bool:
    """Launch installer to install update.

    Args:
        installer_path: Path to downloaded installer
        silent: Run installer in silent mode (no UI)

    Returns:
        True if installer launched successfully
    """
    try:
        logger.info(f"Launching installer: {installer_path}")

        # Build command line arguments
        args = [str(installer_path)]

        if silent:
            # Inno Setup silent installation
            args.append('/SILENT')
            args.append('/NORESTART')

        # Launch installer
        # Note: This will start the installer and return immediately
        # The installer will replace the running application
        subprocess.Popen(args)

        logger.info("Installer launched successfully")
        return True

    except Exception as e:
        logger.error(f"Failed to launch installer: {e}", exc_info=True)
        return False


# Version-specific helpers

def get_current_version() -> str:
    """Get current application version.

    Returns:
        Version string (e.g., "1.0.0")
    """
    return CURRENT_VERSION


def set_current_version(version: str) -> None:
    """Update current version (for testing).

    Args:
        version: New version string
    """
    global CURRENT_VERSION
    CURRENT_VERSION = version


# Example usage
if __name__ == "__main__":
    # Test update check
    print(f"Current version: {CURRENT_VERSION}")
    print("Checking for updates...")

    update_info = check_for_updates()

    if update_info['available']:
        print(f"\nUpdate available: v{update_info['version']}")
        print(f"Download: {update_info['download_url']}")
        print(f"Release date: {update_info['release_date']}")
        print(f"\nRelease notes:\n{update_info['release_notes']}")
    else:
        print("\nYou are using the latest version.")
