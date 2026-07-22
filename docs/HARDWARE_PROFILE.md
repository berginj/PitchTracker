# PitchTracker Candidate Hardware Qualification Profile

**Last reviewed:** 2026-07-22

**Applies to:** v2.0.0 testing

**Status:** Candidate requirements; no public known-good hardware claim yet

This guide defines what hardware may enter PitchTracker field qualification. It
is not a shopping endorsement and does not establish measurement accuracy.
Hardware becomes known-good only after a report satisfies the setup,
repeatability, and independent physical-reference requirements in the
[roadmap](ROADMAP.md).

## Before purchasing cameras

Do not purchase cameras solely because they are USB/UVC compatible or advertise
a high frame rate. A field-validation candidate must meet every required camera
property below, and the exact physical pair must still pass onsite setup and
validation.

PitchTracker's local catalog currently recognizes a generic **ArduCam USB global
shutter** family through names including `ArduCam`, `global shutter`, `OV9281`,
and `OV2311`. This seed entry helps discovery and recommendation; it is not proof
that an individual model, firmware revision, USB path, or camera pair is
validated.

Before ordering a specific model, confirm its published sensor, supported UVC
modes, control behavior, lens/focus arrangement, and stable hardware identity.
When uncertain, add the proposed model to
[global-shutter qualification issue #9](https://github.com/berginj/PitchTracker/issues/9)
before purchase.

## Required camera properties

Both cameras must be the same model and hardware revision where practical.

| Property | Requirement | Why it matters |
|---|---|---|
| Shutter | Documented global shutter | Rolling-shutter distortion corrupts fast-ball geometry. |
| Identity | Stable serial or hardware ID | Index-only selection can change after reconnect or reboot. |
| Interface | UVC/DirectShow mode observable by PitchTracker | Requested and negotiated modes must be recorded. |
| Frame rate | At least 60 FPS at the intended resolution | Lower rates reduce temporal evidence for a pitch. |
| Resolution | At least 1280×720, with the exact mode verified | Discovery alone does not prove the camera negotiated the requested mode. |
| Exposure | Manual or lockable, with readback when supported | Auto-exposure can create blur and mismatched images. |
| Gain | Manual or lockable, with readback when supported | Unbounded gain changes detection noise. |
| Focus | Fixed or mechanically/manual lockable | Autofocus hunting changes image geometry and sharpness. |
| Pixel format | Explicitly negotiated and recorded | Format conversion and bandwidth affect timing and image evidence. |
| Synchronization | Pair skew measured; hardware sync recorded if present | Global shutter does not by itself synchronize two independent USB cameras. |

PitchTracker's default runtime request is 1280×720 at 60 FPS. The seeded
ArduCam catalog entry also lists 1280×800 at 60 FPS and 640×480 at 120 FPS as
candidate modes. The setup snapshot must record what each connected device
actually negotiates; it must not substitute catalog values for observed values.

## Hardware that is not recommended for validation

Do not use the following as the basis for a physical accuracy claim:

- Logitech C920/C922, Logitech BRIO, Microsoft LifeCam, or other conventional
  rolling-shutter webcams.
- A camera whose shutter type is unknown.
- Mixed camera models or revisions unless the mismatch is explicitly studied.
- A pair selected only through unstable OpenCV indexes.
- A device that cannot sustain the requested mode on the onsite USB topology.
- A catalog match without verified negotiated mode and control readback.

Such devices may be useful for UI exploration or simulator-adjacent development,
but results must remain diagnostic and must not be labeled `VALIDATED`.

## Computer and USB requirements

Use a 64-bit Windows 10 or Windows 11 system with:

- a modern four-core-or-better CPU;
- at least 16 GB RAM for field qualification;
- an SSD with enough free space for the planned recordings and evidence bundle;
- two USB 3.x connections, preferably on separate host-controller paths;
- AC power and a performance-oriented power profile during capture; and
- current camera, chipset, and USB-controller drivers.

Avoid unpowered hubs. If a hub or extension is unavoidable, record its make,
model, power arrangement, cable lengths, and topology. Setup must measure actual
FPS, dropped frames, cadence jitter, unmatched frames, and pair-skew tails under
the final topology.

## Physical rig requirements

The field rig should include:

- rigid camera mounts that cannot shift during a session;
- a measured stereo baseline and working distance;
- a flat, dimensionally verified ChArUco calibration target;
- repeatable camera orientation and placement references;
- controlled or measured lighting;
- protected cable routing and strain relief; and
- an independent calibrated reference channel for physical confirmation.

Record all relevant dimensions and units. A calibration that merely completes
is not sufficient: reprojection quality, overlap, field alignment, focus,
exposure agreement, and synchronization must pass their configured gates.

## Setup and qualification evidence

For each candidate pair, archive or locally retain a privacy-reviewed evidence
package containing:

1. PitchTracker commit/version and setup-snapshot fingerprint.
2. Camera vendor, model, revision, firmware, and anonymized stable IDs.
3. Windows version, driver versions, and USB-controller/topology information.
4. Requested and negotiated resolution, FPS, and pixel format for each camera.
5. Exposure, gain, white-balance, focus, and auto-control state with provenance.
6. Calibration artifact fingerprints and quality metrics.
7. Frame totals and explicit denominators for paired, unmatched, rejected, and
   dropped frames.
8. Achieved FPS, cadence jitter, and pair-skew p50/p95/p99.
9. Reconnect and repeated-start/stop results.
10. Results after at least one intentional poor-setup condition and correction.

Unavailable facts must be recorded as unavailable with a reason. Do not infer a
capability from a product name or silently fill an observation with a default.

## Qualification states

- **Discovered:** the device can be enumerated.
- **Recognized:** the catalog matches the reported identity.
- **Operational:** the exact pair passes setup gates for the current snapshot.
- **Validated:** an independent, predeclared physical confirmation dataset passes
  every required threshold and is approved for the exact evidence fingerprint.

Only the final state supports a physical accuracy claim, and only within the
validated operating envelope. A previously validated model does not automatically
validate a different physical pair, firmware revision, USB topology, or setup.

## Reporting results

- Use [issue #9](https://github.com/berginj/PitchTracker/issues/9) for camera,
  setup, reconnect, and recovery qualification.
- Use [issue #10](https://github.com/berginj/PitchTracker/issues/10) for independent
  speed and plate-location confirmation.
- Follow [TESTING_NEEDED.md](TESTING_NEEDED.md) for privacy-safe reporting.
- Follow [PHYSICAL_VALIDATION_PROTOCOL_V2.md](PHYSICAL_VALIDATION_PROTOCOL_V2.md)
  before making or approving any accuracy claim.

Do not post athlete media, private facility information, raw serial numbers,
trust keys, or unreviewed logs to public issues.
