# Baseline configuration and calibration

Baseline is the camera separation used by the stereo geometry. Display units are
inches or feet; calibration translation matrices store millimeters.

For guided setup, a manual baseline is an initial estimate. When full calibration
is accepted, setup derives the effective baseline from the norm of its translation
vector and saves it with the working rig configuration. The calibrated matrices
remain authoritative for triangulation. Bundled defaults and previous completed
rigs are preserved.

A changed reported baseline is a reason to inspect the setup: board square size,
image quality, camera identities, lens settings, image transforms, mount movement,
and calibration residuals. Calibration output alone does not establish that its
baseline is more accurate than an independent physical measurement.

Do not adjust baseline to make pitch outputs match expectations. Correct the
underlying setup inputs, rerun calibration, and check surveyed holdout targets.
Moving cameras or changing optical/image geometry invalidates downstream checks.

Setup displays saved settings and the required checks explicitly. A passing
calibration/field check is engineering evidence, not a published precision bound.
No fixed baseline accuracy is claimed without independent physical validation.

See [Guided Setup](GUIDED_SETUP.md) and
[Desktop Measurement Research](MEASUREMENT_RESEARCH.md).
