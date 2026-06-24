# PitchTracker: Product Strategy and Capability Contract

**Document Type:** Internal Planning & Decision Framework
**Date:** March 26, 2026
**Applies To:** v1.5.0-pilot (Canonical Pilot Build)
**Purpose:** Compound existing product value through disciplined capability development and enabling investments

---

## Part 1: Executive Summary

### Where We Stand

**What is strong:**

PitchTracker has achieved meaningful engineering maturity. The product has:
- A working stereo vision pipeline with real-time 3D tracking
- Three distinct operational modes (Setup, Coaching, Review) with role-appropriate UIs
- A pattern detection system with pitch classification and anomaly detection
- 389+ automated tests at 98%+ coverage
- Desktop packaging with auto-update infrastructure
- Documented APIs and serializable contracts
- Performance optimizations delivering 60-90 FPS detection
- Multiple visualization modes including trajectory overlay, heat maps, and trend analysis

This is not a prototype. This is a functional product with depth.

**What is risky:**

The product's commercial readiness lags its engineering readiness:
- **Setup friction is high**: ChArUco board printing, dual camera positioning, ROI calibration, strike zone configuration. This is a 30-60 minute setup process requiring technical literacy.
- **Trust is unproven**: No published accuracy validation, no comparison to trusted references (Rapsodo, TrackMan), no defined operating envelope.
- **Release discipline needs enforcement**: Version strings are now aligned around v1.5.0-pilot, but test reporting, installer publication, and "ready" claims still need a single verified release record.
- **Market positioning is unclear**: The product appears aimed at everyone but is realistically suitable for facilities and academies today, not casual users.
- **Feature breadth outpaces adoption proof**: Multiple dashboards, game modes, and analytics exist before pilot evidence shows which ones actually matter.

**What is likely true:**

PitchTracker is **pilot-ready for controlled environments** with technical operators. It is **not yet ready for casual consumer adoption** without substantial setup simplification and published validation. The product is strongest as a facility/academy tool where:
- Technical setup is one-time
- Cameras remain fixed
- Operators can be trained
- Value compounds over repeated sessions

**What should happen next:**

Continue advancing core capabilities while prioritizing enabling work that makes those capabilities **trusted, repeatable, and adoptable**. This means:

1. **Establish one canonical pilot build** with known-good hardware and validated accuracy
2. **Run structured pilots** in 2-3 academies with measurable success criteria
3. **Reduce setup friction** before expanding feature surface area
4. **Publish validation evidence** for velocity, location, and reliability claims
5. **Clean up release discipline** so external observers see consistent quality signals
6. **Continue core development** in tracking, detection, and analysis—but only where it strengthens differentiated value and passes the capability contract

This is not about stopping development. This is about **making development compound** by ensuring each capability lands on a foundation of trust, usability, and commercial proof.

---

## Part 2: What Continues Without Interruption

The following areas represent strategic assets that should continue advancing:

### Core Tracking & Detection Engine
**Status:** Continue developing
**Why:** This is the product's technical moat. Improvements in detection accuracy, stereo matching speed, and trajectory modeling directly strengthen every downstream capability.

**Ongoing investments:**
- Detection algorithm refinement (classical and ML-based)
- Stereo matching optimization
- Trajectory smoothing and physics validation
- Performance optimization for higher frame rates
- ML data export for future model training

**Rationale:** Better tracking accuracy reduces false positives, improves user trust, and makes all analytics more reliable. This is the foundation.

### Pattern Detection & Analytics
**Status:** Continue developing with validation discipline
**Why:** Pitch classification, anomaly detection, and trend analysis are differentiated capabilities. Most competitors don't offer automatic repertoire analysis or fatigue detection.

**Ongoing investments:**
- Heuristic classifier refinement based on pilot feedback
- Cross-session trend analysis for pitcher development tracking
- Baseline comparison features for coaching workflows
- Report generation improvements

**Constraint:** New analytics must include validation criteria (see Capability Contract). Don't expand dashboard surface area without pilot evidence of usage.

### Review Mode & Post-Session Workflow
**Status:** Continue refining
**Why:** Review mode is where coaches actually make decisions. Trajectory replay, parameter tuning, and pitch-by-pitch analysis are core to coaching workflows.

**Ongoing investments:**
- Playback UX improvements
- Annotation and scoring workflows
- Export format improvements for athlete sharing
- Side-by-side pitch comparison features

**Constraint:** Focus on workflows that pilots actually use, not hypothetical features.

### UI/UX for Coaching Workflows
**Status:** Continue with user feedback loops
**Why:** The three-mode visualization system (Broadcast, Progression, Game) represents real thought about coaching needs. Game modes add engagement value.

