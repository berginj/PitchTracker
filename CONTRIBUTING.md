# Contributing to PitchTracker

## Branch & merge policy

`main` is protected. **All changes reach `main` through a pull request** that must
pass the required CI checks (`test (3.11)`, `test (3.12)`, `security`) and be up to
date with `main` (linear history; no force-push, no branch deletion).

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
