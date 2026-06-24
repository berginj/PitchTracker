# PitchTracker User Personas

**Last Updated:** 2026-06-22
**Applies To:** v1.5.0-pilot
**Status:** Baseline personas pending pilot confirmation

---

## Purpose

These personas define the real users PitchTracker should optimize for during
the pilot phase. They are intentionally practical: they describe jobs,
constraints, success signals, and documentation implications.

The current market assumption is that PitchTracker is a facility/academy tool
for controlled environments, not a casual self-service consumer product.

---

## Primary Personas

### 1. Setup Technician / Installer

**Job to be done:** Install, calibrate, validate, and hand off a dual-camera
rig that can be trusted for coaching sessions.

**Typical context:**

- first-time facility setup
- camera replacement or rig movement
- calibration troubleshooting
- pre-session readiness checks

**Primary tasks:**

- identify left and right cameras
- confirm focus, exposure, overlap, and mounting stability
- run ChArUco/stereo calibration
- configure lane and plate ROIs
- run Setup Doctor and resolve CRITICAL findings
- export enough evidence for support if setup fails

**Success looks like:**

- setup status is clear: PASS, WARN, or CRITICAL
- the operator knows whether software correction is enough or physical
  adjustment is required
- the rig profile can be reused without repeating full setup every session
- support can diagnose failures from saved reports and logs

**Documentation needs:**

- hardware checklist
- calibration walkthrough
- Setup Doctor failure guide
- support bundle/export instructions

### 2. Coach / Session Operator

**Job to be done:** Start a session quickly, capture reliable pitch metrics,
and make immediate coaching decisions without owning technical pipeline details.

**Typical context:**

- bullpen session
- pitching lesson
- team practice
- controlled facility evaluation

**Primary tasks:**

- choose pitcher/session context
- start capture and recording
- monitor velocity, location, strike/ball result, and obvious warnings
- pause/resume or end the session cleanly
- review or export session results

**Success looks like:**

- daily session start takes seconds once setup is complete
- live metrics are legible and credible
- warnings are actionable without reading logs
- review mode answers what happened and what to do next

**Documentation needs:**

- quick-start session workflow
- error message glossary
- review/export guide
- "what to trust before validation is complete" guidance

### 3. Facility Owner / Program Director

**Job to be done:** Decide whether PitchTracker is worth deploying, supporting,
and eventually buying for repeated use across athletes and coaches.

**Typical context:**

- pilot recruitment
- buying decision
- staff training
- evaluation against radar/Rapsodo/TrackMan alternatives

**Primary tasks:**

- assess hardware cost and setup burden
- confirm staff can operate the system
- evaluate accuracy and reliability evidence
- compare business value against alternatives
- decide whether to continue after the pilot

**Success looks like:**

- expectations are clear before pilot start
- the operating envelope is documented
- accuracy and detection-rate evidence is credible
- staff adoption is measurable
- support burden is acceptable

**Documentation needs:**

- pilot agreement and success metrics
- known-good hardware profile
- validation report
- operating envelope
- pricing/support expectations

### 4. Pitcher / Athlete Review Recipient

**Job to be done:** Understand what changed, what to work on next, and how
current performance compares with previous sessions or baselines.

**Typical context:**

- post-session review with coach
- athlete progress tracking
- shareable summary after a lesson

**Primary tasks:**

- review velocity, location, movement, and pitch-type patterns
- compare current results with previous sessions
- understand coach-selected takeaways
- receive export or report outside the capture workstation

**Success looks like:**

- summaries are credible and easy to understand
- metrics are not overclaimed beyond validation
- comparisons answer "what changed?"
- outputs support coaching, not just data display

**Documentation needs:**

- lightweight report interpretation guide
- privacy expectations
- explanation of metric limitations

### 5. Support / Maintenance Operator

**Job to be done:** Diagnose field failures without physical access to the rig
and guide the facility back to a usable state.

**Typical context:**

- pilot support call
- calibration failure
- camera disconnect/reconnection issue
- recording or disk failure
- confusing metric output

**Primary tasks:**

- inspect logs, setup reports, manifests, and config snapshots
- determine whether issue is hardware, calibration, detection, recording, or UI
- reproduce with simulator tests when possible
- give non-destructive recovery steps

**Success looks like:**

- logs include camera/session/pitch identifiers
- support bundles omit private video unless explicitly selected
- failures map to actionable user steps
- recurring issues become test cases or documentation fixes

**Documentation needs:**

- support checklist
- log/artifact map
- privacy and redaction rules
- escalation rules for hardware-only validation

---

## Out-of-Scope For The Pilot Phase

These users may matter later, but should not drive v1.5.0-pilot decisions:

- casual individual consumers
- parents running ad-hoc mobile setups
- tournament/game-day users requiring portable installation
- cloud-only analytics users without local facility workflow

Revisit these after setup friction, accuracy validation, and pilot adoption are
proven.

---

## Discovery Questions

### Setup and Operations

1. Who actually performs first-time setup?
2. How often is the rig moved?
3. What setup duration is acceptable?
4. What proof is required before a setup is ready for coaching?
5. Which failures happen most: camera identity, calibration, overlap, lighting,
   ROI, recording, or operator workflow?

### Coaching Workflow

1. What is the minimum useful live output?
2. Who operates the laptop during practice?
3. Which actions happen every session?
4. What happens immediately after the session: replay, export, upload, or
   conversation?
5. Which metrics are trusted today, and which need reference validation?

### Facility Buying Decision

1. What competitor or reference system does the facility already trust?
2. What support burden is acceptable during a pilot?
3. What usage volume would justify purchase?
4. What accuracy evidence must be public before conversion?
5. What privacy commitments are required for athlete data?

### Athlete Review

1. Does the athlete want quick takeaways, clips, trends, or full reports?
2. Which comparisons matter most?
3. How much technical detail is helpful?
4. What device is used for review?
5. What makes the athlete trust the system: video, overlays, metrics, or coach
   commentary?

---

## Documentation Implications

- User docs should separate first-time setup from daily session operation.
- Accuracy claims must point to validation status, not aspirational targets.
- Support docs need real contact channels before pilot distribution.
- Pilot docs should state facility/academy fit clearly and avoid consumer
  positioning.
- Schema and contract changes should reference these personas only when user
  role affects routing, privacy, or durable output.
