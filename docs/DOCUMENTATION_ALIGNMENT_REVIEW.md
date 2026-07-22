# Documentation Alignment Review

**Reviewed:** 2026-07-22
**Scope:** active Markdown files outside `archive/` and `docs/archive/`, plus
GitHub metadata, releases, issue forms, support/security surfaces, and repository
publishing guidance

## Canonical hierarchy

1. `README.md` — public repository landing page.
2. `docs/CURRENT_STATUS.md` — current delivery and evidence state.
3. `docs/ROADMAP.md` — only canonical open-work list.
4. Requirements, ADRs, evidence contracts, and PT/AR traceability.
5. User, operator, developer, investigation, and strategy guides.
6. Archive material — historical only.

## Corrections made in this review

- Replaced obsolete 389/841/1051-test claims with the recorded 1,267-pass run
  in canonical status/test pages.
- Corrected the canonical setup workflow from six/nine steps to ten.
- Replaced v1.5 pilot release guidance with v2.0 identity and the actual release
  gap: the public release has no attached installer and `main` is ahead.
- Added a single evidence-based roadmap and a privacy-safe testing request.
- Updated issue forms to request commit/snapshot identity and denominators.
- Marked dated strategy, pilot, review, and prototype pages as context rather
  than current delivery status.
- Preserved historical changelog entries and archived reports unchanged.
- Replaced stale installer, launcher, FAQ, storage, update, privacy, and hardware
  instructions with behavior verified against current code and GitHub assets.
- Corrected public support URLs and removed advice to bypass Windows security
  controls for an unverified installer.
- Added private vulnerability-reporting and support policies.
- Replaced the hard-coded release helper with explicit tag, notes, artifact, and
  checksum inputs plus refusal to overwrite an existing release.

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
