# PitchTracker Personas and Workflow Context

Last updated: 2026-03-06

## Purpose

This document establishes the baseline end-user personas currently implied by
the codebase, UI copy, and user documentation. Shared schemas reference these
personas so contract decisions can stay tied to real workflows instead of
generic payload design.

## Baseline Personas

### 1. Setup Technician / Installer

Job to be done: get a dual-camera rig physically installed, calibrated,
validated, and declared ready for live coaching sessions with minimal rework.

Primary tasks:
- Select the correct left and right cameras.
- Measure and enter the physical baseline.
- Run calibration and confirm quality.
- Configure ROI, detector settings, and validation checks.
- Export or hand off a ready-to-use setup to the coaching workflow.

What success looks like:
- Setup can be completed in one guided flow.
- Calibration quality is clear and trustworthy.
- The system can prove it is ready for coaching before handoff.
- Troubleshooting evidence is easy to export for support.

### 2. Coach / Session Operator

Job to be done: start a live session quickly, capture reliable pitch results,
and turn those results into immediate coaching decisions.

Primary tasks:
- Launch the coaching experience with minimal setup friction.
- Select the pitcher and session context.
- Start capture and recording quickly.
- Monitor velocity, strike/ball outcome, and location during practice.
- End the session cleanly and export or upload results.

What success looks like:
- Session start takes seconds, not minutes.
- Live metrics are understandable without technical knowledge.
- The coach can trust the output enough to change drills in real time.
- Export and review paths match the coach's next step.

### 3. Pitcher / Athlete Review Recipient

Job to be done: understand what changed in a session, what to work on next, and
how current performance compares with prior sessions or baselines.

Primary tasks:
- Review session output after practice.
- Understand velocity, location, movement, and pitch-type patterns.
- Compare current results with previous sessions or a pitcher profile.
- Share or discuss takeaways with the coach.

What success looks like:
- The athlete receives a simple and credible summary.
- The report answers "What changed?" and "What should I work on next?"
- The review artifact is easy to consume on a non-technical device.

## Contract Mapping

### `session_summary.schema.json`

Primary workflow: coach completes or pauses a live session and needs a compact
summary for review, export, or upload.

Persona relevance:
- Primary producer: Coach / Session Operator
- Primary consumers: Coach / Session Operator, Pitcher / Athlete Review Recipient

### `session_upload.schema.json`

Primary workflow: a session leaves the local desktop product and is handed to a
remote analytics or reporting system.

Persona relevance:
- Primary producer: Coach / Session Operator or upload integration
- Primary consumers: Cloud analytics, dashboards, later reviewer experiences

### `training_report.schema.json`

Primary workflow: setup validation, troubleshooting, or diagnostics where a
technical operator needs evidence about capture quality and system health.

Persona relevance:
- Primary producer: Setup Technician / Installer
- Primary consumers: Setup Technician / Installer, support, engineering

### `marker_spec.schema.json`

Primary workflow: marked-ball experiments where detection or training tooling
needs a stable representation of the marking geometry.

Persona relevance:
- Primary producers: Vision engineer, advanced setup operator
- Primary consumers: Vision tooling and analysis pipelines

## Discovery Questions To Ask End Users

### Questions for Setup Technicians / Installers

1. Who usually owns first-time setup: installer, coach, parent, or athlete?
2. How often is the rig moved between locations?
3. What setup duration is acceptable before users feel blocked?
4. What proof is required before a setup is considered "ready for coaching"?
5. Which setup failures are most common in the field: camera selection,
   calibration quality, alignment, lighting, or performance?

### Questions for Coaches / Session Operators

1. What is the minimum useful output during a live session: velocity, location,
   strike/ball, movement, or pitch classification?
2. Who operates the laptop during practice?
3. How many steps are acceptable before the first pitch can be captured?
4. Which actions happen every session versus only during initial setup?
5. When a session ends, what is the next action: replay, export, upload, or
   discussion with the athlete?

### Questions for Pitchers / Athlete Review Recipients

1. What does the athlete want immediately after a session: quick takeaways,
   clips, trends, or a full analytics report?
2. Which comparisons matter most: session-to-session, baseline-to-current, or
   pitch-type breakdown?
3. How much technical detail is useful versus distracting?
4. Is the review artifact consumed on the same laptop, on mobile, or shared
   later by the coach?
5. Which outputs make the athlete trust the system: video, overlays, metrics,
   or coach commentary?

### Cross-Cutting Questions

1. What environments matter most: portable bullpen, fixed indoor lane, team
   practice, or game-day warmup?
2. How much cloud usage is acceptable for the target customer?
3. What privacy expectations exist for athlete identity and session data?
4. Are youth, high-school, college, and advanced private coaching all in scope,
   or should the product optimize for one segment first?

## Immediate Contract Implications

- Do not add persona fields just to label users; add them only when they change
  behavior, routing, privacy, or product outcomes.
- Add workflow context through README guidance, schema `description`, and
  `$comment` fields first.
- Add a new contract when a new durable artifact appears, especially for setup
  handoff, calibration validation, or player-facing review packages.
- Treat session context, calibration provenance, and export audience as likely
  future contract needs.