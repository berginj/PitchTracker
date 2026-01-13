"""Radar gun integration stub (Bluetooth)."""

from __future__ import annotations

from typing import Optional, Protocol


class RadarGunClient(Protocol):
    """Expected interface for a radar gun provider."""

    def latest_speed_mph(self) -> Optional[float]:
        """Return the latest observed speed in mph, or None if unavailable."""


class NullRadarGun:
    """No-op radar client placeholder."""

    def latest_speed_mph(self) -> Optional[float]:
        return None
