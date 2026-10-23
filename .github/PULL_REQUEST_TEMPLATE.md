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
- [ ] `python scripts/check_file_length.py` passes (active Python files stay within 500 lines)
- [ ] `python scripts/sync_schema.py --check` passes (schema mirror in sync)
- [ ] `python scripts/check_public_docs.py` passes for maintained Markdown and entry points
- [ ] Typing policy and `python -m mypy . --no-incremental --show-error-codes` pass
- [ ] Expected failures use typed errors/codes; isolation catches log, clean up and preserve valid state
- [ ] No unrelated files or generated artifacts included
- [ ] Public behavior/status claims and linked documentation remain accurate
- [ ] No secrets, private media, raw hardware identities, or unreviewed logs included

## Validation

<!-- How was this verified? Note any hardware-only validation that could not be run in CI. -->

## Risk / rollback

<!-- What could break, and how to revert if it does? -->
