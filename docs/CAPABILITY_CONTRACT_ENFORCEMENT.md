# Capability Contract Enforcement Framework

**Document Type:** Process & Template Library
**Date:** March 26, 2026
**Version:** 1.0 (for v1.5.0-pilot and beyond)
**Owner:** Product Lead + Engineering Lead
**Status:** OPERATIONAL

---

## Purpose

This document provides the **operational framework** for enforcing the Capability Contract defined in `PRODUCT_STRATEGY.md`. It includes templates, workflows, and decision-making tools to ensure all new capabilities pass the 8-point contract before being added to the product.

**Key Principle:**
> "No capability gets added because it is interesting alone. New capabilities must improve trust, usability, or commercial viability."

---

## Table of Contents

1. [Feature Proposal Template](#1-feature-proposal-template)
2. [Capability Contract Checklist](#2-capability-contract-checklist)
3. [Scoring Rubric (Evaluation Tool)](#3-scoring-rubric-evaluation-tool)
4. [Approval Workflow](#4-approval-workflow)
5. [Monthly Roadmap Review Template](#5-monthly-roadmap-review-template)
6. [Decision Log Format](#6-decision-log-format)
7. [Rejection Criteria & Appeals](#7-rejection-criteria--appeals)
8. [Enforcement Examples](#8-enforcement-examples)

---

## 1. Feature Proposal Template

Use this template when proposing any new capability. Submit to Product Lead for review.

```markdown
# Feature Proposal: [Feature Name]

**Proposer:** [Name]
**Date:** [YYYY-MM-DD]
**Status:** Draft / Under Review / Approved / Rejected
**Target Release:** [Version number, e.g., v1.6.0]

---

## Executive Summary (1-2 sentences)

[What is this feature and why does it matter?]

---

## Problem Statement

**What problem does this solve?**
[Describe the user pain point or coaching workflow gap]

**Evidence of need:**
- [ ] Pilot partner request (facility: ___, date: ___)
- [ ] User interview findings (summarize)
- [ ] Analytics data showing gap (link to data)
- [ ] Competitive gap (competitor has this, we don't)
- [ ] Other: ___

---

## Proposed Solution

**High-level description:**
[Describe the feature in 2-3 paragraphs]

**User interaction:**
[How does the user interact with this feature? When in the workflow?]

**Mock-ups / wireframes:**
[Attach or link to visual designs if available]

---

## Capability Contract Evaluation

### 1. User Value ✅ ⚠️ ❌

**Coaching decision enabled:**
[What specific coaching decision does this enable?]

**Evidence of user demand:**
[Pilot feedback? Interview quotes? Usage data?]

**Repeatable value:**
- [ ] Users would use this every session
- [ ] Users would use this occasionally (1-2× per month)
- [ ] Users would use this rarely (novelty feature)

**Score (1-5):** ___

---

### 2. Evidence & Validation ✅ ⚠️ ❌

**Validation protocol:**
[How will we prove this works? What tests are required?]

**Error bounds / operating limits:**
[What accuracy is required? What are known limitations?]

**Failure modes:**
[What happens when this feature fails? How is it communicated?]

**Score (1-5):** ___

---

### 3. Workflow Fit ✅ ⚠️ ❌

**Workflow integration:**
[When in the session workflow is this used? Pre-session? During? Post?]

**Friction impact:**
- [ ] Reduces friction (makes sessions faster/easier)
- [ ] Neutral (no impact on session flow)
- [ ] Adds friction (requires extra steps/configuration)

**Operator skill required:**
- [ ] No technical expertise needed
- [ ] Basic computer skills needed
- [ ] Technical expertise required

**Score (1-5):** ___

---

### 4. Setup & Calibration Impact ✅ ⚠️ ❌

**Setup complexity:**
- [ ] No additional setup (uses existing calibration)
- [ ] One-time setup (add to initial calibration flow)
- [ ] Per-session setup (requires ongoing configuration)

**Hardware requirements:**
- [ ] Works with existing hardware
- [ ] Requires additional hardware: ___

**Environmental sensitivity:**
- [ ] Same operating envelope as existing features
- [ ] Narrows operating envelope: ___
- [ ] Requires specific conditions: ___

**Score (1-5):** ___

---

### 5. Architectural Fit ✅ ⚠️ ❌

**Service layer integration:**
- [ ] Uses existing PipelineService methods
- [ ] Requires new service methods (describe): ___
- [ ] Bypasses service layer (REJECT unless justified)

**Data persistence:**
- [ ] Uses existing contracts (session manifest, recording format)
- [ ] Requires new contract (provide schema): ___
- [ ] Unversioned data (REJECT)

**UI/backend separation:**
- [ ] Maintains clean separation
- [ ] Some coupling (justify): ___
- [ ] Tight coupling (REJECT unless justified)

**Score (1-5):** ___

---

### 6. Supportability ✅ ⚠️ ❌

**Test coverage:**
- [ ] Unit tests planned (estimate coverage: ___%)
- [ ] Integration tests planned
- [ ] No tests (REJECT)

**Documentation:**
- [ ] User guide update planned
- [ ] Troubleshooting section planned
- [ ] No documentation (REJECT)

**Error messaging:**
- [ ] Clear error messages for non-experts
- [ ] Technical error messages only
- [ ] Silent failures (REJECT)

**Remote diagnostics:**
- [ ] Telemetry/logging included
- [ ] No diagnostic capability

**Score (1-5):** ___

---

### 7. Commercial Relevance ✅ ⚠️ ❌

**Target market fit:**
- [ ] Facilities/academies will use this (primary market)
- [ ] Only high-end facilities (narrow market)
- [ ] Consumer-oriented (defer until setup simplified)

**Value compounding:**
- [ ] Value increases over 10+ sessions
- [ ] Single-session value only

**Competitive differentiation:**
- [ ] Unique capability (competitors don't have this)
- [ ] Parity feature (competitors have similar)
- [ ] Commodity feature (everyone has this)

**Score (1-5):** ___

---

### 8. Release Readiness ✅ ⚠️ ❌

**Definition of "done":**
- [ ] Tests written and passing
- [ ] Documentation complete
- [ ] Validation complete (if accuracy-related)
- [ ] Error handling implemented
- [ ] Release notes drafted
- [ ] Known limitations documented

**Release risk:**
- [ ] Low risk (isolated feature, good test coverage)
- [ ] Medium risk (touches multiple systems, needs careful testing)
- [ ] High risk (breaking change, requires migration)

**Score (1-5):** ___

---

## Weighted Score Calculation

| Category | Score (1-5) | Weight | Weighted Score |
|----------|-------------|--------|----------------|
| Trust & Validation | ___ | 25% | ___ |
| Friction Reduction | ___ | 20% | ___ |
| User Value | ___ | 20% | ___ |
| Target Market Fit | ___ | 15% | ___ |
| Implementation | ___ | 10% | ___ |
| Architecture Fit | ___ | 5% | ___ |
| Support Burden | ___ | 3% | ___ |
| Differentiation | ___ | 2% | ___ |
| **TOTAL** | | **100%** | **___/100** |

**Interpretation:**
- **80-100:** Strong candidate - prioritize if resources available
- **60-79:** Acceptable - consider timing and dependencies
- **40-59:** Marginal - defer unless strategic necessity
- **<40:** Reject - fails contract or misaligned

---

## Implementation Plan

**Estimated effort:**
[Engineering hours/days/weeks]

**Key milestones:**
1. Design complete: [date]
2. Implementation complete: [date]
3. Testing complete: [date]
4. Documentation complete: [date]
5. Ready for release: [date]

**Dependencies:**
[What must be done first? Blockers?]

**Resources required:**
[Engineering, design, QA, documentation]

---

## Risks & Mitigation

**Key risks:**
1. [Risk]: [Mitigation plan]
2. [Risk]: [Mitigation plan]

---

## Alternatives Considered

**Alternative 1:** [Description]
- **Pros:** ___
- **Cons:** ___
- **Why not chosen:** ___

**Alternative 2:** [Description]
- **Pros:** ___
- **Cons:** ___
- **Why not chosen:** ___

---

## Approval Section

**Product Lead Review:**
- [ ] Approved
- [ ] Approved with conditions: ___
- [ ] Rejected - Reason: ___
- **Signature:** ___________ **Date:** ___

**Engineering Lead Review:**
- [ ] Approved
- [ ] Approved with conditions: ___
- [ ] Rejected - Reason: ___
- **Signature:** ___________ **Date:** ___

**Founder Approval:**
- [ ] Approved
- [ ] Approved with conditions: ___
- [ ] Rejected - Reason: ___
- **Signature:** ___________ **Date:** ___

---

**Final Decision:** Approved / Rejected / Deferred
**Rationale:** [Summary of decision reasoning]
**Next Steps:** [What happens next?]
```

---

## 2. Capability Contract Checklist

Quick checklist for evaluating features. Can be used in meetings or quick reviews.

```markdown
# Capability Contract Quick Check

**Feature:** [Name]
**Reviewer:** [Name]
**Date:** [YYYY-MM-DD]

## Pass/Fail Checklist

### Critical (Must Pass All)
- [ ] Solves real coaching problem (not just "cool idea")
- [ ] Evidence of user demand (pilot feedback, interview, or data)
- [ ] Passes architectural fit (uses service layer, versioned contracts)
- [ ] Includes test plan (unit + integration)
- [ ] Includes documentation plan (user guide + troubleshooting)
- [ ] Has validation plan (if accuracy-related)

### High Priority (Should Pass Most)
- [ ] Fits actual session workflow (clear integration point)
- [ ] Doesn't increase setup complexity (or provides proportional value)
- [ ] Supports facilities/academies (target market)
- [ ] Value compounds over 10+ sessions
- [ ] Includes error handling (clear messages for non-experts)

### Medium Priority (Nice to Have)
- [ ] Reduces friction (makes sessions faster/easier)
- [ ] Differentiates from competitors
- [ ] Low implementation complexity (quick win)

## Red Flags (Automatic Reject)
- [ ] ❌ Unvalidated accuracy claims
- [ ] ❌ Consumer feature before setup simplification
- [ ] ❌ Bypasses architecture (direct UI-to-pipeline coupling)
- [ ] ❌ No test coverage
- [ ] ❌ No documentation
- [ ] ❌ "Probably works" without validation

## Decision
- [ ] ✅ PASS - Move to detailed scoring
- [ ] ⚠️ CONDITIONAL - Address issues: ___
- [ ] ❌ REJECT - Reason: ___

**Next Action:** ___
```

---

## 3. Scoring Rubric (Evaluation Tool)

Spreadsheet-style scoring tool for quantitative evaluation.

```csv
Category,Weight,Criteria,Score (1-5),Weighted Score,Notes
Trust & Validation,25%,Improves credibility / requires validation,,,
Friction Reduction,20%,Reduces setup / operator burden,,,
User Value,20%,Enables coaching decisions,,,
Target Market Fit,15%,Helps facilities/academies,,,
Implementation,10%,Effort vs. value (5=quick win 1=months),,,
Architecture Fit,5%,Fits service model,,,
Support Burden,3%,Non-developer supportable,,,
Differentiation,2%,Separates from competitors,,,
TOTAL,100%,,,/100,
```

**Scoring Guidelines:**

**5 - Exceptional:**
- Validation: Proves product works, publishable results
- Friction: Eliminates major pain point (e.g., auto-calibration)
- User Value: Changes how coaches make decisions
- Market Fit: Enables new customer segment
- Implementation: 1-2 weeks, high impact
- Architecture: Clean extension, no coupling
- Support: Self-service, clear error messages
- Differentiation: Unique to PitchTracker

**4 - Strong:**
- Validation: Measurable improvement in trust
- Friction: Noticeable time savings
- User Value: Frequently used, clear benefit
- Market Fit: Core to target customer workflow
- Implementation: 2-4 weeks, good ROI
- Architecture: Fits well with minor adjustments
- Support: Mostly self-service
- Differentiation: Better than competitors

**3 - Neutral:**
- Validation: No impact on trust
- Friction: Neutral (neither helps nor hurts)
- User Value: Occasionally useful
- Market Fit: Acceptable for target market
- Implementation: 4-8 weeks, moderate value
- Architecture: Acceptable with workarounds
- Support: Some support needed
- Differentiation: Parity with competitors

**2 - Weak:**
- Validation: Could damage trust if wrong
- Friction: Slight increase in complexity
- User Value: Rarely used
- Market Fit: Narrow appeal
- Implementation: 8-12 weeks, marginal value
- Architecture: Requires compromises
- Support: Frequent support needed
- Differentiation: Commodity feature

**1 - Poor:**
- Validation: Unvalidated, likely wrong
- Friction: Major setup burden
- User Value: Novelty only, no real benefit
- Market Fit: Wrong market segment
- Implementation: 3+ months, low value
- Architecture: Breaks patterns, creates debt
- Support: Requires developer intervention
- Differentiation: Behind competitors

---

## 4. Approval Workflow

### Step 1: Proposal Submission
**Who:** Feature proposer (anyone on team)
**What:** Complete Feature Proposal Template
**Where:** Submit to Product Lead via email or shared document
**Timeline:** Anytime

### Step 2: Initial Screening
**Who:** Product Lead
**What:** Quick check against contract checklist (5-10 minutes)
**Decision:**
- **Pass:** Move to detailed review
- **Conditional:** Request clarifications/revisions
- **Reject:** Provide reasoning, suggest alternatives

**Timeline:** Within 2 business days

### Step 3: Detailed Review
**Who:** Product Lead + Engineering Lead
**What:** Score feature using rubric, evaluate against roadmap
**Meeting:** Optional 30-minute discussion if score is close (55-65 range)
**Timeline:** Within 1 week

### Step 4: Founder Approval (if score ≥60)
**Who:** Founder
**What:** Final approval based on commercial relevance and resource allocation
**Timeline:** Within 3 business days

### Step 5: Decision Communication
**Who:** Product Lead
**What:** Notify proposer of decision with reasoning
**Document:** Log decision in Decision Log
**Timeline:** Within 1 business day of final decision

### Step 6: Roadmap Addition (if approved)
**Who:** Product Lead
**What:** Add to roadmap with priority and target release
**Communication:** Share in next team meeting or roadmap update

### Fast-Track Process (Urgent Items)

**Criteria for fast-track:**
- Critical pilot blocker (prevents pilot success)
- Security/safety issue
- Competitive emergency (must-have for customer retention)

**Process:**
- Same contract evaluation (no shortcuts)
- Compressed timeline (decisions within 24 hours)
- Synchronous review meeting instead of async
- Founder approval required

---

## 5. Monthly Roadmap Review Template

Conducted first Monday of each month.

```markdown
# Monthly Roadmap Review - [Month YYYY]

**Date:** [YYYY-MM-DD]
**Attendees:** Founder, Product Lead, Engineering Lead
**Duration:** 60-90 minutes

---

## Agenda

1. Review last month's commitments (10 min)
2. Score new proposals (30 min)
3. Re-evaluate in-progress work (20 min)
4. Adjust priorities based on pilot feedback (15 min)
5. Capacity allocation (10 min)
6. Action items (5 min)

---

## 1. Last Month's Commitments

| Feature | Status | Notes |
|---------|--------|-------|
| [Feature A] | ✅ Shipped | On time, no issues |
| [Feature B] | 🚧 In Progress | Delayed 1 week, still on track |
| [Feature C] | ❌ Deferred | Deprioritized due to pilot feedback |

**Learnings:**
- [What went well?]
- [What could be improved?]

---

## 2. New Proposals to Score

### Proposal 1: [Feature Name]
- **Proposer:** ___
- **Score:** ___/100
- **Decision:** Approve / Defer / Reject
- **Reasoning:** ___
- **Target Release:** ___

### Proposal 2: [Feature Name]
- **Proposer:** ___
- **Score:** ___/100
- **Decision:** Approve / Defer / Reject
- **Reasoning:** ___
- **Target Release:** ___

---

## 3. In-Progress Work Re-Evaluation

### Feature X (in v1.6.0)
- **Status:** 60% complete
- **Pilot Feedback:** ___
- **Decision:** Continue / Adjust Scope / Cancel
- **Notes:** ___

### Feature Y (in v1.6.0)
- **Status:** 80% complete
- **Pilot Feedback:** ___
- **Decision:** Continue / Adjust Scope / Cancel
- **Notes:** ___

---

## 4. Pilot Feedback Integration

**Key Insights from Pilots:**
1. [Insight from Facility A]
2. [Insight from Facility B]
3. [Insight from Facility C]

**Roadmap Adjustments:**
- [Move Feature Z to higher priority based on feedback]
- [Defer Feature W - no pilot demand]
- [Add new feature request to backlog]

---

## 5. Capacity Allocation (Next Month)

**Total Engineering Capacity:** [X person-weeks]

**Allocation:**
- **70% Core Development:** [List features]
- **30% Enabling Work:** [Validation, setup simplification, pilot support]

**Rationale:**
[Why these priorities? How do they align with strategic plan?]

---

## 6. Action Items

- [ ] [Action]: [Owner] - [Due Date]
- [ ] [Action]: [Owner] - [Due Date]
- [ ] [Action]: [Owner] - [Due Date]

---

**Next Review:** [First Monday of next month]
```

---

## 6. Decision Log Format

Track all feature decisions in a central log (CSV or spreadsheet).

```csv
Date,Feature Name,Proposer,Score,Decision,Reasoning,Target Release,Status
2026-03-26,Automatic Pitch Classification,Engineering,74.7,Approved,High value for facilities - needs validation,v1.5.0,Shipped
2026-03-28,Social Media Sharing,Marketing,30.1,Rejected,Consumer feature - defer until setup simplified,N/A,Rejected
2026-04-02,Velocity Validation Tests,Engineering,87.3,Approved,Critical for trust building,v1.5.0-pilot,In Progress
2026-04-05,Cloud Analytics Dashboard,Product,52.4,Deferred,Good idea but premature - wait for pilot data,v1.7.0 (maybe),Deferred
```

**Columns:**
- **Date:** When decision was made
- **Feature Name:** Short name
- **Proposer:** Who proposed it
- **Score:** Total weighted score (0-100)
- **Decision:** Approved / Rejected / Deferred
- **Reasoning:** One-sentence rationale
- **Target Release:** Version number (if approved)
- **Status:** Shipped / In Progress / Deferred / Rejected / Cancelled

---

## 7. Rejection Criteria & Appeals

### Automatic Rejection Criteria

Features are **automatically rejected** if they meet ANY of these criteria:

1. **No test coverage** - Feature has no test plan
2. **Unvalidated accuracy claims** - Makes accuracy claims without validation protocol
3. **Bypasses architecture** - Direct UI-to-pipeline coupling without justification
4. **No documentation plan** - No user guide or troubleshooting section
5. **Consumer feature pre-setup simplification** - Targets consumers before setup is simplified
6. **Score <40** - Fails weighted scoring rubric

**Exception Process:**
- Proposer can request exception review with **written justification**
- Requires unanimous approval (Product Lead + Engineering Lead + Founder)
- Rarely granted (expect <5% exception rate)

### Conditional Approval Criteria

Features may be **conditionally approved** with requirements:

1. **Score 60-69:** Approved IF specific improvements made (e.g., add tests, improve docs)
2. **Pilot blocker:** Approved IF critical for pilot success (fast-track with heightened scrutiny)
3. **Strategic value:** Score 55-59 but strategically critical (Founder override)

**Conditions must be met before implementation begins.**

### Appeals Process

**If feature is rejected:**
1. **Proposer may appeal** within 5 business days
2. **Appeal must include:**
   - Why rejection reasoning is incorrect
   - New evidence addressing concerns
   - Revised proposal with improvements
3. **Appeal reviewed by** Founder (final decision)
4. **Timeline:** Decision within 3 business days

**Appeal outcomes:**
- **Approved:** Feature added to roadmap
- **Conditionally Approved:** With specific requirements
- **Upheld Rejection:** Decision stands, proposer notified

---

## 8. Enforcement Examples

### Example 1: Feature Proposal - "Injury Risk Prediction"

**Proposal:** Add ML model that predicts injury risk based on mechanics degradation

**Contract Evaluation:**
1. **User Value:** ⚠️ Coaches interested BUT no evidence they'd trust it
2. **Validation:** ❌ No biomechanical validation, medical liability concerns
3. **Workflow Fit:** ⚠️ Post-session review, doesn't affect in-session coaching
4. **Setup Impact:** ✅ No additional setup
5. **Architecture:** ✅ Clean service extension
6. **Supportability:** ❌ Requires expert interpretation, no clear error handling
7. **Market Fit:** ⚠️ Appeals to high-end facilities only (narrow market)
8. **Release Readiness:** ❌ No validation, no liability review

**Score:** 35/100

**Decision:** **REJECTED**

**Reasoning:** Unvalidated medical/injury claim creates liability risk. No biomechanical validation protocol. Wrong metrics damage trust more than missing metrics.

**Alternative:** Defer until after partnerships with sports medicine experts and rigorous validation.

---

### Example 2: Feature Proposal - "Guided Calibration Wizard Improvements"

**Proposal:** Add visual progress indicator, auto-detect board quality, provide real-time feedback

**Contract Evaluation:**
1. **User Value:** ✅ Reduces setup frustration (top pilot complaint)
2. **Validation:** ✅ Easy to validate (does calibration complete successfully?)
3. **Workflow Fit:** ✅ Improves pre-session setup (reduces time by 30%+)
4. **Setup Impact:** ✅ **Reduces** setup complexity (key goal)
5. **Architecture:** ✅ Contained within setup wizard, clean separation
6. **Supportability:** ✅ Reduces support calls (fewer calibration failures)
7. **Market Fit:** ✅ All facilities benefit (universal improvement)
8. **Release Readiness:** ✅ Clear success criteria, testable, documentable

**Score:** 86/100

**Decision:** **APPROVED - HIGH PRIORITY**

**Reasoning:** Directly addresses pilot pain point (setup friction). Aligns with strategic priority to reduce setup complexity. High ROI for enabling work.

**Target Release:** v1.6.0 (post-pilot based on feedback)

---

### Example 3: Feature Proposal - "Multi-Language Support"

**Proposal:** Add Spanish, Japanese translations for UI

**Contract Evaluation:**
1. **User Value:** ⚠️ Enables international expansion BUT no current demand
2. **Validation:** ✅ Easy to validate (translation accuracy)
3. **Workflow Fit:** ✅ Transparent to workflow (doesn't change operations)
4. **Setup Impact:** ✅ Neutral (no setup changes)
5. **Architecture:** ⚠️ Requires i18n framework integration (moderate effort)
6. **Supportability:** ⚠️ Increases support complexity (multi-language docs)
7. **Market Fit:** ❌ Not aligned with current target (US facilities/academies)
8. **Release Readiness:** ⚠️ Significant testing required (all UI strings)

**Score:** 48/100

**Decision:** **DEFERRED**

**Reasoning:** Good idea for future international expansion, but premature. No current demand from target market (US facilities). Defer until after domestic pilots successful and setup simplified.

**Reconsider:** v2.0 (if international expansion becomes strategic priority)

---

## Appendix A: Quick Reference Card

Print and post in team workspace or meeting room.

```
┌─────────────────────────────────────────────────────────────┐
│         PITCHTRACKER CAPABILITY CONTRACT CHECKLIST          │
│                   (Quick Reference)                         │
└─────────────────────────────────────────────────────────────┘

Before proposing a feature, ask:

✅ MUST PASS (Critical):
 □ Solves real coaching problem?
 □ Evidence of user demand?
 □ Has test plan?
 □ Has documentation plan?
 □ Fits architecture (service layer, contracts)?
 □ Has validation plan (if accuracy-related)?

⚠️ SHOULD PASS (Important):
 □ Fits actual workflow?
 □ Doesn't increase setup complexity?
 □ Serves facilities/academies?
 □ Value compounds over 10+ sessions?
 □ Clear error messages for non-experts?

❌ AUTOMATIC REJECT:
 × Unvalidated accuracy claims
 × Consumer feature (before setup simplified)
 × Bypasses architecture
 × No tests or documentation
 × Score <40 on rubric

📊 SCORING THRESHOLDS:
 80-100: Strong candidate (prioritize)
 60-79:  Acceptable (evaluate timing)
 40-59:  Marginal (defer)
 <40:    Reject (misaligned)

📋 SUBMIT TO:
 Product Lead (use Feature Proposal Template)

───────────────────────────────────────────────────────────────
"No feature gets added because it is interesting alone."
        - PitchTracker Capability & Release Alignment Policy
```

---

## Appendix B: Common Rejection Reasons

Keep this list handy for consistent decision communication.

1. **"No evidence of user demand"**
   - No pilot feedback, interview data, or usage analytics supporting need
   - Suggestion: Validate demand before reproposing

2. **"Fails validation requirement"**
   - Makes accuracy claims without validation protocol
   - Suggestion: Develop validation methodology first

3. **"Consumer feature - defer until setup simplified"**
   - Targets casual users before setup friction is solved
   - Suggestion: Wait for facility market success first

4. **"Increases setup complexity without proportional value"**
   - Adds calibration steps or configuration burden
   - Suggestion: Simplify or justify with significant value

5. **"Bypasses architecture contract"**
   - Couples UI directly to pipeline, skips service layer
   - Suggestion: Refactor to fit architecture model

6. **"Insufficient test coverage"**
   - No unit or integration tests planned
   - Suggestion: Add test plan before reproposing

7. **"Score below threshold (<60)"**
   - Weighted score indicates low value or high risk
   - Suggestion: Address low-scoring categories and resubmit

8. **"Wrong market segment"**
   - Targets market outside current focus (facilities/academies)
   - Suggestion: Defer until market expansion phase

9. **"Low ROI given implementation effort"**
   - Engineering effort outweighs user value
   - Suggestion: Simplify scope or find higher-leverage approach

10. **"Pilot priorities take precedence"**
    - Good feature but not critical during pilot phase
    - Suggestion: Repropose post-pilot with updated context

---

**Document Status:** OPERATIONAL - Ready for immediate use
**Owner:** Product Lead
**Maintained By:** Product team
**Review Frequency:** Quarterly (adjust process based on learnings)
**Last Updated:** March 26, 2026
