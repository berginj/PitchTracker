"""Shared typed helpers for live setup providers."""

from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import TYPE_CHECKING, Any, Iterable, Optional, Protocol

from contracts.catalog import KnownDevice

if TYPE_CHECKING:
    from configs.settings import AppConfig


class CameraCatalog(Protocol):
    """Narrow catalog boundary required by the setup workflow."""

    def known_devices(self) -> Iterable[KnownDevice]: ...

    def remember_device(
        self,
        hardware_id: str,
        friendly_name: str = "",
        model: Optional[str] = None,
        side: Optional[str] = None,
    ) -> KnownDevice: ...

    def save(self) -> None: ...


def _new_profile_id() -> str:
    return (
        "rig_"
        + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
        + "_"
        + uuid.uuid4().hex[:12]
    )


def _effective_pixfmt(config: "AppConfig") -> str:
    pixfmt = config.camera.pixfmt
    return "YUYV" if config.camera.color_mode and pixfmt == "GRAY8" else pixfmt


def _normalize_mode(mode: Optional[dict[str, Any]]) -> dict[str, Any]:
    normalized = dict(mode or {})
    if str(normalized.get("pixfmt") or "").upper() == "YUY2":
        normalized["pixfmt"] = "YUYV"
    if "fps" in normalized:
        normalized["fps"] = float(normalized["fps"])
    return normalized


def _setup_payload(value: Any) -> Any:
    if value is None:
        return None
    if hasattr(value, "to_payload") and callable(value.to_payload):
        return value.to_payload()
    if hasattr(value, "__dict__"):
        return dict(value.__dict__)
    return value