**Ongoing investments:**
- Mode refinement based on pilot usage data
- Simplified session start flow
- In-session control improvements
- Fatigue indicator refinements

**Constraint:** New modes or dashboards require pilot validation before public release.

### Architecture & Contracts
**Status:** Protect and extend
**Why:** The separation between UI, service layer, and serializable contracts enables future flexibility. The manifest schema, recording format, and export contracts are assets.

**Ongoing investments:**
- Contract versioning discipline
- Schema validation in tests
- Export format stability
- API documentation

**Rationale:** This enables future work (cloud services, third-party integrations, ML pipelines) without breaking existing installations.

### Test Infrastructure & Performance
**Status:** Maintain and extend
**Why:** 389+ tests at 98% coverage is a competitive advantage. Memory leak prevention, stress testing, and integration tests reduce support burden.

**Ongoing investments:**
- Integration test coverage for new features
- Performance regression tests
- Memory profiling
- Accuracy validation test harness (new—see next section)

**Rationale:** High test coverage enables faster iteration with lower regression risk.

---

## Part 3: Immediate Next Steps

### Next 30 Days: Foundation and Pilot Prep

| # | Action | Objective | Owner | Outcome | Priority | Risk |
|---|--------|-----------|-------|---------|----------|------|
| 1 | **Create Known-Good Hardware Profile** | Define validated camera models, mounting specs, lighting requirements | Engineering + Founder | Published hardware spec doc, tested config | **P0** | Low—mostly documentation |
| 2 | **Establish Canonical Release Build** | Lock v1.5.0-pilot as pilot baseline, freeze feature additions to pilot branch | Engineering | Tagged release, installer with consistent version strings | **P0** | Low—version discipline |
| 3 | **Clean Up Version Signals** | Align README, installer name, status docs, test reports to single version truth | Product/Founder | Externally consistent messaging | **P0** | Low—documentation only |
| 4 | **Draft Accuracy Validation Plan** | Design test protocol: compare PitchTracker to trusted reference (radar gun, known trajectory) | Engineering + Founder | Test protocol document | **P0** | Medium—requires equipment access |
| 5 | **Identify 2-3 Pilot Partners** | Recruit facilities/academies willing to run structured 4-week pilots | Founder | Signed pilot agreements with success criteria | **P0** | High—requires outreach and partner buy-in |
| 6 | **Create Pilot Success Metrics** | Define what "pilot success" means: session count, velocity accuracy, user retention, workflow adoption | Product/Founder | Pilot scorecard document | **P0** | Low—definition exercise |
| 7 | **Package Pilot Onboarding Kit** | Hardware checklist, setup guide, calibration walkthrough, troubleshooting FAQ | Product/UX | Onboarding PDF + video | **P0** | Medium—requires documentation + recording |

**Why this matters:** Without a locked pilot build and clear success criteria, pilots become ad-hoc feature testing instead of product validation. Version consistency is a trust signal.

---

### Next 60-90 Days: Run Pilots and Validate

| # | Action | Objective | Owner | Outcome | Priority | Risk |
|---|--------|-----------|-------|---------|----------|------|
| 8 | **Execute Pilot Deployments** | Install pilot build at 2-3 facilities, train operators, run sessions | Founder + Pilot Partners | 3 live installations with trained operators | **P0** | High—requires on-site support |
| 9 | **Run Accuracy Validation Tests** | Execute validation protocol: compare velocity, location, trajectory to trusted reference | Engineering + QA | Validation report with error bounds (±X mph, ±Y inches) | **P0** | High—requires reference equipment and methodology |
| 10 | **Collect Pilot Usage Data** | Track session count, feature usage, setup time, error rate, user feedback | Product | Pilot analytics dashboard + qualitative feedback log | **P0** | Medium—requires telemetry and feedback loops |
| 11 | **Simplify Setup Flow (High-Value Fixes Only)** | Reduce setup friction based on pilot pain points—focus on highest-ROI improvements | Engineering + UX | Reduced setup time by 30%+ or clearer failure messaging | **P1** | Medium—scope creep risk |
| 12 | **Publish Accuracy Validation Report** | Release public accuracy validation with methodology, error bounds, and operating envelope | Product/Founder | Public validation doc + README update | **P1** | Low—depends on test #9 |
| 13 | **Define Operating Envelope** | Document known-good conditions: camera distance range, lighting requirements, ball type, speed range | Engineering | Operating envelope spec (public) | **P1** | Low—documentation |
| 14 | **Create Pilot Case Studies** | Document 1-2 pilot partner experiences: setup, usage, value delivered | Product/Founder | Case study PDFs or web pages | **P2** | Low—depends on pilot success |

