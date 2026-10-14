# PitchTracker Roadmap

**Last reviewed:** 2026-10-14
**Source of truth for open work:** this document and linked GitHub issues

This roadmap separates completed software work from physical evidence that
cannot be produced in CI. A checked box means the implementation and automated
contract are complete; it does not imply physical measurement accuracy.

## Current priority: desktop measurement research

Use [Desktop Measurement Research](MEASUREMENT_RESEARCH.md) to inspect captured
evidence, edit shadow cases, and compare independent speed/location references.
The eight October 5 software follow-ups now have focused implementations; see
[the acceptance ledger](review/RESEARCH_ACCEPTANCE_LEDGER.md). Establish the
operator-run rig qualification and initial 100-attempt, three-session shadow
baseline before selecting the next algorithm change. Confirmation, independent
review, signing, and clean-machine qualification retain their existing gates.

## UX: unified workspace first

The [UX workspace plan](UX_WORKSPACE_PLAN.md) defines the approved direction,
assignable work packages, acceptance criteria and implementation prompts.
This checklist is the delivery-status source. UX-01 supplies a rendered synthetic
baseline, target layouts and interface mapping. UX-02 delivers the persistent
workspace shell. Detailed page redesign and real Windows display/hardware
verification remain open. This work does not replace
physical qualification or release gates.

- [x] UX-01: Establish the shared experience specification and synthetic visual baseline
  ([specification and evidence](review/ux/UX_01_SPEC.md)).
- [x] UX-02: Introduce persistent Live, Sessions, Players and Setup navigation
  ([implementation and evidence](review/ux/UX_02_IMPLEMENTATION.md)).
- [x] UX-03: Clarify recording states and session controls
  ([implementation and evidence](review/ux/UX_03_IMPLEMENTATION.md)).
- [ ] UX-04: Prioritize latest-pitch feedback in live coaching.
- [ ] UX-05: Connect session history, pitch selection and review.
- [ ] UX-06: Align setup and player workflows within the workspace.
- [ ] UX-07: Normalize analytics, dialogs, settings, help and visual presentation.
- [ ] UX-08: Validate complete operator journeys and record manual evidence.

Execute in ID order. Each package must pass its focused checks before the next
starts; carry pending hardware evidence explicitly without claiming it passed.
Completed audit fixes below remain completed unless a new regression is reproduced.

## Completed in software

- [x] PT-001–PT-015 evidence-first field-robustness implementation.
- [x] Interruptible, deadline-bounded setup capture.
- [x] Candidate-level decision lineage, unmatched outcomes, global stereo
  assignment, durable journal, and offline replay reconciliation.
- [x] Physical-validation v2 protocol, datasets, reports, signatures, and exact
  fingerprint-bound approvals.
- [x] Canonical content-addressed setup-system snapshot.
- [x] Validated-pair-first camera recommendation with capability fallback.
- [x] Compact operator health/actions with detailed diagnostics on demand.
- [x] Optional local BaseballCV detector, twelve-cell stereo comparison,
  separate monocular study, and rig-bound live qualification controls
  ([workflow](BASEBALLCV_COMPARISON.md)).
- [x] Clean Windows application and installer build from commit `40158c1`.
- [x] Automated regression coverage for queue saturation, event metadata,
  setup observations, launcher closure, and camera-step re-entry.
