"""Real-backend adapter providers for the canonical stereo setup workflow.

These convert live hardware backends into the Qt-free snapshot dataclasses that
the camera-select and paired-preview step widgets render. They are injected into
the widgets by the live wizard; the registry's test-safe defaults in
:mod:`ui.setup.stereo_steps` stay empty so the synthetic step tests never touch
hardware.

Every adapter takes its hardware dependency as an injected parameter so the
logic is unit-testable with fakes and the :class:`SimulatedCamera` backend.

This package re-exports the full public API previously available from
``ui.setup.providers`` as a stable facade.
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
from ui.setup.providers.context import (  # noqa: F401
    LiveSetupContext,
    _new_profile_id,
    _effective_pixfmt,
    _normalize_mode,
    _setup_payload,
)
from ui.setup.providers import profile as _profile  # noqa: F401
from ui.setup.providers.wiring import (  # noqa: F401
    build_live_stereo_step_widgets,
)

__all__ = [
    "DeviceLister",
    "PreviewProvider",
    "LiveSetupContext",
    "build_live_stereo_step_widgets",
    "capture_paired_preview",
    "discover_camera_selection",
    "make_camera_preview_provider",
    "simulated_paired_preview",
]
