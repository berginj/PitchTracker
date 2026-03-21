# PitchTracker - Next Steps

**Date:** 2026-03-06
**Status:** Contract baseline established, product discovery gaps identified

---

## Goal

Turn the current review findings and persona work into an actionable backlog that
stabilizes contract governance, validates product assumptions with end users,
and defines the next durable artifacts the system needs.

## References

- `docs/PRODUCT_DISCOVERY_BASELINE.md`
- `contracts-shared/PERSONAS.md`
- `contracts-shared/README.md`

---

## Priority Definitions

- `P1` Blocks reliable delivery or creates contract ambiguity
- `P2` Important product or workflow gap that should be resolved before broadening scope
- `P3` Valuable follow-up once the core contract and workflow model is stable

---

## P1: Immediate Next 1-2 Weeks

### 1. Establish One Contract Source of Truth

**Why:** The repo still has duplicated contract surfaces in `schema/` and
`contracts-shared/schema/`, which makes drift likely even after the version
alignment and schema tests.

**Actions:**
- [ ] Decide whether `contracts-shared/schema/` or `schema/` is authoritative
- [ ] Document the decision in `contracts-shared/README.md` and `docs/README.md`
- [ ] Add a sync/release process for version bumps, sample payloads, and schema updates
- [ ] Decide whether the non-authoritative copy should be generated, mirrored, or removed

**Deliverable:** documented contract ownership model and a repeatable update path

### 2. Expand Contract Validation Beyond Static Samples

**Why:** We now validate published schemas and examples, but exported runtime
payloads should also be checked against those same contracts.

**Actions:**
- [ ] Add tests for session summary export payloads from `ui/export.py`
- [ ] Add tests for upload payload construction
- [ ] Add tests for `record/training_report.py` output against the shared schema
- [ ] Add a regression test for export dialog code paths that depend on Qt imports

**Deliverable:** export-producing code validated against published schemas

### 3. Define the Setup Handoff Artifact

**Why:** The setup workflow produces meaningful state, but there is no durable
contract for handing that state from installer/setup to daily coaching use.

**Actions:**
- [ ] Define the minimum setup artifact fields
- [ ] Include camera identifiers, calibration provenance, ROI state, validation status, and readiness
- [ ] Decide whether this is local-only or portable across machines
- [ ] Draft a schema before adding new runtime code

**Deliverable:** schema proposal for setup handoff / readiness

---

## P2: Next 2-4 Weeks

### 4. Run User Discovery Against the Baseline Personas

**Why:** The current personas are strong, but still inferred from code and docs.

**Actions:**
- [ ] Interview at least one setup technician / installer
- [ ] Interview at least one coach / session operator
- [ ] Interview at least one pitcher / athlete review recipient
- [ ] Capture answers to the question bank in `contracts-shared/PERSONAS.md`
- [ ] Update `docs/PRODUCT_DISCOVERY_BASELINE.md` with validated assumptions

**Deliverable:** validated persona notes and a sharper problem statement

### 5. Decide the Minimum Successful Coach Workflow

**Why:** Contract scope depends on what output actually creates value during and
immediately after a session.

**Actions:**
- [ ] Decide the minimum live output for coaches
- [ ] Decide the required end-of-session output
- [ ] Rank replay, export, upload, and pattern analysis by actual user value
- [ ] Use that ranking to guide future contract fields

**Deliverable:** explicit definition of the minimum successful session

### 6. Define the Player Review Artifact

**Why:** The product talks about player review, but there is no shared contract
for the thing the athlete actually receives.

**Actions:**
- [ ] Decide whether the athlete consumes a summary, clips package, analysis report, or all three
- [ ] Define audience, delivery channel, and trust signals
- [ ] Draft a player-facing artifact contract if needed
- [ ] Align pattern-analysis outputs to that artifact

**Deliverable:** player review artifact definition and contract direction

---

## P3: Follow-On Work

### 7. Add Richer Session Context Only After Workflow Decisions

Potential fields to revisit after discovery:
- operator role
- calibration provenance
- ball type
- batter profile / strike-zone context
- review audience
- session mode

**Rule:** do not add these fields until they clearly support a user workflow.

### 8. Reduce Role Confusion Across Product Surfaces

**Why:** The launcher and newer docs describe role-based workflows, while older
surfaces still imply a single expert operator.

**Actions:**
- [ ] Audit docs and UI entry points for setup/coaching/review role language
- [ ] Decide whether the legacy all-in-one experience remains strategic
- [ ] Align help text and onboarding to the chosen model

### 9. Clarify Privacy and Cloud Posture

**Why:** Upload exists, but the product story does not yet clearly explain when
data remains local versus when it moves to cloud systems.

**Actions:**
- [ ] Define default local vs cloud behavior
- [ ] Define required identity and privacy fields
- [ ] Decide whether customer segment changes the default

---

## Exit Criteria For This Next Phase

- One contract source of truth is documented
- Runtime exports are validated against published schemas
- Setup handoff artifact is defined
- Baseline personas are validated with real users
- Coach success criteria and player review artifact are explicitly defined