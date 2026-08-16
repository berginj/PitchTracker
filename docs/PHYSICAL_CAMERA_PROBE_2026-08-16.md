# Physical Camera Probe — 2026-08-16

This is a local hardware capability observation, not a physical accuracy
validation or approval. It contains no camera serials, frames, athlete data, or
facility identifiers.

| Field | Observation |
|---|---|
| Checkout | `codex/python313-mypy` at `c3220f4` |
| Runtime | Repository Python 3.13 virtual environment |
| UVC identity enumeration | No stable UVC identities returned; the Windows PnP query timed out |
| OpenCV indices | Indices `0` and `1` were readable through DirectShow |
| Camera 0 modes | 1080p60 requested and read successfully; 9/10 tested modes passed |
| Camera 1 modes | 720p60 maximum observed; all 1080p modes negotiated to 720p |
| Dual 1080p60 request | 151 frames per side in 5 seconds, approximately 30.2 FPS per side, zero read errors |

## Qualification result

The target requirement is two cameras at 1920×1080@60. This environment does
not qualify that requirement: the second camera negotiated to 1280×720 and the
dual capture achieved approximately 30 FPS. The result is therefore
**not-validated / rejected for the 1080p60 operating profile**.

The probe did not establish global-shutter behavior, stable hardware identity,
verified exposure/gain/focus/white-balance readback, synchronization quality,
pair-skew tails, USB-controller behavior, calibration quality, or pitch accuracy.
Those remain open under the physical-validation protocol.

## Next required run

Repeat with two matching global-shutter UVC cameras that expose stable hardware
IDs. Capture the complete checklist, including negotiated modes, control
readback, synchronization, cadence/drop denominators, pair-skew p50/p95/p99,
and an independent reference channel before considering any `VALIDATED` claim.
