"""Feature flags for staged TAG Sports integrations."""

from __future__ import annotations

import os
from dataclasses import dataclass


def _env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class TagSportsFeatureFlags:
    """Feature flags that gate staged TAG integrations."""

    cloud_sync_enabled: bool = False
    bluetooth_enabled: bool = False

    @classmethod
    def from_env(cls) -> "TagSportsFeatureFlags":
        """Build feature flags from environment variables."""
        return cls(
            cloud_sync_enabled=_env_flag("PITCHTRACKER_TAG_CLOUD_SYNC_ENABLED"),
            bluetooth_enabled=_env_flag("PITCHTRACKER_TAG_BLE_ENABLED"),
        )
