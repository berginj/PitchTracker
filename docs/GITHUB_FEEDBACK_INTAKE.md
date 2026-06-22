# GitHub Feedback Intake

**Last Updated:** 2026-06-22
**Applies To:** v1.5.0-pilot

---

## Purpose

Pilot feedback should be captured in GitHub issues using structured issue
forms. This gives us a support channel that is easy to search, label, export,
and convert into work items.

Use GitHub for:

- pilot feedback
- setup friction reports
- camera alignment issues
- validation results
- documentation gaps
- repeatable bugs

Do not upload private athlete video, identifiable athlete data, facility
private information, or raw recordings unless explicitly authorized.

---

## Available Forms

| Form | Use For | Default Labels |
| --- | --- | --- |
| Pilot Feedback | Session/setup feedback, friction, bugs, improvement requests | `pilot-feedback`, `needs-triage` |
| Validation Report | Camera alignment, velocity/location accuracy, detection-rate results | `validation`, `needs-triage` |

The issue templates live in `.github/ISSUE_TEMPLATE/`.

---

## Consuming Feedback

Examples with GitHub CLI:

```powershell
gh issue list --label pilot-feedback --state open
gh issue list --label validation --state all --json number,title,labels,createdAt,body
gh issue list --label needs-triage --state open --json number,title,url
```

Suggested triage labels:

- `needs-triage`
- `pilot-feedback`
- `validation`
- `camera-alignment`
- `setup-doctor`
- `calibration`
- `recording`
- `review-mode`
- `documentation`
- `pilot-blocker`

Create these labels in GitHub before pilot intake begins so issue-form defaults
and triage queries work consistently.

Suggested weekly triage:

1. Review new `needs-triage` issues.
2. Add subsystem labels.
3. Mark pilot blockers explicitly.
4. Convert validated bugs into scoped engineering work.
5. Summarize repeated friction in pilot status notes.

---

## Release Use

Before publishing a new pilot build, review:

```powershell
gh issue list --label pilot-blocker --state open
gh issue list --label validation --state open
```

Do not claim validation is complete until validation issues include enough
reference-equipment results to support the published operating envelope.
