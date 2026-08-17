# Type checking

PitchTracker uses mypy with Python 3.13 as the configured target. The full
tree is not clean yet, so CI runs `scripts/check_mypy_baseline.py` as a
ratchet: existing diagnostics are recorded in `mypy-baseline.txt`, while any
new diagnostic fails CI. The baseline key omits line numbers so harmless line
movement does not create churn.

Run the gate locally with:

```powershell
python scripts/check_mypy_baseline.py
```

When a change genuinely resolves diagnostics, refresh the baseline and review
the resulting diff:

```powershell
python scripts/check_mypy_baseline.py --update
```

Do not use `--update` to hide new errors. Prefer fixing changed modules and
keep focused checks strict even while the whole-tree backlog is retired.
