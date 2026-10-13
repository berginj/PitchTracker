"""Reusable discovery and diagnostic adapters; guided setup owns the workflow.

Hardware dependencies remain injectable for deterministic tests. The older
ten-stage widget registry has been retired; these helpers are not an entry point.
"""

from ui.setup.providers.discovery import (  # noqa: F401
    DeviceLister,
    discover_camera_selection,
)
from ui.setup.providers.preview import (  # noqa: F401
    PreviewProvider,
    capture_paired_preview,
    make_camera_preview_provider,
    simulated_paired_preview,
)
from ui.setup.providers.context import LiveSetupContext  # noqa: F401
from ui.setup.providers.support import (  # noqa: F401
    _new_profile_id,
    _effective_pixfmt,
    _normalize_mode,
    _setup_payload,
)
from ui.setup.providers import profile as _profile  # noqa: F401

__all__ = [
    "DeviceLister",
    "PreviewProvider",
    "LiveSetupContext",
    "capture_paired_preview",
    "discover_camera_selection",
    "make_camera_preview_provider",
    "simulated_paired_preview",
]
