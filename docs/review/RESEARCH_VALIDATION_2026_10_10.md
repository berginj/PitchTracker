# Measurement research software validation — 2026-10-10

Baseline: `main` at `e8287a9`; results below apply to the local uncommitted
measurement research change. No physical accuracy claim or release approval is
created by these checks.

## Automated checks

- Python 3.14.8 serial full suite: **1,882 passed, 34 skipped**, in 510.52 seconds.
  Focused checks below also cover changes added after full-suite collection.
- Python 3.13.16 and 3.14.8 focused regression runs: **97 passed on each**. Covers desktop research,
  real tooling subprocess evaluation, cancellation and worker reaping, source
  preservation, snapshot bindings, camera evidence, autofocus presentation,
  ROI sides, durable status labels, typing policy and installer/tag checks.
- Python 3.13 full suite before the final additions: **1,874 passed, 34 skipped,
  one failed**. The failure was the old replay-label expectation; the updated
  assertion passes in the focused run above.
- Canonical Python 3.13 mypy: **768 source files, no issues**.
- Flake8, effective typing-policy check, schema mirror, public documentation,
  500-line convention and whitespace checks pass.

## Local environment scope

Separate ignored `venv/research313` and `venv/research314` environments preserve
the existing development environment. Dependencies use repository pins plus
the optional native DirectShow provider. Python 3.13's pinned PyYAML was built
without its optional C extension because the local C++ compiler is unavailable.

The pre-existing ignored `.codex` directory contains another environment.
Local Flake8, mypy and typing-policy runs exclude that third-party tree; repository
policy and CI suppression rules are unchanged. Mypy runs on the canonical 3.13
environment, matching CI. An exploratory 3.14 mypy run reported two pre-existing
redundant casts in `trajectory/camera_model.py`; no suppression was added.

Known dependency deprecation and existing test warnings do not establish
camera timing, optical accuracy or installer qualification. Skips remain skips.

## Remaining operator evidence

Actual camera/control/timing/USB and recovery qualification, independent
references, the initial 100-attempt three-session shadow baseline, disjoint
confirmation and review, signing, frozen-build inspection and clean-Windows
install/update/uninstall qualification remain outstanding. No camera was opened,
recording collected, athlete artifact uploaded, approval activated, GitHub issue
closed, or release published as part of this implementation.

Follow [Desktop Measurement Research](../MEASUREMENT_RESEARCH.md) and
[the acceptance ledger](RESEARCH_ACCEPTANCE_LEDGER.md).
