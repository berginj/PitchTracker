# TAG Sports Integration - Value Summary & Visual Guide

**Document Type:** Partnership Value Communication
**Date:** March 26, 2026
**Audience:** TAG Sports Leadership, Engineering, Product
**Purpose:** Communicate integration vision clearly and compellingly

---

## The Vision (One Sentence)

**Make TAG Sports devices work seamlessly at home AND at professional facilities, creating a consumer-to-pro ecosystem where practice data flows everywhere and athletes never outgrow their TAG device.**

---

## Integration Phases (Visual Roadmap)

```
PHASE 1 (Months 1-3): Manual Export/Import
═══════════════════════════════════════════════════════════════
 TAG App        File         Facility
 ┌─────┐       ┌────┐       ┌─────┐
 │ 📱  │──────>│📄  │──────>│ 💻  │
 └─────┘       └────┘       └─────┘
           Manual Transfer

VALUE: Data continuity (basic)
EFFORT: 2-4 weeks
FRICTION: Medium (manual)


PHASE 2 (Months 4-6): Cloud Sync
═══════════════════════════════════════════════════════════════
 TAG App                     Facility
 ┌─────┐       ┌─────┐      ┌─────┐
 │ 📱  │──────>│ ☁️  │<─────│ 💻  │
 └─────┘       └─────┘      └─────┘
          Auto-Sync Cloud Platform

VALUE: Seamless sync (no athlete action)
EFFORT: 8-12 weeks + cloud
FRICTION: Low (automatic)


PHASE 3 (Months 7-9): Bluetooth PC Ingest ⭐ GAME-CHANGER
═══════════════════════════════════════════════════════════════
 TAG Device               Facility PC
 ┌─────────┐  Bluetooth  ┌──────────┐
 │   📡    │<──────────>│ 💻 + 📷  │
 └─────────┘  Real-time  └──────────┘
    ↕️                        ↕️
  Mobile App              Cloud API

DUAL-MODE: TAG works at home (app) AND facility (PC)
VALUE: Real-time streaming, cross-validation, live viewing
EFFORT: 6-8 weeks + firmware
FRICTION: None (Bluetooth pairing is easy)


PHASE 4 (Months 10-12): Bidirectional Insights
═══════════════════════════════════════════════════════════════
 TAG App     ←── Insights ───     Facility
 ┌─────┐    ┌─────────────┐      ┌─────┐
 │ 📱  │<───│  🧠 AI      │<─────│ 💻  │
 └─────┘    │  Analytics  │      └─────┘
            └─────────────┘
         PitchTracker Pattern Detection

VALUE: Professional coaching insights in TAG app
EFFORT: 8-12 weeks
BENEFIT: TAG app becomes more valuable (not just data collection)
```

---

## Key Differentiators (Why This Beats MVP)

### Bluetooth PC Ingest (Phase 3) - The Big Unlock

**What It Enables:**

1. **Dual-Mode TAG Device**
   ```
   AT HOME:
   TAG Device --[Bluetooth]--> TAG Mobile App
   (Standard consumer experience)

   AT FACILITY:
   TAG Device --[Bluetooth]--> Facility PC (PitchTracker)
                    |
                    └──> Streams velocity in real-time
                    └──> Cross-validates with stereo cameras
                    └──> Parents watch live from TAG app
   ```

2. **Real-Time Cross-Validation**
   ```
   Pitch #18:
   ├─ TAG Device:       73.4 mph
   ├─ PitchTracker:     73.2 mph
   └─ Difference:        0.2 mph ✅ Agreement!

   Result: Both systems validated each other
   Trust: Athletes/parents see two independent measurements agree
   ```

3. **Live Facility Viewing (Parents at Home)**
   ```
   Parent's TAG App (live during facility session):
   ┌────────────────────────────────────┐
   │  📍 Live - Elite Baseball Academy │
   │  4:38 PM (23 minutes in)          │
   │                                    │
   │  Pitches: 18                       │
   │  Current Avg: 73.4 mph             │
   │  Latest: 74.1 mph - Strike! ⚾     │
   │                                    │
   │  [End Updates] [View 3D]           │
   └────────────────────────────────────┘
   ```

