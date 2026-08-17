# Type checking

PitchTracker uses mypy with Python 3.13 as the minimum configured target. CI
runs mypy directly over the repository; there is no stored diagnostic baseline.
Application code, tooling, scripts, and shared contracts must be clean under
the root policy.

Test modules remain part of the same run, but use a fixed relaxation list for
dynamic fakes, monkeypatch method replacement, deliberately malformed payloads,
and optional hardware APIs. Pytest is the behavioral contract for those cases.
`scripts/check_typing_policy.py` mechanically prevents that test-only list from
expanding unnoticed and forbids blanket `ignore_errors` or unscoped ignores.

Run the gate locally with:

```powershell
python -m mypy . --no-incremental --show-error-codes
```

Do not add production exclusions or suppression sections. A narrow inline
ignore must name its mypy error code and should be used only when the external
library contract cannot be expressed locally.
