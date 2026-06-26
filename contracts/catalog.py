"""Typed contracts for the camera catalog.

The catalog is a publishable / pullable record of *supported camera models*
(model -> detected capabilities + known-good settings) plus a carry-over record
of *known physical devices* keyed by stable hardware id. It lets setup recognise
a camera the moment it is plugged in, seed step 1 (device select) and step 4
(focus/exposure lock) with known-good values, and keep the same physical camera
assigned to the same left/right side across sessions.

All dataclasses are frozen and JSON round-trippable via ``to_payload`` /
``from_payload`` so the catalog can be persisted locally and shared.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

CATALOG_SCHEMA_VERSION = "1.0"

# Stable left/right side labels for carry-over device assignment.
SIDE_LEFT = "left"
SIDE_RIGHT = "right"
SIDE_UNASSIGNED = ""


@dataclass(frozen=True)
class CameraMode:
    """A single supported capture mode.

    Attributes:
        width: Frame width in pixels.
        height: Frame height in pixels.
        fps: Frames per second.
    """

    width: int
    height: int
    fps: int

    def to_payload(self) -> Dict[str, Any]:
        return {"width": self.width, "height": self.height, "fps": self.fps}

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CameraMode":
        return cls(
            width=int(payload["width"]),
            height=int(payload["height"]),
            fps=int(payload["fps"]),
        )


@dataclass(frozen=True)
class CameraCapabilities:
    """Detected capabilities of a camera model.

    Attributes:
        supported_modes: Capture modes confirmed to work.
        controls: UVC control names the device exposes (e.g. "exposure").
        global_shutter: True/False if known, None if undetermined.
        sync_capable: True/False if the device supports hardware sync, else None.
    """

    supported_modes: Tuple[CameraMode, ...] = ()
    controls: Tuple[str, ...] = ()
    global_shutter: Optional[bool] = None
    sync_capable: Optional[bool] = None

    def best_mode(self) -> Optional[CameraMode]:
        """Return the highest-throughput mode (by pixels*fps), if any."""
        if not self.supported_modes:
            return None
        return max(self.supported_modes, key=lambda m: m.width * m.height * m.fps)

    def supports(self, width: int, height: int, fps: int) -> bool:
        """True if the given mode is in the supported set."""
        return any(m.width == width and m.height == height and m.fps == fps for m in self.supported_modes)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "supported_modes": [m.to_payload() for m in self.supported_modes],
            "controls": list(self.controls),
            "global_shutter": self.global_shutter,
            "sync_capable": self.sync_capable,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CameraCapabilities":
        return cls(
            supported_modes=tuple(CameraMode.from_payload(m) for m in payload.get("supported_modes", [])),
            controls=tuple(payload.get("controls", [])),
            global_shutter=payload.get("global_shutter"),
            sync_capable=payload.get("sync_capable"),
        )

    @classmethod
    def from_detected_modes(
        cls,
        modes: List[Tuple[int, int, int]],
        controls: Optional[List[str]] = None,
        global_shutter: Optional[bool] = None,
        sync_capable: Optional[bool] = None,
    ) -> "CameraCapabilities":
        """Build capabilities from raw ``(width, height, fps)`` detection output.

        This adapts the output of the live capability probe (which returns plain
        ``(w, h, fps)`` tuples) into the typed contract.
        """
        return cls(
            supported_modes=tuple(CameraMode(int(w), int(h), int(f)) for (w, h, f) in modes),
            controls=tuple(controls or ()),
            global_shutter=global_shutter,
            sync_capable=sync_capable,
        )


@dataclass(frozen=True)
class KnownGoodSettings:
    """Known-good camera settings for a recognised model.

    Seeds step 4 (focus/exposure/white-balance lock) so a recognised device can
    apply validated values instead of guessing.

    Attributes:
        exposure_us: Exposure time in microseconds.
        gain: Analog/digital gain.
        white_balance_k: White-balance color temperature in Kelvin.
        working_distance_in: Recommended camera-to-plate distance in inches.
        mode: Recommended capture mode, if any.
        notes: Free-form operator notes.
    """

    exposure_us: float
    gain: float
    white_balance_k: float
    working_distance_in: float
    mode: Optional[CameraMode] = None
    notes: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "exposure_us": self.exposure_us,
            "gain": self.gain,
            "white_balance_k": self.white_balance_k,
            "working_distance_in": self.working_distance_in,
            "mode": self.mode.to_payload() if self.mode else None,
            "notes": self.notes,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "KnownGoodSettings":
        mode = payload.get("mode")
        return cls(
            exposure_us=float(payload["exposure_us"]),
            gain=float(payload["gain"]),
            white_balance_k=float(payload["white_balance_k"]),
            working_distance_in=float(payload["working_distance_in"]),
            mode=CameraMode.from_payload(mode) if mode else None,
            notes=payload.get("notes", ""),
        )


@dataclass(frozen=True)
class CameraCatalogEntry:
    """A supported-camera-model entry in the publishable catalog.

    Attributes:
        model: Canonical model identifier (e.g. "ArduCam B0497 OV9281").
        vendor: Vendor/brand name.
        capabilities: Detected capabilities of the model.
        known_good: Optional known-good settings for the model.
        global_shutter: Convenience flag (also on capabilities) for quick filtering.
        match_names: Substrings that identify this model in a friendly name.
        notes: Free-form notes.
        schema_version: Catalog schema version.
    """

    model: str
    vendor: str = ""
    capabilities: CameraCapabilities = field(default_factory=CameraCapabilities)
    known_good: Optional[KnownGoodSettings] = None
    global_shutter: Optional[bool] = None
    match_names: Tuple[str, ...] = ()
    notes: str = ""
    schema_version: str = CATALOG_SCHEMA_VERSION

    def matches_name(self, friendly_name: str) -> bool:
        """True if ``friendly_name`` contains any of this entry's match tokens."""
        if not friendly_name:
            return False
        lowered = friendly_name.lower()
        return any(token.lower() in lowered for token in self.match_names)

    def to_payload(self) -> Dict[str, Any]:
        return {
            "model": self.model,
            "vendor": self.vendor,
            "capabilities": self.capabilities.to_payload(),
            "known_good": self.known_good.to_payload() if self.known_good else None,
            "global_shutter": self.global_shutter,
            "match_names": list(self.match_names),
            "notes": self.notes,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "CameraCatalogEntry":
        known_good = payload.get("known_good")
        return cls(
            model=payload["model"],
            vendor=payload.get("vendor", ""),
            capabilities=CameraCapabilities.from_payload(payload.get("capabilities", {})),
            known_good=KnownGoodSettings.from_payload(known_good) if known_good else None,
            global_shutter=payload.get("global_shutter"),
            match_names=tuple(payload.get("match_names", [])),
            notes=payload.get("notes", ""),
            schema_version=payload.get("schema_version", CATALOG_SCHEMA_VERSION),
        )


@dataclass(frozen=True)
class KnownDevice:
    """Carry-over state for a specific physical device, keyed by hardware id.

    Attributes:
        hardware_id: Stable identifier (UVC serial, or OpenCV index string).
        model: Catalog model this device was matched to, if recognised.
        friendly_name: Last-seen friendly name.
        side: Last assigned side (SIDE_LEFT / SIDE_RIGHT / SIDE_UNASSIGNED).
        last_seen_utc: ISO-8601 UTC timestamp the device was last seen.
    """

    hardware_id: str
    model: str = ""
    friendly_name: str = ""
    side: str = SIDE_UNASSIGNED
    last_seen_utc: str = ""

    def to_payload(self) -> Dict[str, Any]:
        return {
            "hardware_id": self.hardware_id,
            "model": self.model,
            "friendly_name": self.friendly_name,
            "side": self.side,
            "last_seen_utc": self.last_seen_utc,
        }

    @classmethod
    def from_payload(cls, payload: Dict[str, Any]) -> "KnownDevice":
        return cls(
            hardware_id=payload["hardware_id"],
            model=payload.get("model", ""),
            friendly_name=payload.get("friendly_name", ""),
            side=payload.get("side", SIDE_UNASSIGNED),
            last_seen_utc=payload.get("last_seen_utc", ""),
        )