4. **One Device, Two Contexts**
   - Athletes don't need separate equipment
   - TAG device purchased for home ($230) works at facility too
   - Reduced friction, increased TAG device value

---

## Value Multiplication Table

| Integration Level | TAG User Value | Facility Value | TAG Sports Revenue | PitchTracker Revenue |
|-------------------|----------------|----------------|-------------------|---------------------|
| **None** (baseline) | Speed tracking at home | No TAG integration | $230 (device sale) | $0 (no TAG users) |
| **Phase 1** (manual) | Practice data transfers | See practice baseline | $230 + $50-100 referral | $1,200 (facility sale) |
| **Phase 2** (cloud) | Auto-sync, no friction | Real-time athlete updates | $230 + $100-150 referral | $1,200 + recurring fees |
| **Phase 3** (Bluetooth) | Dual-mode device, live viewing | Cross-validation, live TAG data | $230 + $150+ (higher LTV) | $1,200 + bundles + validation value |
| **Phase 4** (insights) | Professional AI coaching | Athlete retention | $230 + $200+ (app becomes coaching platform) | $1,200 + insight licensing |

**Key Insight:** Each phase multiplies value for all stakeholders. Phase 3 (Bluetooth) is the biggest unlock.

---

## Technical Differentiation

### What TAG Sports Gets (That Pocket Radar Can't)

**Pocket Radar (Competitor):**
- Speed measurement only
- No facility integration
- No data platform
- Standalone product

**TAG Sports (With PitchTracker Partnership):**
- ✅ Speed measurement (same as Pocket Radar)
- ✅ **Facility integration** (works at PitchTracker facilities via Bluetooth)
- ✅ **Cloud data platform** (practice + facility data unified)
- ✅ **Professional insights** (PitchTracker analysis flows to TAG app)
- ✅ **Live facility viewing** (parents watch sessions remotely)
- ✅ **Cross-validation** (TAG radar validates facility stereo cameras)
- ✅ **Ecosystem product** (not standalone, part of complete training platform)

**Competitive Positioning:**
> "TAG Sports: The only consumer radar that integrates with professional facility training. Your $230 device works at home AND at the academy."

---

## Architecture Advantages

### For TAG Sports Engineering Team

**Clean API Integration:**
- RESTful API (standard HTTP, JSON payloads)
- OAuth 2.0 authentication (industry standard)
- Webhook notifications (real-time updates)
- Versioned schemas (backward compatibility)
- Comprehensive documentation (Swagger/OpenAPI spec)

**Low Engineering Burden:**
- Phase 1: Simple JSON export (2 weeks)
- Phase 2: OAuth + HTTP calls (2 weeks, standard libraries)
- Phase 3: BLE firmware update (4-6 weeks, if TAG hardware team approves)
- Phase 4: Webhook listeners + UI updates (2-3 weeks)

**No Lock-In:**
- Open API (TAG Sports controls when to pull data)
- Standard protocols (OAuth, REST, WebSocket, BLE)
- Can disconnect cleanly if partnership ends (data export for all users)

---

### For PitchTracker Engineering Team

**Platform Value:**
- Cloud infrastructure enables future features (multi-facility, mobile app)
- API-first design (enables third-party integrations beyond TAG Sports)
- Data network effects (more TAG data → better insights → more facility value)

**Competitive Advantage:**
- Exclusive TAG integration (no Rapsodo/TrackMan partnership exists)
- "Works with TAG Sports" is unique market position
- Bluetooth PC ingest is technically novel (no competitor has this)

---

## User Stories (Concrete Examples)

### Story 1: Sarah (13-year-old travel ball pitcher)

**Without Integration:**
- Sarah uses TAG Sports at home: 3-4 practice sessions/week, tracking velocity
- Sarah visits Elite Baseball Academy: 1 session/week, PitchTracker cameras
- **Problem:** Coach has no context about Sarah's home practice. Data siloed.