**Why this matters:** Pilots provide evidence. Validation provides trust. Operating envelope prevents overpromising. Without these, the product remains "interesting" instead of "credible."

**Dependency:** Steps 8-10 must complete before step 11 (setup simplification) to avoid premature optimization.

---

### Next 6 Months: Scale Readiness and Core Development

| # | Action | Objective | Owner | Outcome | Priority | Risk |
|---|--------|-----------|-------|---------|----------|------|
| 15 | **Iterate Setup Flow Based on Pilot Data** | Implement high-ROI setup improvements: guided calibration, auto-ROI suggestions, pre-flight checks | Engineering + UX | Setup time reduced by 50%+ | **P0** | Medium—requires UX design + validation |
| 16 | **Harden Error Recovery** | Improve camera reconnection, disk space handling, and failure messaging based on pilot issues | Engineering | Reduced support calls, improved error messaging | **P0** | Medium—requires incident analysis |
| 17 | **Expand Pilot Program to 5-10 Sites** | Scale pilot program with validated build and improved setup flow | Founder | 5-10 active pilot sites with measurable usage | **P1** | High—requires sales/BD effort |
| 18 | **Launch Public Beta Program** | Open pilot program to early adopters with clear expectations and feedback loops | Founder + Product | Public beta landing page, 20+ beta users | **P1** | Medium—requires support infrastructure |
| 19 | **Continue Core Capability Development** | Advance trajectory modeling, detection accuracy, analytics depth—features that pass capability contract | Engineering | Measurable improvements in accuracy, speed, or differentiated analytics | **P1** | Low—ongoing development |
| 20 | **Implement ML-Based Detector (if validated)** | If pilot data justifies ML detector investment, train and deploy model | Engineering | ML detector option with accuracy comparison to classical | **P2** | High—requires training data and validation |
| 21 | **Explore Cloud Analytics (Optional)** | If pilots show demand, prototype cloud-based trend comparison and multi-pitcher analytics | Engineering | Cloud analytics prototype with pilot feedback | **P2** | High—requires infrastructure and privacy design |

**Why this matters:** Pilots inform setup simplification. Validated builds enable scaling. Core development continues where it strengthens differentiated value.

**Philosophy:** Continue building, but ensure each capability lands on a foundation of trust and usability.

---

## Part 4: Capability Contract

All future capabilities must satisfy this contract before being added to the product roadmap. Existing capabilities should be evaluated against this contract and hardened where gaps exist.

### 1. User Value

**Principle:** Features must solve real coaching or operational problems, not just look impressive.

**Required Criteria:**
- Clear answer to "What coaching decision does this enable?"
- Evidence of user demand (pilot feedback, interview notes, or workflow observation)
- Repeatable value—users would use it every session, not just once

**Red Flags:**
- "Wouldn't it be cool if..." features without user validation
- Dashboards that don't inform actions
- Analytics that users can't interpret or act on

**Approval Questions:**
1. What specific coaching action does this enable?
2. What evidence do we have that users want this?
3. Will users engage with this every session or rarely?

---

### 2. Evidence and Validation

**Principle:** Claims must be supported by evidence. Accuracy must be validated before public exposure.

**Required Criteria:**
- New metrics require validation protocol (comparison to reference, error bounds, sample size)
- Pattern detection requires pilot confirmation (pitch classification accuracy, anomaly detection precision)
- Performance claims require benchmark data (FPS, latency, resource usage)

**Red Flags:**
- "Probably accurate" without measurement
- Extrapolating from limited test cases
- Marketing claims without technical backing

**Approval Questions:**
1. What validation test proves this capability works?
2. What are the error bounds and operating limits?
3. What failure modes exist and how are they communicated?

**For Existing Capabilities:**
- **Velocity tracking:** Requires validation against radar gun or TrackMan (±X mph at Y distance)
- **Location tracking:** Requires validation against marked target grid (±X inches)
- **Pitch classification:** Requires human expert agreement rate (X% match) on sample set

---

### 3. Workflow Fit

**Principle:** Features must fit actual session workflows, not hypothetical ideal workflows.

**Required Criteria:**
- Clear workflow integration: when does the user interact with this?
- Neutral or positive friction impact: does this make sessions faster, same speed, or slower?
- Operator skill match: can non-expert users operate this reliably?

**Red Flags:**
- Features that require stopping mid-session for configuration
- UI modes that require training to understand
- "Power user" features that slow down basic operations

**Approval Questions:**
1. When in the session workflow does this get used?
2. Does this speed up or slow down the operator?
3. Can this be used without technical expertise?

---

### 4. Setup and Calibration Impact

**Principle:** Features must not increase setup complexity without proportional value.

