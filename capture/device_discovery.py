"""Windows PnP device discovery for UVC cameras."""

from __future__ import annotations

import json
import subprocess
from typing import List

from log_config.logger import get_logger

logger = get_logger(__name__)


def list_uvc_devices() -> list[dict[str, str]]:
    """Return UVC camera devices with friendly names and serials."""
    return _list_camera_devices()


def _list_camera_devices() -> list[dict[str, str]]:
    """List camera devices from Windows PnP system.

    Returns:
        List of camera device dictionaries with friendly_name, serial, manufacturer, etc.

    Note:
        - Tries "Camera" class first (fastest, most accurate)
        - Falls back to "Image" class if no cameras found
        - "Image" class includes scanners/printers, so filtering is important
    """
    devices = _query_pnp_devices("Camera")
    if not devices:
        devices = _query_pnp_devices("Image")
    output: list[dict[str, str]] = []
    for device in devices:
        friendly = (device.get("FriendlyName") or "").strip()
        instance = (device.get("InstanceId") or "").strip()
        serial = (device.get("Serial") or "").strip()
        manufacturer = (device.get("Manufacturer") or "").strip()
        description = (device.get("Description") or "").strip()
        hwids = device.get("HardwareIds") or ""

        if not friendly:
            continue

        if isinstance(hwids, list):
            hwids = " ".join(hwids)
        hwids = str(hwids).lower()

        # Filter out printers and scanners by hardware IDs
        if "class_07" in hwids or "class_09" in hwids:
            logger.debug(f"Skipping printer/hub device by HW ID: {friendly}")
            continue

        # Filter by manufacturer (common printer brands)
        mfg_lower = manufacturer.lower()
        printer_mfgs = [
            "brother",
            "hp inc",
            "hewlett-packard",
            "epson",
            "canon",
            "xerox",
            "konica",
            "ricoh",
            "sharp",
            "kyocera",
            "lexmark",
        ]
        if any(brand in mfg_lower for brand in printer_mfgs):
            name_lower = friendly.lower()
            if any(term in name_lower for term in ["printer", "scanner", "scan", "mfp", "multifunction"]):
                logger.info(f"Skipping printer device: {friendly} (Mfg: {manufacturer})")
                continue

        if not serial and instance:
            serial = instance.split("\\")[-1]

        device_info = {
            "friendly_name": friendly,
            "instance_id": instance,
            "serial": serial or friendly,
        }

        if manufacturer:
            device_info["manufacturer"] = manufacturer

        if description and description != friendly:
            device_info["description"] = description

        output.append(device_info)

    return output


def _query_pnp_devices(device_class: str) -> List[dict[str, str]]:
    """Query PnP devices via PowerShell.

    Args:
        device_class: Device class to query (Camera, Image, etc.)

    Returns:
        List of device dictionaries
    """
    command = (
        "Get-PnpDevice -Class "
        + device_class
        + " | Where-Object { $_.Present -eq $true -and ($_.Status -eq 'OK' -or $_.Status -eq $null) } "
        + "| ForEach-Object { "
        + "$dev = $_; "
        + "$props = Get-PnpDeviceProperty -InstanceId $dev.InstanceId -ErrorAction SilentlyContinue; "
        + "$serial = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_SerialNumber' } | Select-Object -First 1).Data; "
        + "$mfg = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_Manufacturer' } | Select-Object -First 1).Data; "
        + "$desc = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_DeviceDesc' } | Select-Object -First 1).Data; "
        + "$hwids = ($props | Where-Object { $_.KeyName -eq 'DEVPKEY_Device_HardwareIds' } | Select-Object -First 1).Data; "
        + "[pscustomobject]@{"
        + "FriendlyName=$dev.FriendlyName;"
        + "InstanceId=$dev.InstanceId;"
        + "Serial=$serial;"
        + "Manufacturer=$mfg;"
        + "Description=$desc;"
        + "HardwareIds=($hwids -join ' ');"
        + "Status=$dev.Status;"
        + "Present=$dev.Present"
        + "} "
        + "} | ConvertTo-Json"
    )

    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=10.0,
            check=False,
        )
    except subprocess.TimeoutExpired:
        logger.warning(f"PowerShell query for {device_class} devices timed out after 10s")
        return []

    if result.returncode != 0 or not result.stdout.strip():
        return []

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        logger.warning(f"Failed to parse PowerShell output for {device_class} devices")
        return []
    if isinstance(data, dict):
        return [data]
    return [item for item in data if isinstance(item, dict)]
