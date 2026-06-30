## Summary

<!-- What does this change do and why? Link any issue or decision record. -->

## Type of change

- [ ] Bug fix
- [ ] New feature
- [ ] Refactor / cleanup
- [ ] Docs only
- [ ] CI / tooling

## Checklist (CI gates are enforced on `main`)

- [ ] `flake8 .` is clean (**hard CI gate** — any error blocks merge)
- [ ] `python -m pytest` passes locally
- [ ] `python scripts/check_file_length.py` passes (no file over 500 lines)
- [ ] `python scripts/sync_schema.py --check` passes (schema mirror in sync)
- [ ] New errors raise custom exceptions from `exceptions.py` (no bare `Exception`/`RuntimeError`)
- [ ] No unrelated files or generated artifacts included

## Validation

<!-- How was this verified? Note any hardware-only validation that could not be run in CI. -->

## Risk / rollback

<!-- What could break, and how to revert if it does? -->