**With Integration (Phase 2 - Cloud Sync):**
- Sarah's TAG practice data auto-syncs to cloud
- Elite Academy coach sees practice trends before Sarah arrives
- Coach: "Sarah, I see you've been working on your changeup at home (40 pitches this week, 65 mph avg). Let's focus on location today."
- **Result:** Better coaching, Sarah feels seen and understood

**With Integration (Phase 3 - Bluetooth):**
- Sarah brings TAG device to facility
- Device pairs with facility PC via Bluetooth
- During session: TAG measures velocity (73.4 mph), PitchTracker measures velocity (73.2 mph)
- **Result:** Cross-validation shows both systems agree (builds trust for parents and coach)
- Sarah's mom watches live from TAG app at work (sees each pitch: "74.1 mph - Strike!")

**With Integration (Phase 4 - Insights):**
- After facility session, PitchTracker generates insight: "Sarah's velocity up 1.3 mph/week. Continue current training regimen."
- Insight appears in TAG app (push notification)
- Sarah and parents see professional analysis in familiar TAG interface
- **Result:** TAG app becomes coaching platform, not just data collector

---

### Story 2: Elite Baseball Academy (30 athletes, 15 use TAG Sports)

**Without Integration:**
- Academy uses PitchTracker for facility sessions
- 15 athletes use TAG Sports at home (Academy unaware)
- **Problem:** Can't leverage athletes' home practice data

**With Integration (Phase 1 - Manual):**
- Coaches ask athletes: "If you use TAG Sports, export your data and email it to us"
- 5-8 athletes actually do it (friction)
- **Partial value:** Some practice context for some athletes

**With Integration (Phase 2 - Cloud):**
- All 15 TAG-using athletes link accounts (one-time OAuth)
- Practice data auto-syncs
- **Full value:** Coaches see all athletes' practice trends automatically

**With Integration (Phase 3 - Bluetooth):**
- Academy markets: "Bring your TAG Sports device to sessions!"
- 10 athletes bring TAG devices, pair with facility PC
- **Academy pitch:** "We're the only facility where your TAG device works during sessions. Two measurements for every pitch."
- **Result:** Attracts TAG users from competing facilities (competitive differentiation)

**With Integration (Phase 4 - Insights):**
- Academy coaches add coaching notes after sessions
- Notes appear in athletes' TAG apps (push notifications)
- Parents receive weekly progress summaries via TAG app
- **Result:** Enhanced communication, improved parent satisfaction, higher retention

---

## Economics (Detailed)

### TAG Sports Revenue Impact

**Current (No Partnership):**
- Device sale: $230 (one-time)
- Lifetime value: $230

**With Partnership (All Phases):**
- Device sale: $230 (one-time)
- Referral fee (athlete joins facility): $90-135 (10-15% of $900 annual)
- Increased retention (integrated users stay longer): +$50 LTV
- Facility bundle sales (academy buys 10× devices): $2,300 hardware revenue
- **Lifetime value: $370-715 (61-210% increase)**

**Scale (1,000 TAG users join facilities):**
- Referral revenue: $90,000-135,000/year (recurring)
- Bundle revenue: $46,000 (20 bundles × $2,300)
- **Total new revenue: $136,000-181,000/year**

**At 10% market penetration (10,000 TAG users → 1,000 join facilities):**
- **$136K-181K annual partnership revenue**
- **Pays for TAG engineering investment in 6-12 months**

---

### PitchTracker Revenue Impact

**Current (Solo GTM):**
- Facility sales: 5-10 facilities/year @ $1,200 = $6,000-12,000

**With Partnership:**
- Direct facility sales: 5-10 @ $1,200 = $6,000-12,000
- TAG-driven facility sales: 15-20 @ $1,200 = $18,000-24,000 (facilities want TAG users)
- Facility subscriptions: 100-200 athletes @ $900/year = $90,000-180,000 (PitchTracker keeps 85-90%)
- Hardware bundles: 5-10 @ $700 = $3,500-7,000
- **Total Year 1: $117,500-223,000** (vs. $6K-12K solo)

**10-20× revenue increase with partnership**

---

## Partnership Proposal (3-Tier Options)

