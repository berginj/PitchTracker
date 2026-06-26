# Documentation Alignment Review

**Last Updated:** 2026-06-22
**Scope:** Active Markdown documentation, with archive treated as historical
**Release Baseline:** v1.5.0-pilot

---

## Review Scope

I reviewed the active Markdown set outside `archive/` and `docs/archive/`
for version, architecture, persona, validation, and release-readiness
consistency. Historical archive documents were left intact unless an active doc
depended on them.

Active Markdown count after this pass: **70 files**.

---

## Alignment Actions Taken

| Area | Action |
| --- | --- |
| Version identity | Reconfirmed `v1.5.0-pilot` as external release identity and `1.5.0` as internal app version |
| Current status | Added `docs/CURRENT_STATUS.md` as the active status reference and updated it with owner guidance |
| Architecture | Replaced stale `InProcessPipelineService` current-state doc with service-oriented architecture overview |
| Personas | Added canonical `docs/USER_PERSONAS.md` for pilot-phase personas |
| Contract personas | Updated `contracts-shared/PERSONAS.md` to point at the canonical persona doc |
| Installer naming | Aligned installer filename docs/scripts around `PitchTracker-Setup-v1.5.0-pilot.exe` |
| Accuracy language | Removed or softened unvalidated accuracy/production claims in active user-facing docs |
| Archive handling | Clarified that archive files may contain stale versions and should not be read as current state |
| GitHub feedback | Added structured issue forms and `docs/GITHUB_FEEDBACK_INTAKE.md` |

---

## Areas Of Concern Requiring Guidance

### 1. Hardware Validation Evidence

Hardware is currently in validation testing. `docs/HARDWARE_PROFILE.md`
previously described the profile as pilot-validated, so active docs now avoid
that claim until testing produces field evidence.

Needed next:

- Record actual camera, mount, lighting, and PC specs from validation.
- Decide whether C920 and/or BRIO are approved pilot hardware.
- Add validation results to GitHub using the Validation Report issue form.

### 2. Pilot Timeline Status

The pilot is pending camera alignment and validation. Several strategy docs were
written on March 26, 2026 and describe an April-June 2026 pilot window; active
status docs now describe the actual blocker instead of treating the pilot as
already launched.

Needed next:

- Define the camera alignment pass/fail threshold.
- Record validation results.
- Update the pilot materials once the pilot actually starts.

### 3. External Release State

No external v1.5.0-pilot release has been created yet. The target is to release
a current version today.

Needed next:

- Run release validation.
- Build `PitchTracker-Setup-v1.5.0-pilot.exe`.
- Create and push tag `v1.5.0-pilot`.
- Publish the GitHub release.

### 4. Test Suite Claims

Several docs claim 389+ tests and 98%+ pass rate. I did not run the full test
suite during this documentation pass. Before publishing externally, rerun the
current suite and update:

- `README.md`
- `docs/TEST_SUITE_DOCUMENTATION.md`
- `docs/CURRENT_STATUS.md`
- any pilot materials that cite pass rate

### 5. Support Contact

GitHub issue forms now provide a consumable feedback path. User docs avoid fake
support email/forum URLs and refer to the pilot support channel provided with
the installation package.

Needed next:

- Confirm that GitHub Issues is acceptable as the primary pilot feedback intake.
- Create/confirm labels used by issue forms: `pilot-feedback`, `validation`,
  `needs-triage`, and any subsystem labels.

### 6. TAG Sports Documents

TAG Sports planning docs remain active because the work is pending feedback from
TAG. Active TAG docs now include planning/concept caveats where validation
examples could be mistaken for completed results.

### 7. Orchestrator Calibration Boundary

`PipelineOrchestrator.run_calibration()` is not implemented. The practical
impact is:

- Routing calibration through the orchestrator gives callers one public pipeline
  API, but adds long-running setup/tooling responsibility to the runtime path.
- Keeping calibration in Setup Doctor/tooling keeps the pilot runtime simpler,
  but the public API must clearly tell callers where calibration belongs.

Recommendation for v1.5.0-pilot: keep calibration in setup/tooling and document
that boundary.

---

## Review Notes

- Archive/session/completed docs intentionally preserve older version strings.
  They should not be bulk-edited unless a specific historical correction is
  required.
- Product docs should use "pilot-ready for controlled facility deployments"
  until reference validation and real pilot outcomes support stronger claims.
- Capability expansion should continue to reference `docs/PRODUCT_STRATEGY.md`
  and `docs/CAPABILITY_CONTRACT_ENFORCEMENT.md`.