**Required Criteria:**
- Setup complexity assessment: does this add steps, time, or failure modes?
- Deployability impact: does this work with existing hardware or require new equipment?
- Fragility analysis: does this increase sensitivity to environmental conditions?

**Red Flags:**
- Features requiring additional calibration steps
- Features sensitive to lighting, distance, or environmental factors not already controlled
- Features requiring operator expertise beyond current baseline

**Approval Questions:**
1. Does this increase setup time or complexity?
2. Does this require additional hardware or calibration?
3. Does this increase the number of ways setup can fail?

**Acceptable Exceptions:**
- Features that simplify setup (auto-calibration, guided workflows)
- One-time setup increases with long-term operational benefits
- Optional advanced features that don't impact basic operation

---

### 5. Architectural Fit

**Principle:** Features must align with the existing architecture and contract model.

**Required Criteria:**
- Uses existing service layer abstractions (PipelineService, ReviewService)
- Persists data through serializable contracts (session manifest, recording format)
- UI/backend separation maintained
- Does not introduce hidden coupling or side effects

**Red Flags:**
- Direct UI-to-pipeline coupling bypassing service layer
- Unversioned data formats
- Features that break existing export contracts
- "Quick hacks" that violate separation of concerns

**Approval Questions:**
1. Does this fit the existing service architecture?
2. Are data formats versioned and serializable?
3. Could this feature be reimplemented in a different UI without backend changes?

---

### 6. Supportability

**Principle:** Features must be testable, documentable, and supportable by non-developers.

**Required Criteria:**
- Automated test coverage (unit + integration)
- User-facing documentation (how to use, what to expect, how to troubleshoot)
- Error messages that guide non-expert users
- Telemetry or logging for remote troubleshooting

**Red Flags:**
- "Works on my machine" features
- Undocumented configuration knobs
- Features that fail silently
- Features that require developer intervention to debug

**Approval Questions:**
1. How will this be tested automatically?
2. What documentation is required for users?
3. How will support diagnose issues remotely?

---

### 7. Commercial Relevance

**Principle:** Features must serve realistic early adopters, not hypothetical broad markets.

**Required Criteria:**
- Alignment with facility/academy operating environment (fixed camera setup, trained operators)
- Value for 10-50 session volume (not just single-session novelty)
- Differentiation from consumer smartphone apps (why pay for this?)

**Red Flags:**
- Features aimed at casual consumers before setup simplification
- Features requiring data volumes only high-end facilities generate
- Features that compete with free smartphone apps on convenience

**Approval Questions:**
1. Does this help facilities/academies specifically?
2. Does this value compound over repeated sessions?
3. Why would someone pay for this instead of using a smartphone app?

---

### 8. Release Readiness

**Principle:** Features are not "done" until they are documented, tested, validated, and ready for external use.

**Required Criteria:**
- Test coverage: unit + integration tests passing
- Documentation: user guide + troubleshooting
- Validation: accuracy tested, error bounds known
- Failure handling: graceful degradation, clear error messages
- Release notes: changelog entry with known limitations

**Red Flags:**
- "90% done" features in public builds
- Features enabled by default without validation
- Missing documentation or unclear operating limits
- Breaking changes without migration path

**Approval Questions:**
1. Is this ready for non-developer users?
2. Are known limitations documented?
3. Can this be supported remotely?

---

### Contract Enforcement Process

**Before adding to roadmap:**
1. Feature proposal must address all 8 contract areas
2. Product owner reviews against scoring rubric (see Part 5)
3. Engineering lead assesses implementation risk and architectural fit
4. Founder approves based on commercial relevance and resource allocation

**For existing capabilities:**
- Identify contract gaps (e.g., velocity validation not published)
- Create hardening plan (e.g., run validation tests, publish results)
- Prioritize based on user visibility and trust impact
- Do not remove capabilities—strengthen them

---

## Part 5: Decision Filter for Future Roadmap Items

Use this scoring rubric to evaluate any proposed capability. Score each category 1-5, apply weights, sum to 100-point scale.

### Scoring Scale
- **5:** Exceptional—major competitive advantage or trust multiplier
- **4:** Strong—clear value, low risk, good fit
- **3:** Neutral—acceptable but not compelling
- **2:** Weak—marginal value or significant concerns
- **1:** Poor—fails contract, high risk, or misaligned

### Weighted Categories

