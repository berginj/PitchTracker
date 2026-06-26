"""Camera catalog service: persisted, publishable supported-camera registry.

Responsibilities:

* Persist a local catalog of supported camera *models* (capabilities +
  known-good settings) and a set of *known physical devices* keyed by stable
  hardware id (carry-over state across sessions).
* Match a freshly probed device (friendly name) to a catalog model so setup can
  recognise it and pre-fill known-good values.
* Remember per-device left/right assignment by hardware id.
* Publish the catalog to a shareable file and pull/merge an external catalog so
  a known-good catalog can be distributed across rigs.

The service is intentionally free of camera/Qt dependencies so it is fully
unit-testable; live capability detection lives in tooling and is adapted into
``CameraCapabilities`` via ``CameraCapabilities.from_detected_modes``.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from contracts.catalog import (
    CATALOG_SCHEMA_VERSION,
    CameraCapabilities,
    CameraCatalogEntry,
    CameraMode,
    KnownDevice,
    KnownGoodSettings,
    SIDE_UNASSIGNED,
)
from exceptions import PitchTrackerError
from log_config.logger import get_logger

logger = get_logger(__name__)

DEFAULT_CATALOG_FILENAME = "camera_catalog.json"


class CatalogError(PitchTrackerError):
    """Raised when the camera catalog cannot be loaded or saved."""


def default_catalog_entries() -> List[CameraCatalogEntry]:
    """Seed entries for cameras known to be supported.

    The target rig uses ArduCam USB global-shutter cameras (fixed focus); seed a
    generic ArduCam global-shutter entry so the very first run already recognises
    the hardware. Known-good values are conservative starting points to be
    refined and re-published from a real calibration.
    """
    arducam_global_shutter = CameraCatalogEntry(
        model="ArduCam USB Global Shutter",
        vendor="ArduCam",
        capabilities=CameraCapabilities(
            supported_modes=(
                CameraMode(1280, 800, 60),
                CameraMode(640, 480, 120),
            ),
            controls=("exposure", "gain", "white_balance"),
            global_shutter=True,
            sync_capable=False,
        ),
        known_good=KnownGoodSettings(
            exposure_us=4000.0,
            gain=8.0,
            white_balance_k=4600.0,
            working_distance_in=120.0,
            mode=CameraMode(1280, 800, 60),
            notes="Conservative starting point; refine from a real calibration.",
        ),
        global_shutter=True,
        match_names=("arducam", "global shutter", "ov9281", "ov2311"),
        notes="Seed entry for ArduCam USB global-shutter fixed-focus cameras.",
    )
    return [arducam_global_shutter]


class CameraCatalogService:
    """Loads, persists, matches, and shares the camera catalog."""

    def __init__(self, catalog_path: Optional[Path] = None, seed_defaults: bool = True):
        """Initialise the service.

        Args:
            catalog_path: Path to the catalog JSON. Defaults to
                ``configs/camera_catalog.json``.
            seed_defaults: When the catalog file does not exist, seed it with
                :func:`default_catalog_entries` in memory (not written until
                :meth:`save`).
        """
        self._path = catalog_path or (Path("configs") / DEFAULT_CATALOG_FILENAME)
        self._entries: Dict[str, CameraCatalogEntry] = {}
        self._devices: Dict[str, KnownDevice] = {}
        self._loaded = False
        self._seed_defaults = seed_defaults

    # -- Persistence ---------------------------------------------------------

    @property
    def path(self) -> Path:
        return self._path

    def load(self) -> None:
        """Load the catalog from disk, seeding defaults if it is absent."""
        if not self._path.exists():
            if self._seed_defaults:
                for entry in default_catalog_entries():
                    self._entries[entry.model] = entry
                logger.info("Camera catalog not found; seeded {} default entries", len(self._entries))
            self._loaded = True
            return
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"Failed to read camera catalog at {self._path}: {exc}") from exc

        self._entries = {entry["model"]: CameraCatalogEntry.from_payload(entry) for entry in data.get("entries", [])}
        self._devices = {dev["hardware_id"]: KnownDevice.from_payload(dev) for dev in data.get("devices", [])}
        self._loaded = True
        logger.info(
            "Loaded camera catalog: {} entries, {} known devices from {}",
            len(self._entries),
            len(self._devices),
            self._path,
        )

    def save(self) -> None:
        """Persist the catalog to disk (creates parent directories)."""
        self._ensure_loaded()
        payload = {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "entries": [e.to_payload() for e in self._entries.values()],
            "devices": [d.to_payload() for d in self._devices.values()],
        }
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise CatalogError(f"Failed to write camera catalog at {self._path}: {exc}") from exc
        logger.info("Saved camera catalog to {}", self._path)

    def _ensure_loaded(self) -> None:
        if not self._loaded:
            self.load()

    # -- Catalog entries -----------------------------------------------------

    def entries(self) -> List[CameraCatalogEntry]:
        """All catalog model entries."""
        self._ensure_loaded()
        return list(self._entries.values())

    def get_entry(self, model: str) -> Optional[CameraCatalogEntry]:
        """Return the entry for ``model`` if present."""
        self._ensure_loaded()
        return self._entries.get(model)

    def add_entry(self, entry: CameraCatalogEntry, overwrite: bool = True) -> bool:
        """Add or update a catalog entry.

        Returns:
            True if the entry was added/updated, False if it already existed and
            ``overwrite`` was False.
        """
        self._ensure_loaded()
        if entry.model in self._entries and not overwrite:
            return False
        self._entries[entry.model] = entry
        return True

    def match_model(self, friendly_name: str) -> Optional[CameraCatalogEntry]:
        """Return the catalog entry whose match tokens match ``friendly_name``."""
        self._ensure_loaded()
        for entry in self._entries.values():
            if entry.matches_name(friendly_name):
                return entry
        return None

    # -- Known devices (carry-over by hardware id) ---------------------------

    def known_devices(self) -> List[KnownDevice]:
        """All remembered physical devices."""
        self._ensure_loaded()
        return list(self._devices.values())

    def get_device(self, hardware_id: str) -> Optional[KnownDevice]:
        """Return the remembered device for ``hardware_id`` if present."""
        self._ensure_loaded()
        return self._devices.get(hardware_id)

    def remember_device(
        self,
        hardware_id: str,
        friendly_name: str = "",
        model: Optional[str] = None,
        side: Optional[str] = None,
    ) -> KnownDevice:
        """Record/refresh carry-over state for a physical device.

        When ``model`` is not supplied, the device's friendly name is matched
        against the catalog to fill it in. Existing ``side`` is preserved unless
        a new ``side`` is given.

        Returns:
            The stored :class:`KnownDevice`.
        """
        if not hardware_id:
            raise CatalogError("remember_device requires a non-empty hardware_id")
        self._ensure_loaded()

        existing = self._devices.get(hardware_id)
        resolved_model = model
        if resolved_model is None:
            match = self.match_model(friendly_name) if friendly_name else None
            resolved_model = match.model if match else (existing.model if existing else "")

        device = KnownDevice(
            hardware_id=hardware_id,
            model=resolved_model,
            friendly_name=friendly_name or (existing.friendly_name if existing else ""),
            side=side if side is not None else (existing.side if existing else SIDE_UNASSIGNED),
            last_seen_utc=datetime.now(timezone.utc).isoformat(),
        )
        self._devices[hardware_id] = device
        return device

    def assign_side(self, hardware_id: str, side: str) -> KnownDevice:
        """Assign ``side`` (left/right) to a remembered device."""
        return self.remember_device(hardware_id, side=side)

    def known_good_for(self, hardware_id: str) -> Optional[KnownGoodSettings]:
        """Return known-good settings for a device's matched model, if any."""
        self._ensure_loaded()
        device = self._devices.get(hardware_id)
        if not device or not device.model:
            return None
        entry = self._entries.get(device.model)
        return entry.known_good if entry else None

    # -- Publish / pull ------------------------------------------------------

    def publish(self, dest: Path) -> Path:
        """Write the catalog *entries* (not local devices) to a shareable file.

        Device carry-over state is intentionally excluded from published
        catalogs since hardware ids are local/private.

        Returns:
            The destination path written.
        """
        self._ensure_loaded()
        payload = {
            "schema_version": CATALOG_SCHEMA_VERSION,
            "entries": [e.to_payload() for e in self._entries.values()],
        }
        try:
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        except OSError as exc:
            raise CatalogError(f"Failed to publish catalog to {dest}: {exc}") from exc
        logger.info("Published {} catalog entries to {}", len(self._entries), dest)
        return dest

    def pull(self, source: Path, overwrite: bool = False) -> int:
        """Merge catalog entries from an external file into this catalog.

        Args:
            source: Path to a published catalog file.
            overwrite: When True, incoming entries replace existing models of the
                same name; when False, existing models are kept.

        Returns:
            Number of entries added or updated.
        """
        self._ensure_loaded()
        try:
            data = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise CatalogError(f"Failed to pull catalog from {source}: {exc}") from exc

        merged = 0
        for raw in data.get("entries", []):
            entry = CameraCatalogEntry.from_payload(raw)
            if self.add_entry(entry, overwrite=overwrite):
                merged += 1
        logger.info("Pulled {} catalog entries from {}", merged, source)
        return merged
