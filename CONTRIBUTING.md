# Contributing to PitchTracker

## Testing contributions are especially valuable

The current priority is real Windows hardware and field evidence, not additional
accuracy claims based on simulation. See
[`docs/TESTING_NEEDED.md`](docs/TESTING_NEEDED.md) and the canonical
[`docs/ROADMAP.md`](docs/ROADMAP.md).

Useful contributions include clean Windows installer smoke tests,
global-shutter camera discovery and control-readback reports, setup recovery
tests, anonymized capture-quality metrics with explicit denominators, and
predeclared physical validation using an independent calibrated reference.

Submit results through the Validation Report or Pilot Feedback issue form. Do
not attach athlete media, private facility data, secrets, or unreviewed logs.
Report suspected vulnerabilities privately as described in
[`SECURITY.md`](SECURITY.md), not through a public issue.

## Branch & merge policy

`main` is protected. **All changes reach `main` through a pull request** that must
pass the required CI checks (`test (3.13)`, `test (3.14)`, `security`) and be up to
date with `main`. The protected branch requires linear history and disallows
force-pushing or deleting `main`; merged feature branches may be deleted.

Repository admins are intentionally **not** forced through PRs (`enforce_admins`
is off) so the owner can land emergency fixes directly — but the default, expected
path for all feature and refactor work is a PR. Do not merge large changes
directly to `main`.

## Before you push

Run the same gates CI runs — all of these block merge:

```powershell
flake8 .                              # HARD GATE: any error fails CI
python -m pytest                      # full suite
python scripts/check_file_length.py   # no file over 500 lines
python scripts/sync_schema.py --check # schema/ mirrors contracts-shared/
```

`mypy .` and the `safety` dependency scan run **advisory** (`continue-on-error`)
and do not block, but please keep them clean where practical.

> Note: full-style `flake8` is a **hard** gate (`flake8 . --count --statistics`
> with no `continue-on-error`). It is *not* limited to `E9,F63,F7,F82`.

## Conventions (see `.github/copilot-instructions.md` for the full list)

- **Files** max 500 lines (target 200–300); **functions** max 50 lines, max 5 params.
- **Errors:** raise custom exceptions from `exceptions.py`; never bare `Exception`
  or `RuntimeError`. Chain with `raise CustomError(...) from exc`.
- **Logging:** use `from log_config.logger import get_logger`.
- **UI:** PySide6 types stay in `ui/`; style only via `ui/themes/` tokens.
- **Versioning:** bump `installer.iss` and `contracts/versioning.py` together.

## Architecture decisions

Significant direction changes (e.g., the core-pipeline rewrite) are recorded as
Architecture Decision Records under `docs/decisions/`. Add or update an ADR in the
same change that implements the decision.

## Evidence discipline

- Automated tests prove software behavior, not physical accuracy.
- Preserve failures, rejected attempts, unmatched frames, and denominators.
- Never replace missing information with zero or an assumed pass.
- Keep raw values when proposing or applying a correction.
- Update requirements, traceability, and roadmap status in the same change when
  behavior or acceptance criteria change.

Last reviewed: **2026-07-22**.