| Category | Weight | Scoring Guidance | Low Score Example (1-2) | High Score Example (4-5) |
|----------|--------|------------------|------------------------|-------------------------|
| **Trust & Validation Impact** | 25% | Does this improve or require validation? Does it strengthen credibility? | Unvalidated metric that could be wrong | Accuracy validation test, published operating envelope |
| **Friction Reduction** | 20% | Does this reduce setup time, operator burden, or error rate? | Adds setup step or requires training | Auto-calibration, guided workflow, error prevention |
| **User Value** | 20% | Does this enable coaching decisions or improve session outcomes? | Dashboard that looks nice but doesn't inform actions | Feature that changes how coaches make decisions |
| **Fit for Target Market** | 15% | Does this help facilities/academies specifically? | Casual consumer feature before setup simplification | Feature that compounds value over 10+ sessions |
| **Implementation Complexity** | 10% | Engineering effort vs. value delivered | 6+ months for marginal feature | 1-2 weeks for high-impact feature |
| **Architecture Alignment** | 5% | Fits existing contracts and service model? | Bypasses architecture, creates coupling | Clean service layer extension, versioned contract |
| **Support Burden** | 3% | Can non-developers support this? | Requires developer debugging | Clear error messages, self-service troubleshooting |
| **Differentiation** | 2% | Does this separate from competitors? | Commodity feature (e.g., basic video playback) | Unique capability (e.g., automatic repertoire analysis) |

### Total Score Interpretation

- **80-100:** Strong candidate—prioritize if resources available
- **60-79:** Acceptable—consider timing and dependencies
- **40-59:** Marginal—defer unless strategic necessity
- **Below 40:** Reject—fails contract or misaligned

### Scoring Examples

**Example 1: Automatic Pitch Classification (Already Implemented)**
- Trust & Validation: 3 (needs pilot validation) × 25% = 18.75
- Friction Reduction: 5 (eliminates manual tagging) × 20% = 20
- User Value: 4 (enables repertoire analysis) × 20% = 16
- Target Market Fit: 5 (facilities want this) × 15% = 11.25
- Implementation: 4 (moderate complexity) × 10% = 4
- Architecture: 5 (clean service integration) × 5% = 2.5
- Support: 4 (mostly self-service) × 3% = 1.2
- Differentiation: 5 (few competitors offer this) × 2% = 1
- **Total: 74.7** → Acceptable, prioritize validation

**Example 2: Social Media Sharing Feature (Hypothetical)**
- Trust & Validation: 5 (no accuracy concerns) × 25% = 12.5
- Friction Reduction: 3 (neutral) × 20% = 6
- User Value: 2 (nice-to-have, not core) × 20% = 4
- Target Market Fit: 1 (consumer feature, not facility) × 15% = 2.25
- Implementation: 3 (moderate effort) × 10% = 3
- Architecture: 3 (needs API integration) × 5% = 1.5
- Support: 2 (privacy concerns, failure modes) × 3% = 0.6
- Differentiation: 1 (commodity feature) × 2% = 0.2
- **Total: 30.05** → Reject—misaligned with target market

**Example 3: Velocity Accuracy Validation (Proposed)**
- Trust & Validation: 5 (directly improves trust) × 25% = 25
- Friction Reduction: 4 (prevents user doubt) × 20% = 8
- User Value: 4 (enables confident coaching) × 20% = 8
- Target Market Fit: 5 (facilities need proof) × 15% = 7.5
- Implementation: 4 (test design + execution) × 10% = 4
- Architecture: 5 (no changes needed) × 5% = 2.5
- Support: 5 (reduces support burden) × 3% = 1.5
- Differentiation: 4 (few competitors publish validation) × 2% = 0.8
- **Total: 57.3** → Strong candidate—prioritize

### How to Use This Rubric

1. **For new feature proposals:** Score before adding to roadmap
2. **For roadmap reviews:** Re-score existing items as priorities shift
3. **For resource allocation:** Fund high-scoring items first
4. **For hardening decisions:** Use to prioritize which existing capabilities to validate or improve

**Important:** This rubric is a decision aid, not a replacement for judgment. Context matters. Use this to structure discussions, not to mechanically approve/reject.

---

## Part 6: Recommendation on Roadmap Philosophy

### The Right Framing

The roadmap decision is not "features versus foundations." That framing implies a false choice between building the product and making it work.

The right framing is: **Continue building core capabilities while prioritizing enabling work that makes those capabilities trusted, repeatable, and adoptable.**

### What This Means in Practice

**Continue core development where it strengthens differentiated value:**
- Better detection accuracy → more reliable tracking → higher user trust
- Trajectory modeling improvements → better pitch analysis → coaching insights
- Pattern detection refinement → automatic repertoire analysis → competitive advantage
- Review mode workflow improvements → faster coaching decisions → session efficiency

These investments compound. They make the product better at its core job: tracking pitches accurately and providing coaching insights. They should not pause.

