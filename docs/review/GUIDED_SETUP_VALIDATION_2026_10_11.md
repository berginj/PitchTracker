# Guided setup software validation — 2026-10-11

Initial validation baseline: `main` at `8942bb2`. The October 11 results below
cover the guided setup and configuration change described in
[Guided Setup](../GUIDED_SETUP.md). The October 12 section records its integration
with the newer remote baseline.

## Automated checks

| Runtime | Full suite | Execution |
|---|---|---|
| Python 3.13.14 | 1,910 passed, 34 skipped | Two workers, loadscope; 226.34 seconds |
| Python 3.14.7 | 1,910 passed, 34 skipped | Serial; 397.68 seconds |

Final focused regression runs passed 44 tests on each runtime. They cover
the guided service and desktop workflow, calibration output isolation, build
identity, approval bindings, and launcher behavior. These runs also cover the
final control-locking and launcher/settings adjustments after full-suite collection.

Canonical Python 3.13 mypy passed for 788 source files. Flake8, schema mirror,
public documentation checks, typing policy, the 500-line convention, and
whitespace checks with CRLF support passed. Local static runs exclude the
pre-existing untracked `docs/reviews/` scratch assets; repository typing and
lint policy remain unchanged.

The workflow regressions exercise image pairing and quality checks, calibrated
target triangulation, independent holdout failures, per-camera regions, valid
immediate saves, failed-write recovery, dependent-check invalidation, stale
capture rejection, revision preservation, and recording admission. A simulator
integration starts and stops recording and verifies a durable session manifest;
that test substitutes the video encoder.

## Environment and desktop scope

Separate ignored `venv/setup313` and `venv/setup314` environments use
`requirements-dev.txt`, including the optional native DirectShow dependency.
The existing development environment is preserved. Python 3.13's pinned
PyYAML 6.0.1 was built without its optional C extension.

All five desktop stages were rendered at 1024×768 with synthetic images and
survey data. Screenshots are stored locally under
`validation_output/guided-setup-ui-2026-10-11/`. Tests verify that construction
and stage re-entry do not initiate camera discovery or capture.

Existing dependency deprecation and test warnings remain visible. Skipped
tests remain outside the passing count.

## Pre-push integration — 2026-10-12

The setup change was rebased onto `7167f7c`, preserving its trajectory acceleration
and supervised batch evaluation. Settings retain the compute selector alongside
rig controls owned by Setup. Applying a saved rig preserves the session compute
selection while retaining its calibrated camera configuration.

Focused integration tests passed **72 tests on Python 3.13.14 and 72 on Python
3.14.7**, covering guided setup, rig validation/approvals, launcher, compute
selection, optimized runtime, and fit batches. The full-suite counts above
precede this integration.

The development requirements now include the `pybind11>=3.0` build dependency
declared by the incoming native project so its development script can be type
checked in CI. Canonical Python 3.13 mypy passed for 820 source files using the
same scratch-directory exclusion described above. Lint, typing policy, schema,
documentation, file-length checks, and packaging-spec syntax passed.

## Remaining manual validation

The intended physical rig still needs camera identity/mode/control readback,
optical timing, surveyed-target selection, region overlays, cancellation,
reconnect, and application-restart validation. Installed Windows qualification
must check writable paths and bundled build identity. Actual frozen binaries
and a signed installer were not qualified by this change.

Physical accuracy approval still requires the existing independent reference,
confirmation, and review gates. Follow the manual checklist in
[Guided Setup](../GUIDED_SETUP.md).
