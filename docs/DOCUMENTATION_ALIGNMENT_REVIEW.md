# Documentation Alignment Review

**Reviewed:** 2026-07-21
**Scope:** active Markdown files outside `archive/` and `docs/archive/`

## Canonical hierarchy

1. `README.md` — public repository landing page.
2. `docs/CURRENT_STATUS.md` — current delivery and evidence state.
3. `docs/ROADMAP.md` — only canonical open-work list.
4. Requirements, ADRs, evidence contracts, and PT/AR traceability.
5. User, operator, developer, investigation, and strategy guides.
6. Archive material — historical only.

## Corrections made in this review

- Replaced obsolete 389/841/1051-test claims with the recorded 1,263-pass run
  in canonical status/test pages.
- Corrected the canonical setup workflow from six/nine steps to ten.
- Replaced v1.5 pilot release guidance with v2.0 identity and the actual release
  gap: the public release has no attached installer and `main` is ahead.
- Added a single evidence-based roadmap and a privacy-safe testing request.
- Updated issue forms to request commit/snapshot identity and denominators.
- Marked dated strategy, pilot, review, and prototype pages as context rather
  than current delivery status.
- Preserved historical changelog entries and archived reports unchanged.

## Remaining intentional historical references

Some active technical guides retain old version names because they describe the
version in which a feature was introduced. A dated/historical notice must appear
when the rest of the document could otherwise be mistaken for current status.
The changelog is inherently historical and is not bulk-rewritten.

## Maintenance rule

New standalone TODO lists are not permitted. Add executable work to
`ROADMAP.md` and a GitHub issue, then link from supporting design documents.
Accuracy, performance, hardware, and readiness statements must name their test
environment and evidence date or be labeled as targets/unvalidated.