**Prioritize enabling work when it unlocks adoption, trust, or repeatability:**
- Accuracy validation → proves the product works → converts skeptics to buyers
- Setup simplification → reduces onboarding friction → enables self-service pilots
- Release discipline → improves external perception → reduces doubt
- Operating envelope documentation → sets clear expectations → prevents misuse
- Pilot program → generates proof points → enables commercial traction

These investments unlock value across many capabilities. They are force multipliers.

**Avoid work that creates complexity without improving real-world usefulness:**
- Analytics dashboards without pilot evidence of usage
- Game modes beyond the existing three without engagement data
- Broad-market features before setup is simplified for target market
- Unvalidated metrics that could be wrong
- Features that bypass the architecture contract
- "Cool demo" features that don't inform coaching decisions

These investments fragment the product. They add surface area without adding foundation.

### What Should Be Deprioritized (Explicit Examples)

**Defer these until validation and pilots are complete:**

1. **Additional analytics dashboards without usage proof**
   - Example: "Pitcher fatigue prediction model" before existing fatigue indicator is validated in pilots
   - Rationale: More dashboards don't help if users don't trust the underlying data

2. **Consumer-oriented features before setup simplification**
   - Example: Mobile app, cloud sharing, social media integration
   - Rationale: Setup friction prevents consumer adoption regardless of convenience features

3. **Broad-market positioning before facility proof**
   - Example: Marketing to youth leagues or individual pitchers
   - Rationale: Setup requirements and price point match facilities, not casual users

4. **Unvalidated metrics that could be wrong**
   - Example: "Injury risk score" without biomechanical validation
   - Rationale: Wrong metrics damage trust more than missing metrics

5. **Features that add complexity without measurable coaching value**
   - Example: 3D trajectory visualization for every pitch (vs. on-demand replay)
   - Rationale: Cognitive load matters—more data is not always better

6. **Features that bypass the architecture contract**
   - Example: Quick hacks that couple UI directly to pipeline
   - Rationale: Technical debt accumulates faster than product value

**When to reconsider deferred work:**
- After 5+ successful pilots provide evidence of demand
- After setup time is reduced by 50%+ from baseline
- After velocity and location validation is published
- After revenue or pilot conversion provides resources for expansion

### Roadmap Decision Process (Practical)

**Monthly Roadmap Review:**
1. Score new proposals using Part 5 rubric
2. Re-evaluate in-progress work against pilot feedback
3. Adjust priorities based on trust/friction/adoption gaps identified in pilots
4. Allocate 70% capacity to core development, 30% to enabling work

**Quarterly Strategy Review:**
1. Assess pilot progress against success criteria
2. Evaluate market positioning based on pilot partner profiles
3. Adjust capability contract if operating environment changes
4. Update roadmap philosophy based on commercial traction

**Ad-Hoc Feature Requests:**
1. Apply capability contract (Part 4)
2. Score using rubric (Part 5)
3. Compare to existing roadmap—what gets displaced?
4. Approve only if score >60 and aligns with current phase priorities

---

## Part 7: Draft One-Page Internal Policy

---

# PitchTracker Capability and Release Alignment Policy

**Effective Date:** March 2026
**Owner:** Founder/Product Lead
**Purpose:** Strengthen and compound the existing product through disciplined capability development

## Policy Statement

No capability gets added to PitchTracker because it is interesting alone. New capabilities must improve trust, usability, or commercial viability. This policy exists to protect the product's value, not to slow delivery with process theater.

## Core Principles

1. **Capabilities must serve real coaching workflows**
   Every feature must answer: "What coaching decision does this enable?" If the answer is "none" or "it looks cool," the feature is rejected.

2. **Claims must be supported by evidence**
   Accuracy metrics require validation tests. Performance claims require benchmark data. Pattern detection requires pilot confirmation. "Probably works" is not acceptable.

3. **Setup friction is a veto criterion**
   Features that increase setup complexity, calibration steps, or operator training requirements are rejected unless they provide proportional long-term value.

4. **Release discipline is part of product quality**
   Features are not "done" until they are tested, documented, validated, and ready for non-developer use. "90% done" features do not ship.

5. **Target market alignment is mandatory**
   PitchTracker is a facility/academy tool today. Features aimed at casual consumers are deferred until setup friction is solved. Fit the realistic market, not the aspirational one.

6. **Architecture alignment is non-negotiable**
   Features must use the service layer, persist through versioned contracts, and maintain UI/backend separation. Architectural shortcuts are rejected.

## Approval Requirements

