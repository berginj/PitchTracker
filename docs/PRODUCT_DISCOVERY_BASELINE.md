# Product Discovery Baseline

Last updated: 2026-03-06

## Goal

Capture the current product understanding implied by the codebase, define the
baseline questions we still need to answer with end users, and identify the
highest-value areas for improvement in the product and contract model.

## Current Product Model

The repo currently implies three product surfaces:
- Setup and calibration for technical operators.
- Live coaching and session operation for daily use.
- Post-session review and pattern analysis for coach and athlete follow-up.

The strongest explicit personas today are:
- Setup Technician / Installer
- Coach / Session Operator
- Pitcher / Athlete Review Recipient

Reference: `contracts-shared/PERSONAS.md`

## Current Assumptions To Validate

- The coach is the primary buyer and daily operator.
- A technical setup role exists even if it is not always a separate person.
- The athlete is usually the consumer of exported results rather than the direct
  operator of the laptop.
- Fast session start matters more than exposing technical controls during live
  use.
- Setup artifacts and diagnostics matter because the rig is not always fixed and
  failure recovery matters in the field.

## Questions To Bring Back From Users

### Workflow Questions

1. Is the dominant usage model fixed-install or portable?
2. How often are cameras moved or recalibrated?
3. What is the acceptable time from app launch to first pitch captured?
4. What does a "successful" session mean for the primary customer?
5. Which output is used most often after a session: local review, export,
   printed report, or cloud analytics?

### Coaching Questions

1. Which live metrics actually change coaching behavior?
2. What is the minimum viable live dashboard for practice?
3. Does the coach want per-pitch feedback, session summaries, or both?
4. How often does a coach review previous sessions during practice?

### Athlete Questions

1. What does the athlete expect to receive after a session?
2. Which comparison views create trust and repeat use?
3. Does the athlete need a coach-mediated report or a self-serve review view?

### Setup and Support Questions

1. What evidence does support need when troubleshooting a bad install?
2. Which setup outputs must be preserved and shared between roles?
3. How should the product signal "ready for coaching" versus "setup incomplete"?

## Potential Areas for Improvement

### High Priority

1. Unify contract version governance.
   The repo currently has multiple schema version sources with different values.
   That makes it hard to know which contract version is authoritative.

2. Add a setup handoff contract.
   The setup workflow produces durable outputs such as calibration quality,
   camera selections, ROI state, and readiness, but there is no shared contract
   that represents that handoff cleanly.

3. Add richer session context to exported artifacts.
   Session summary and upload payloads capture pitch data, but they do not fully
   capture operating context such as ball type, batter profile, calibration
   provenance, operator role, or intended review audience.

4. Add schema-backed validation tests.
   The codebase has contract dataclasses and JSON Schemas, but contract tests do
   not strongly enforce that exported payloads continue to match the published
   schemas.

### Medium Priority

1. Define a player-review contract.
   The product talks about player review and pattern analysis, but there is no
   shared contract for a player-facing report package or analysis report.

2. Reduce role-model confusion.
   Some artifacts describe a role-based launcher and separate setup/coaching
   experiences, while older surfaces still imply one expert operator handling
   everything in a single UI.

3. Remove no-code onboarding gaps.
   User-facing setup still depends on command-line steps for calibration-board
   generation even though the product positions itself as installer-friendly for
   non-programmers.

### Lower Priority

1. Separate customer segments more clearly.
   Youth, private coaching, team practice, and advanced analytics likely want
   different defaults and success metrics.

2. Clarify privacy and cloud posture.
   The upload path exists, but the product story does not yet clearly define
   when data stays local versus when it moves to cloud services.

## Recommended Next Product Actions

1. Interview at least one real user in each baseline persona before expanding
   contract fields.
2. Decide whether the authoritative contract source of truth is
   `contracts-shared/schema` or the root `schema` directory.
3. Define a minimal setup-result artifact and whether it must be portable across
   machines.
4. Define the player-facing review artifact before expanding analysis features.
5. Convert the highest-value exported payloads into schema-validated tests.