### Option A: MVP Only (Low Commitment)
**Scope:** Phase 1 only (manual export/import)
**Investment:** 2-4 weeks engineering (both sides)
**Revenue:** Referral fees only (10-15%)
**Exclusivity:** None (test partnership without commitment)
**Duration:** 90-day pilot
**Outcome:** If successful, proceed to Option B or C

---

### Option B: Cloud Platform (Medium Commitment)
**Scope:** Phase 1-2 (manual + cloud sync)
**Investment:** 10-16 weeks engineering + $100-300/month cloud
**Revenue:** Referral fees (10-15%) + hardware bundles
**Exclusivity:** 1-year (TAG is exclusive consumer radar partner)
**Duration:** 1-year partnership
**Outcome:** Proven partnership model, proceed to Phase 3-4 if successful

---

### Option C: Full Platform (Deep Commitment) - **RECOMMENDED**
**Scope:** Phase 1-4 (manual → cloud → Bluetooth → insights)
**Investment:** 30-48 weeks engineering + cloud infrastructure
**Revenue:** Referral fees (10-15%) + bundles + data licensing (future)
**Exclusivity:** 2-year (renewable)
**Duration:** 2-year partnership
**Outcome:** Tight ecosystem integration, maximum network effects

**Recommendation:** Start with Option A (pilot), graduate to Option C if successful.

---

## Risk Assessment

### Technical Risks

**Risk: Bluetooth Reliability**
- **Concern:** BLE connections sometimes unstable (range, interference)
- **Mitigation:** Fallback to mobile app if PC connection fails; redundant measurement (cameras are primary)
- **Test:** Pilot in 5-10 facilities before public rollout

**Risk: Cloud Infrastructure Costs**
- **Concern:** Costs scale with users (could become expensive)
- **Mitigation:** Optimize early (caching, compression); charge facilities for high-volume users if needed
- **Breakeven:** 50-100 facilities cover infrastructure costs

**Risk: TAG Firmware Changes**
- **Concern:** Bluetooth PC mode requires firmware update (TAG hardware team effort)
- **Mitigation:** Start with Phase 1-2 (no firmware needed); prove value before requesting firmware work
- **Alternative:** If firmware not feasible, stay with cloud sync (still valuable)

### Business Risks