Before adding a capability to the roadmap:
- [ ] Passes all 8 areas of the Capability Contract (Part 4)
- [ ] Scores >60 on the Decision Filter Rubric (Part 5)
- [ ] Includes validation plan (if accuracy-related)
- [ ] Includes documentation plan (user guide + troubleshooting)
- [ ] Includes test plan (unit + integration coverage)
- [ ] Reviewed by Product Owner and Engineering Lead
- [ ] Approved by Founder based on commercial relevance

## What This Policy Does Not Mean

- **Does not mean:** Stop building features
- **Does mean:** Build features that compound value

- **Does not mean:** Pause core development
- **Does mean:** Prioritize enabling work that unlocks adoption

- **Does not mean:** Reject innovation
- **Does mean:** Validate before scaling

- **Does not mean:** Bureaucratic approval process
- **Does mean:** Structured decision-making with clear criteria

## Enforcement

- **Monthly roadmap reviews** apply this policy to new proposals
- **Quarterly strategy reviews** assess whether policy criteria need adjustment
- **Founder has final decision authority** on exceptions

## Revision History

- v1.0 (March 2026): Initial policy

---

## Top 5 Actions to Do First

1. **Lock v1.5.0-pilot as canonical pilot build**
   Freeze feature additions. Align version strings across README, installer, status docs. Make this the source of truth.

2. **Design and execute velocity validation test**
   Compare PitchTracker velocity readings to radar gun or TrackMan. Publish error bounds (±X mph). Define operating envelope.

3. **Recruit 2-3 pilot partners with measurable success criteria**
   Target facilities/academies. Define success: X sessions in 4 weeks, Y% velocity accuracy, Z% user retention. Document expectations.

4. **Create known-good hardware profile and setup guide**
   Publish validated camera models, mounting specs, lighting requirements. Package as pilot onboarding kit.

5. **Establish capability contract enforcement**
   Adopt Part 4 contract and Part 5 scoring rubric. Apply to all new proposals starting immediately.

---

## Top 5 Things to Avoid

1. **Do not expand analytics dashboards before pilot validation**
   More dashboards don't help if users don't trust underlying data or use existing ones.

2. **Do not add consumer-oriented features before setup simplification**
   Mobile apps, social sharing, broad-market positioning are premature. Solve facility adoption first.

3. **Do not ship unvalidated accuracy claims**
   "Probably accurate" damages trust more than acknowledging uncertainty. Validate or don't claim.

4. **Do not bypass the architecture contract for "quick wins"**
   Coupling UI to pipeline, unversioned formats, and service layer violations accumulate debt faster than value.

5. **Do not treat pilots as ad-hoc beta testing**
   Pilots must have clear success criteria, structured feedback loops, and measurable outcomes. Otherwise they waste partner goodwill.

---

## Final Recommended Capability Contract (Checklist Form)

Use this checklist to evaluate any proposed capability before adding to roadmap:

### User Value
- [ ] Solves specific coaching or operational problem (describe)
- [ ] Evidence of user demand (pilot feedback, interview, or workflow observation)
- [ ] Repeatable value—users would use every session, not just once

### Evidence and Validation
- [ ] Validation protocol defined (for accuracy-related features)
- [ ] Error bounds and operating limits documented
- [ ] Failure modes identified and communicated

### Workflow Fit
- [ ] Clear integration point in session workflow
- [ ] Neutral or positive impact on operator speed
- [ ] Usable by non-expert operators

### Setup and Calibration Impact
- [ ] Does not increase setup complexity (or provides proportional long-term value)
- [ ] Works with existing hardware (or hardware addition is justified)
- [ ] Does not increase environmental sensitivity

### Architectural Fit
- [ ] Uses existing service layer abstractions
- [ ] Persists through versioned, serializable contracts
- [ ] Maintains UI/backend separation
- [ ] No hidden coupling or side effects

### Supportability
- [ ] Automated test coverage (unit + integration)
- [ ] User documentation (how to use, troubleshoot)
- [ ] Clear error messages for non-experts
- [ ] Telemetry/logging for remote diagnosis

### Commercial Relevance
- [ ] Fits facility/academy operating environment
- [ ] Value compounds over 10+ sessions
- [ ] Differentiates from free consumer alternatives

### Release Readiness
- [ ] Test coverage complete and passing
- [ ] Documentation complete (user guide + troubleshooting)
- [ ] Validation complete (if accuracy-related)
- [ ] Failure handling and error messages implemented
- [ ] Release notes with known limitations

### Scoring and Approval
- [ ] Scored using Part 5 rubric (score: ____)
- [ ] Reviewed by Product Owner (approved/rejected)
- [ ] Reviewed by Engineering Lead (approved/rejected)
- [ ] Approved by Founder (approved/rejected)

---

## STRATEGIC UPDATE: TAG Sports Partnership (March 26, 2026)

### Major GTM Evolution

