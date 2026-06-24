# Version Alignment and Pilot Build Lock

**Last Updated:** 2026-06-23
**Status:** Aligned in repo; pilot release published; refreshed installer rebuilt
**Owner:** Product/Engineering

---

## Canonical Version Decision

**External release identity:** `v1.5.0-pilot`

**Internal app version:** `1.5.0`

PitchTracker uses the `v1.5.0-pilot` label for pilot distribution,
documentation, release tags, and installer filenames. The runtime app version
remains `1.5.0` because code, schemas, and update comparisons expect a numeric
semantic version.

---

## Source Of Truth

| Purpose | Source | Current Value |
| --- | --- | --- |
| Runtime app version | `contracts/versioning.py` | `APP_VERSION = "1.5.0"` |
| Durable schema version | `contracts/versioning.py` | `SCHEMA_VERSION = "1.2.0"` |
| Installer app version | `installer.iss` | `AppVersion "1.5.0"` |
| Installer filename | `installer.iss` | `PitchTracker-Setup-v1.5.0-pilot.exe` |
| Git release/tag | GitHub release process | `v1.5.0-pilot` |
| User/pilot docs | Active Markdown docs | `v1.5.0-pilot` |

---

## Pilot Build Characteristics

### Included

- Stereo camera capture with real-time 3D tracking
- Service-oriented `PipelineOrchestrator` runtime
- Setup Doctor and rig profile validation paths
- Coaching mode and review mode
- Session/pitch recording with manifests and metadata
- Pattern detection and pitcher profile workflows
- ChArUco/stereo calibration tooling
- Local-first data model with no required cloud upload

### Deferred Or Not Yet Validated

- Published reference-equipment velocity validation
- Published location accuracy validation
- Fully self-service casual consumer setup
- Cloud analytics and mobile workflows
- TAG Sports production integration
- ML detector as default production path

---

## Version Freeze Policy

The pilot build should remain stable for structured facility pilots.

Allowed during the pilot lock:

- bug fixes
- documentation improvements
- performance optimizations that do not alter user workflows
- error-message and supportability improvements
- critical pilot-blocker patches as `v1.5.x-pilot`

Not allowed without capability-contract approval:

- new user-facing capabilities
- workflow-changing UI redesigns
- durable schema changes
- export format changes
- architecture shortcuts that bypass service boundaries

---

## Verification Checklist

Repo-local checks:

- [x] `contracts/versioning.py` defines `APP_VERSION = "1.5.0"`
- [x] `updater.py` uses `CURRENT_VERSION = "1.5.0"`
- [x] `installer.iss` uses `AppVersion "1.5.0"`
- [x] installer output filename includes `v1.5.0-pilot`
- [x] `README.md` references `v1.5.0-pilot`
- [x] `CHANGELOG.md` has a `1.5.0-pilot` entry
- [x] active docs have a current status reference in `docs/CURRENT_STATUS.md`
- [x] stale architecture current-state doc has been replaced

External/release checks:

- [x] Git tag `v1.5.0-pilot` has been created and pushed
- [x] GitHub release `v1.5.0-pilot` has been published
- [x] installer has been built as `PitchTracker-Setup-v1.5.0-pilot.exe`
- [ ] installer has been smoke-tested on a clean Windows machine
- [x] current full test run has been recorded for release notes
- [x] refreshed installer contents exclude runtime-local config/cache state

Refreshed installer built 2026-06-23:

- Path: `installer_output/PitchTracker-Setup-v1.5.0-pilot.exe`
- Size: `92,200,172` bytes
- SHA256:
  `F211FC39FA4468281DA7B5BAED67581049ABADDC266EED1A4DA59039A1C999A2`

---

## Release Communication

Use this language for pilot partners:

> You are running PitchTracker v1.5.0-pilot, the canonical pilot build for
> controlled facility deployments. Accuracy validation is in progress, and
> current pilots are part of establishing the published operating envelope.

Avoid stronger public claims such as "validated to ±1 mph" or "production-ready
for all users" until reference validation and pilot outcomes support them.

---

## Update Process

1. Update `contracts/versioning.py`.
2. Update `CHANGELOG.md`.
3. Update `installer.iss` if installer identity changes.
4. Update `README.md`, `docs/CURRENT_STATUS.md`, and this file.
5. Run focused tests for affected release/version behavior.
6. Build and smoke-test installer.
7. Create and push the matching Git tag.
8. Publish GitHub release with installer and release notes.

---

## Open Questions

1. Should patch releases use `v1.5.1-pilot` while keeping app version
   `1.5.1`, or should the app UI display the full pilot suffix?
2. Should a version-sync script enforce docs/build metadata before release?
3. Who owns final sign-off that the published installer and GitHub release are
   the same artifact tested by the pilot team?
