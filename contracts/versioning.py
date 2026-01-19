"""Schema and application version metadata for serialized contracts."""

from __future__ import annotations

from typing import Any, Dict

SCHEMA_VERSION = "1.2.0"
APP_VERSION = "1.3.0"


def make_envelope(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Wrap a payload with schema/app versions for serialization."""
    return {
        "schema_version": SCHEMA_VERSION,
        "app_version": APP_VERSION,
        "payload": payload,
    }