**Risk: TAG Sports Declines Deep Integration**
- **Likelihood:** Low-Medium (depends on TAG's engineering capacity)
- **Mitigation:** Offer phased approach (start simple, build trust, then deeper integration)
- **Fallback:** Phase 1-2 only (still valuable, just less differentiated)

**Risk: Integration Doesn't Drive Adoption**
- **Likelihood:** Low (TAG users are already tracking-literate, facilities want their data)
- **Mitigation:** Pilot with 5-10 facilities before scaling; athlete incentives ($50 credit)
- **Validation:** If <20% of TAG-using athletes adopt integration in pilot, reassess

**Risk: Privacy/Legal Issues**
- **Likelihood:** Low (standard data sharing with consent)
- **Mitigation:** Legal review ($2K-5K); COPPA compliance; clear consent flows
- **Requirement:** Parental consent for athletes <13

---

## Competitive Response Scenarios

### If Rapsodo Approaches TAG Sports

**Rapsodo Offer:** "Integrate with us too"
**TAG Sports Concern:** "Why be exclusive with PitchTracker?"

**PitchTracker Counter:**
1. **First-mover advantage:** We built integration first, proven in market
2. **Deeper integration:** Bluetooth PC ingest (not just data export)
3. **Better economics:** $1,200 PitchTracker vs. $3,000 Rapsodo (facilities can afford more installations → more TAG referrals)
4. **Network effects:** More facilities already using PitchTracker + TAG (switching costs)
5. **Exclusivity value:** Being the ONLY consumer radar with facility integration is stronger brand position

**Recommendation:** Lock in 2-year exclusivity NOW before Rapsodo catches on.

---

### If Pocket Radar Tries to Compete

**Pocket Radar Action:** Builds facility integration to match TAG Sports

**PitchTracker Response:**
1. **Already integrated:** TAG partnership established (first-mover)
2. **Deeper integration:** Our Bluetooth + cloud platform vs. their basic export
3. **Better brand:** TAG Sports has stronger consumer brand than Pocket Radar
4. **Larger user base:** TAG's 10K users vs. Pocket Radar's smaller base

**Outcome:** TAG partnership insulates us from Pocket Radar threat.

---

## Success Metrics (Phase-Specific)

### Phase 1 Success (Manual Export/Import)
- [ ] 50+ athletes export TAG data and import to facilities
- [ ] 5+ facilities report integration as valuable
- [ ] <5% error rate (exports import successfully)
- [ ] NPS ≥8 from integrated athletes
- **If successful → Proceed to Phase 2**

### Phase 2 Success (Cloud Sync)
- [ ] 100+ athletes with linked accounts (TAG + PitchTracker)
- [ ] 80%+ auto-sync success rate (data flows without athlete action)
- [ ] 10+ facilities using athlete cloud data actively
- [ ] $1,000+ referral revenue to TAG Sports (proof of model)
- **If successful → Proceed to Phase 3**

### Phase 3 Success (Bluetooth PC Ingest)
- [ ] 20+ facilities with Bluetooth integration enabled
- [ ] 50+ athletes bring TAG devices to facilities
- [ ] 95%+ Bluetooth connection success rate
- [ ] <0.5 mph average difference (TAG vs. PitchTracker cross-validation)
- [ ] 10+ parents report watching live sessions from TAG app
- **If successful → Proceed to Phase 4**

### Phase 4 Success (Bidirectional Insights)
- [ ] 50+ facilities receiving PitchTracker insights
- [ ] 500+ athletes see coaching insights in TAG app
- [ ] 100+ parents receive weekly progress summaries
- [ ] 20%+ increase in TAG app engagement (insights drive opens)
- [ ] $50,000+ referral revenue (mature partnership)
- **If successful → Consider Phase 5 (unified mobile app)**

---

## Partnership Pitch (30-Second Version for TAG Sports)

> "Your 10,000 users track pitches at home with TAG Sports. We want to make their devices work at professional facilities too.
>
> **Deep integration:** Athletes bring TAG devices to PitchTracker facilities. Devices connect via Bluetooth to facility PCs. Real-time velocity streaming. Cross-validation with our stereo cameras. Parents watch live from your app.
>
> **Your benefit:** Dual-mode TAG device (home AND facility). Higher lifetime value. Referral revenue ($90K-135K/year). Competitive moat vs. Pocket Radar.
>
> **Our benefit:** Qualified leads. Brand awareness. Unique positioning.
>
> **Everyone wins:** Athletes get data continuity. Facilities get TAG users. You earn referrals. We grow together.
>
> Start with simple export/import (2 weeks). If successful, build cloud sync (3 months). Then Bluetooth integration (3 months). Then bidirectional insights (3 months).
>
> Low risk. High upside. Interested?"

---

## Appendix: API Quick Reference

### Core Endpoints (Most Important)

```http
# Authentication
POST /auth/oauth/token
  → Get access token for API calls

# Link Athlete Accounts
POST /athletes
  Body: { tag_user_id, name, email, consent }
  → Create unified profile

# Upload Session (TAG Sports → Cloud)
POST /sessions
  Body: { athlete_id, date, pitches[], summary }
  → Store practice session

# Get Athlete Data (PitchTracker ← Cloud)
GET /athletes/{athlete_id}/sessions?start_date=YYYY-MM-DD
  → Retrieve practice + facility sessions

# Get Insights (TAG Sports ← Cloud)
GET /athletes/{athlete_id}/insights
  → Retrieve AI coaching insights

# Subscribe to Events (TAG Sports)
POST /webhooks/subscribe
  Body: { url, events: ["session.completed", "insight.generated"] }
  → Receive real-time notifications
```

---

**Document Status:** COMPLETE - Visual communication guide for partnership
**Owner:** Product + Engineering
**Use Case:** Include in TAG Sports partnership outreach
**Created:** March 26, 2026