- [x] Rig-profile validation/persistence extraction ([#14](https://github.com/berginj/PitchTracker/issues/14)).
- [x] Setup-provider workflow extraction ([#15](https://github.com/berginj/PitchTracker/issues/15)).

Implementation evidence is mapped in [PT_001_015_TRACEABILITY.md](PT_001_015_TRACEABILITY.md).
The checked regression count is historical evidence for its named commit, not
a statement that the current dirty worktree or every guarded workflow is green.

## Audit remediation gates

The dependency-ordered source of audit findings and closure criteria is
[review/REMEDIATION_PLAN.md](review/REMEDIATION_PLAN.md). Before field hardening:

- [x] Restore simulator coaching-window construction and UI smoke coverage.
- [x] Correct the pytest-qt import guard and split Qt-offscreen from codec tests.
- [x] Replace submitted-frame benchmark accounting with terminal conservation.
- [x] Establish responsive minimum-size and accessibility evidence for setup,
  launcher, and review.
- [x] Complete required message metadata across durable/asynchronous flows.

The historical remediation plan is retained under `docs/review/` for audit
traceability. Its completed findings are not current open work. Earlier full
parallel runs exposed a Windows native-thread teardown access violation. The
September 8 local rerun exited cleanly; target-rig failure injection and
clean-machine lifecycle qualification remain necessary.

## Now: correctness gates and controlled pilot

The September review identified timestamp provenance (#34), distorted-pixel
geometry (#35), drag-prior bias (#36), sampled strike misses (#37), misleading
uncertainty/fit eligibility (#38), speed-reference conflation (#39), and omitted
transverse physics (#40). Committed remediation is described in
[the implementation plan](../DEVELOPMENT_PLAN.md). No issue is closed merely
by this document. Model limitations remain explicit; no spin or movement
accuracy claim is added.

Complete software/build gates, then execute the
[controlled pilot checklist](CONTROLLED_PILOT_CHECKLIST.md). Preserve production
queue capacity and time-based pre-roll pending telemetry. The configurable
stereo process limit is 15 seconds, not a response-time promise.

The [October 12 acceptance reconciliation](review/PLATFORM_AND_ISSUE_CLOSEOUT_2026_10_12.md)
maps every criterion in #34–#40 to evidence or a specific remaining gate.
The deterministic strike-geometry and speed-provenance issues #37/#39 are
closed as completed. Remaining criteria in #34–#36, #38 and #40 retain their original
physical, prior-model, uncertainty or operating-envelope requirements.

## Optional compute-platform qualification

Native ARM64 numerical kernel and standalone-worker checks passed on a
Snapdragon Windows ARM64 host, including cross-architecture clients and bounded
process-tree cancellation/recovery. The full native GUI/video stack and MSVC
production wheels still need qualification.

CUDA qualification is blocked on this host's Adreno GPU. A CUDA-capable NVIDIA
machine must run parity, end-to-end workload throughput and failure/recovery
checks before Auto admission. Thermal/low-memory and representative recorded
workload testing remain platform gates; synthetic timings do not establish them.

## Physical validation and tester feedback

### [R-001 — Global-shutter camera qualification](https://github.com/berginj/PitchTracker/issues/9)

Collect repeatable results across supported Windows systems and camera pairs.

Acceptance evidence:

- Stable hardware IDs and correct recommended left/right preselection.
- Requested and negotiated modes recorded for both cameras.
- Verified exposure/gain/focus/white-balance readback where applicable.
- Frame counts, drops, unmatched rate, achieved FPS, cadence jitter, and pair
  skew p50/p95/p99 captured with explicit denominators.
- Driver, firmware, and USB-controller information recorded or explicitly marked
  unavailable.

### [R-002 — Setup repeatability](https://github.com/berginj/PitchTracker/issues/9)

Run the canonical five-stage workflow after intentional poor configurations such
as camera swap, baseline shift, focus loss, exposure mismatch, USB contention,
and partial overlap.

Acceptance evidence:

- Setup blocks or degrades the correct condition.
- Operator guidance identifies a real corrective action.
- Re-running setup after correction produces a new snapshot and fingerprint.
- No correction silently mutates calibration or makes an accuracy claim.

### [R-003 — Physical ground-truth confirmation](https://github.com/berginj/PitchTracker/issues/10)

Execute [Physical Validation Protocol v2](PHYSICAL_VALIDATION_PROTOCOL_V2.md)
using an independent calibrated reference channel.

Acceptance evidence:

- Protocol, strata, exclusions, sample counts, and thresholds locked before the
  confirmation data is examined.
- Rejected and unmatched attempts retained in denominators.
- Speed bias/MAE/tail error and plate-location MAE/tail error reported with
  reference uncertainty.
- A separate confirmation dataset passes every required threshold.
- Collector and independent reviewer sign an approval bound to the exact rig,
  software, snapshot, artifacts, environment, and correction policy.

### [R-004 — Installer smoke testing](https://github.com/berginj/PitchTracker/issues/11)

Test the clean installer on Windows machines that do not have the development
checkout or Python environment.

Acceptance evidence:

- Install, first launch, setup entry, simulator run, log creation, update check,
  uninstall, and reinstall all complete.
- No repository-local calibration, ROI, recording, or cache data is bundled.
- Windows version, architecture, security warnings, and failure logs recorded.

### [R-005 — UVC capability inventory](https://github.com/berginj/PitchTracker/issues/16)

**Software status:** complete. Optional native DirectShow queries and
conservative OpenCV fallback now preserve explicit status, provenance,
requested/negotiated modes, advertised modes, and device metadata. Physical
camera qualification remains part of R-001.

Acceptance evidence:

- Capability results distinguish supported, unsupported, permission denied, and
  unavailable.
- Tests cover device and query failures.
- Setup snapshots persist observed results without inventing defaults.

See [UVC Capability Evidence](UVC_CAPABILITY_DISCOVERY.md) for status semantics
and the pre-field hardware matrix.

## Next: field hardening after evidence arrives

- Publish a known-good hardware matrix from qualifying reports.
- Define the supported operating envelope for lighting, baseline, distance,
  speed, ball type, and reference uncertainty.
- Turn repeated setup failures into bounded, audited correction proposals.
- Add anonymized replay fixtures for failures that can legally be shared.
- Publish a refreshed installer only after clean-machine smoke testing.
- Run limited facility pilots with measurable setup time, rejection rate,
  operator intervention, and repeatability targets.

## Engineering debt with active owners

The [October 5 audit](review/REQUEST_AND_WORK_AUDIT_2026_10_05.md) records the
historical eight follow-ups. Their implementations and regression coverage are
now mapped in the research acceptance ledger. Physical/manual evidence and
the remaining reconciled acceptance criteria remain work.

- Keep the direct repository-wide mypy gate clean and keep test-only typing
  relaxations fixed through the suppression policy check.
- Keep [OVERSIZED_MODULE_TRIAGE.md](OVERSIZED_MODULE_TRIAGE.md) as historical
  extraction context; the current file-length gate has zero grandfathered files.

## Branch review follow-ups

The operator approved retirement of MainWindow, the older setup registries,
InProcessPipelineService and direct pipeline CLI. Their source/tests are retained
under archive/retired/2026-10-13; the private duplicate enrichment path is removed.
Use [Rig Validation Walkthrough](RIG_VALIDATION_WALKTHROUGH.md) to qualify the rig
and collect independent quality-reference evidence.

The [October 13 branch and archive review](review/BRANCH_AND_ARCHIVE_REVIEW_2026_10_13.md)
reconciles every local branch, records optional detector admission fixes, and
proposes archival work for discussion. Archive candidates are not active removal tasks.

The [October 6 final branch review](review/BRANCH_CONSOLIDATION_2026_10_06.md)
records the meaningful PR #41 merge, already-incorporated work, rejected Python
3.9 patches, and archive references for retired branch tips.

The [branch consolidation review](review/BRANCH_CONSOLIDATION_2026_10_02.md)
distinguishes work already incorporated through squash merges from the remaining
camera and launcher lifecycle changes. Implementation and validation evidence
is recorded in [the October consolidation record](review/CONSOLIDATION_VALIDATION_2026_10_02.md).

- CR-001 recording lifecycle command admission: already implemented on `main`;
  control commands bypass bounded frame capacity while preserving FIFO order.
- CR-004 review-config containment: already implemented on `main`; resolved
  paths must stay within explicitly permitted roots.
- CR-002 launcher validation shutdown: implemented in the consolidation branch;
  cancellation stops/reaps the tooling child and defers closure until validation
  and updater threads finish. Closing suppresses scheduled and late update work.
- CR-003 discovery cancellation: implemented in the consolidation branch;
  cancelled probes do not write caches or deliver stale results. Backend
  switches and setup closure retain and clean up owned discovery/preview work.
  Legacy calibration remains owned until its existing bounded tooling operation
  finishes; close can wait up to that operation's 300-second timeout.

Real-rig disconnect, backend-switch, and repeated setup/launcher-close checks
remain operator-run gates. Automated lifecycle coverage does not replace
clean-machine installer qualification or establish physical accuracy.

The [October pending-work review](review/PENDING_WORK_2026_10_03.md) is a
historical baseline. Its eight software findings now have implementations:
frozen GUI dependencies, per-user writable storage/data preservation, retained
recording and capture ownership, accepted-pitch terminal delivery, manual
updater shutdown, exact installer/config provenance, and CSV/strike uncertainty
semantics. The [remediation validation record](review/REMEDIATION_VALIDATION_2026_10_03.md)
tracks tests and artifact hashes. Physical qualification, independent accuracy
confirmation, signing, and clean-machine lifecycle tests remain open.

## Later or conditional

- Promote ray trajectory modes only after separate confirmation evidence.
- Expand ML defaults only after representative labeled data and regression gates.
- Qualify optional BaseballCV profiles with supplied weights, the dedicated
  six-session study and sustained recorded capture; retain the separate physical
  confirmation gates ([workflow](BASEBALLCV_COMPARISON.md)).
- Activate TAG/cloud integrations only after partnership scope, privacy review,
  and dedicated implementation issues.
- Add coaching capabilities beyond the UX workspace redesign only when pilot
  usage demonstrates a decision need.

## Not current commitments

Historical month-by-month estimates, old version task lists, and partnership
concept schedules remain useful context but are not the active backlog. The
active queue includes physical gates #9–#11, remaining acceptance criteria in
#34–#36/#38/#40, optional platform qualification and baseline-driven research
improvements, plus UX-01 through UX-08 above. Preserve regression coverage
for the eight implemented October software follow-ups.