**Original Strategy:** Solo facility sales, compete with consumer radar guns
**New Strategy:** **Partner with TAG Sports** to create consumer-to-facility ecosystem

**Why This Changes Everything:**
- TAG Sports serves consumer market ($230 portable radar) - **we don't compete, we integrate**
- PitchTracker serves facility market ($1,200 stereo vision) - **complementary, not competitive**
- Creates consumer→facility pipeline: TAG users → PitchTracker facilities
- 4-13× revenue increase potential (Year 1: $774K-1M vs. $60K-200K solo)

### Partnership Value Proposition

**For TAG Sports:**
- New revenue stream ($50-150 per facility referral, $90K-135K/year potential)
- Competitive moat (exclusive PitchTracker integration vs. Pocket Radar)
- Network effects (more facilities → more valuable to consumers)

**For PitchTracker:**
- Qualified lead pipeline (TAG's 10K+ users already value tracking)
- Brand awareness (piggyback on TAG's D2C marketing)
- Unique differentiation (vs. Rapsodo, TrackMan)

**For Athletes:**
- Data continuity (practice at home → train at facility, seamless data flow)
- Affordable path ($230 TAG + $75/month facility vs. $3K Rapsodo)

### Integration Architecture

**Phase 1: MVP (Months 1-3)**
- TAG Sports: Add "Export to PitchTracker" button (JSON export)
- PitchTracker: Add "Import TAG Sports Data" feature
- Manual transfer (athlete exports → emails to coach → facility imports)

**Phase 2: Cloud Sync (Months 7-12)**
- Unified athlete profile service (cloud API)
- Auto-sync TAG practice data to PitchTracker facilities
- Seamless (no manual transfer)

**Phase 3: Unified Ecosystem (2027+)**
- Mobile companion app (view TAG + PitchTracker data)
- Advanced analytics (combine home practice + facility training)
- Predictive insights (ML using integrated dataset)

### Roadmap Impact

**New High-Priority Features (Partnership-Driven):**
1. TAG Sports data import (Month 2) - Score: 85/100
2. Practice History tab (Month 2) - Score: 78/100
3. Facility vs. Practice trend charts (Month 3) - Score: 72/100
4. Cloud sync (Months 7-9) - Score: 81/100

**These features now PASS capability contract because:**
- ✅ User Value: Enables data continuity (high coaching value)
- ✅ Validation: Easy to validate (does import work?)
- ✅ Workflow Fit: Pre-session setup (coach sees practice history)
- ✅ Setup Impact: Neutral (import is optional)
- ✅ Architecture: Clean service layer extension
- ✅ Supportability: Simple workflow, clear error messages
- ✅ Commercial Relevance: Attracts TAG users to facilities (target market)
- ✅ Release Readiness: Low-risk MVP, clear scope

**Deferred Consumer Features (Still Rejected):**
- ❌ Standalone mobile app (TAG Sports handles consumer market)
- ❌ Portability improvements (TAG Sports handles portability)
- ❌ Social media sharing (TAG Sports handles consumer social)

### Next Immediate Actions (Updated)

**This Week:**
1. Research TAG Sports contacts (CEO, Head of Partnerships)
2. Prepare partnership outreach (one-pager ready)
3. Initiate contact (warm intro preferred, or LinkedIn/email)

**Next 2 Weeks:**
4. Discovery call with TAG Sports (present partnership vision)
5. Deliver full proposal (40+ pages documentation ready)
6. Negotiate MOU (referral %, exclusivity, pilot structure)

**Month 2 (If MOU Signed):**
7. Build MVP integration (TAG export + PitchTracker import)
8. Recruit pilot facilities with TAG user overlap
9. Co-marketing partnership announcement

**Months 3-4:**
10. Launch MVP integration publicly
11. Track referral revenue and facility enrollments
12. Evaluate partnership success (proceed to full MSA or iterate)

### Documentation Created

**Partnership Strategy Documents:**
- `TAG_SPORTS_PARTNERSHIP_STRATEGY.md` (40 pages) - Full partnership plan
- `TAG_INTEGRATION_TECHNICAL_SPEC.md` (35 pages) - Technical implementation
- `TAG_PARTNERSHIP_PROPOSAL_ONE_PAGER.md` (3 pages) - Executive summary for outreach
- `GTM_STRATEGY_TAG_PARTNERSHIP.md` (30 pages) - Revised go-to-market strategy
- `COMPETITIVE_ANALYSIS_TAG_SPORTS.md` (25 pages) - Competitive intelligence

**Total:** 133+ pages of partnership planning (ready for execution)

---

**End of Document** (Updated March 26, 2026 with TAG Sports Partnership Strategy)
