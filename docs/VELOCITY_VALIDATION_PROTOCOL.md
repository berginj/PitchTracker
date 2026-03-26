# Velocity Validation Test Protocol

**Document Type:** Validation Methodology & Test Plan
**Date:** March 26, 2026
**Version:** 1.0
**Applies To:** PitchTracker v1.5.0-pilot
**Owner:** Engineering + QA

---

## Executive Summary

This document defines the validation protocol for PitchTracker velocity measurements. The goal is to establish **objective error bounds** (±X mph) and **operating envelope** (distance range, speed range, conditions) by comparing PitchTracker readings to trusted reference equipment.

**Target Outcome:** Published validation report stating:
- "PitchTracker measures velocity within ±X mph of reference equipment"
- "Under conditions: Y-Z feet from mound, A-B mph speed range, proper lighting"
- "Based on N pitches across M sessions"

---

## Validation Objectives

### Primary Objectives
1. **Measure velocity accuracy** - Determine error bounds (±X mph) vs. reference
2. **Define operating envelope** - Document known-good conditions for reliable measurements
3. **Establish trust** - Provide external proof that PitchTracker works as claimed

### Secondary Objectives
4. **Identify failure modes** - Document conditions where accuracy degrades
5. **Compare detection rates** - PitchTracker capture % vs. reference equipment
6. **Validate consistency** - Measure variance across multiple sessions
7. **Benchmark competitors** - Compare accuracy to known systems (Rapsodo, TrackMan)

---

## Reference Equipment Options

### Option 1: Pocket Radar (Recommended for Initial Testing)
**Cost:** $300-400
**Pros:**
- Affordable, widely available
- Trusted by coaches and scouts
- Sufficient accuracy (±1 mph) for initial validation
- Portable, easy to setup

**Cons:**
- Less precise than TrackMan/Rapsodo
- Measures peak velocity, not release velocity
- Single-point measurement (no trajectory data)

**Recommendation:** Use for initial validation to establish baseline accuracy

### Option 2: Stalker Radar Gun
**Cost:** $800-1200
**Pros:**
- Professional-grade accuracy (±0.5 mph)
- Used by MLB scouts
- Durable and reliable

**Cons:**
- Higher cost
- Still single-point measurement

**Recommendation:** Use if budget allows for higher confidence

### Option 3: Rapsodo (Ideal but Expensive)
**Cost:** $3,000-4,000
**Pros:**
- Industry-standard for facilities
- Measures release velocity, spin, break
- Can compare trajectory data, not just velocity
- High accuracy (±0.5 mph)

**Cons:**
- Expensive
- May require facility partnership for access

**Recommendation:** Partner with facility that owns Rapsodo for comprehensive validation

### Option 4: TrackMan (Gold Standard but Rare)
**Cost:** $18,000+
**Pros:**
- MLB-grade accuracy
- Comprehensive trajectory data
- Industry gold standard

**Cons:**
- Prohibitively expensive
- Rare availability

**Recommendation:** Only if facility partnership provides access

---

## Test Methodology

### Test Setup

**Equipment Required:**
- PitchTracker system (dual cameras, calibrated)
- Reference device (Pocket Radar, Stalker, or Rapsodo)
- Baseball pitcher (consistent throwing ability)
- Baseballs (consistent type throughout test)
- Measuring tape (verify distances)
- Lighting measurement tool (lux meter)
- Stopwatch or frame counter

**Setup Configuration:**
```
[Pitcher]  ------ 60.5 ft ------ [Home Plate]
              (Mound)
    |                                  |
    v                                  v
[Reference Device]              [PitchTracker Cameras]
   (behind mound)                  (behind plate)
```

**Reference Device Positioning:**
- Pocket Radar: 10-15 feet behind mound, aimed at release point
- Rapsodo: 6-8 feet behind plate, per manufacturer specs
- TrackMan: Per manufacturer specs (typically behind mound)

**PitchTracker Camera Positioning:**
- Behind home plate, per standard setup guide
- Cameras calibrated with ChArUco board
- ROI configured for lane and plate
- Strike zone calibrated for pitcher height

### Test Conditions

**Required Environmental Conditions:**
- **Lighting:** Minimum 500 lux (indoor facility lighting or outdoor daylight)
- **Distance:** Mound to plate = 60.5 ft (MLB regulation) or 54 ft (high school)
- **Temperature:** 60-85°F (avoid extreme temperatures affecting ball behavior)
- **Background:** Controlled background for detection (avoid busy/bright backgrounds)

**Controlled Variables:**
- Same pitcher throughout session (consistency)
- Same ball type (consistency)
- Same lighting conditions (time of day if outdoor)
- Calibration verified before each session

### Test Protocol

**Sample Size:**
- Minimum 100 pitches per pitcher
- Minimum 3 pitchers (different velocity profiles)
- Minimum 2 sessions per pitcher (different days)
- Target: 300+ total pitch comparisons

**Pitcher Profiles:**
- **Low velocity:** 55-65 mph (youth/changeup specialist)
- **Medium velocity:** 70-80 mph (average high school)
- **High velocity:** 85+ mph (college/advanced)

**Procedure:**
1. **Pre-Session Setup (15 minutes)**
   - Set up reference device per manufacturer specs
   - Verify PitchTracker calibration (ChArUco board check)
   - Measure distances with tape
   - Measure lighting conditions
   - Document environmental conditions

2. **Warmup Period (10 pitches)**
   - Pitcher warms up
   - Verify both systems detecting pitches
   - Do not include in dataset

3. **Data Collection (100 pitches per session)**
   - Pitcher throws at game-like intensity
   - Capture velocity from both systems for every pitch
   - Log any detection failures (PitchTracker missed, reference missed)
   - Note any environmental changes during session

4. **Post-Session Verification**
   - Export PitchTracker session data
   - Compare velocity readings pitch-by-pitch
   - Document any anomalies

### Data Collection Template

For each pitch, record:
- **Pitch Number:** 1-100
- **Reference Velocity:** (mph from Pocket Radar/Rapsodo)
- **PitchTracker Velocity:** (mph from session export)
- **Detection Status:** (Both detected / PitchTracker missed / Reference missed)
- **Notes:** (Any anomalies, environmental changes)

**Example CSV:**
```csv
pitch_num,reference_mph,pitchtracker_mph,detection_status,notes
1,72.3,71.8,both_detected,
2,74.1,73.9,both_detected,
3,71.5,null,pt_missed,ball hit net early
4,73.8,74.2,both_detected,
...
```

---

## Analysis Methodology

### Velocity Accuracy Analysis

**Metrics to Calculate:**
1. **Mean Absolute Error (MAE):** Average of |reference - pitchtracker| across all pitches
2. **Root Mean Square Error (RMSE):** sqrt(mean((reference - pitchtracker)^2))
3. **Bias:** Mean of (pitchtracker - reference) - measures systematic over/under-reading
4. **Correlation:** Pearson correlation coefficient
5. **Error Bounds:** ±X mph that captures 95% of measurements

**Acceptance Criteria:**
- MAE < 2.0 mph → Acceptable for pilot
- MAE < 1.5 mph → Good accuracy
- MAE < 1.0 mph → Excellent accuracy (comparable to prosumer devices)
- Correlation > 0.95 → Strong linear relationship

### Detection Rate Analysis

**Metrics:**
- **PitchTracker Detection Rate:** % of pitches detected by PitchTracker when reference detected
- **False Positive Rate:** % of pitches detected by PitchTracker but not reference
- **Capture Latency:** Time delay between pitch and PitchTracker detection

**Acceptance Criteria:**
- Detection Rate > 90% → Acceptable
- Detection Rate > 95% → Good
- False Positive Rate < 5% → Acceptable

### Breakdown Analysis

**By Velocity Range:**
- Low (55-65 mph): MAE, bias, detection rate
- Medium (65-75 mph): MAE, bias, detection rate
- High (75-85 mph): MAE, bias, detection rate
- Very High (85+ mph): MAE, bias, detection rate

**By Environmental Conditions:**
- Indoor vs. outdoor
- Different lighting levels
- Different backgrounds

**By Session:**
- Session-to-session consistency
- Time of day effects

---

## Operating Envelope Definition

Based on validation results, define:

### Known-Good Conditions (Green Zone)
"PitchTracker is validated to operate with X mph accuracy under these conditions:"
- Camera distance from plate: Y-Z feet
- Lighting: Minimum A lux
- Background: Controlled (no bright/busy backgrounds behind batter)
- Ball speed: B-C mph
- Ball type: Standard baseball (5 oz, 9" circumference)
- Mound distance: 54-60.5 feet

### Acceptable Conditions (Yellow Zone)
"PitchTracker may work but accuracy degrades:"
- Lower lighting (< A lux)
- Varying backgrounds
- Edge cases (very slow/very fast pitches)

### Unsupported Conditions (Red Zone)
"PitchTracker is not validated for:"
- Extreme low light (< X lux)
- Non-standard balls (softballs, tennis balls)
- Distances outside validated range
- Moving camera setups

---

## Validation Report Template

### Report Structure

**Executive Summary**
- Key findings (MAE, detection rate, operating envelope)
- One-sentence accuracy claim

**Methodology**
- Reference equipment used
- Sample size (N pitches, M pitchers, X sessions)
- Test conditions

**Results**
- Velocity accuracy (MAE, RMSE, bias, error bounds)
- Detection rate
- Breakdown by velocity range
- Session-to-session consistency
- Comparison charts (scatter plot, Bland-Altman plot)

**Operating Envelope**
- Known-good conditions
- Limitations
- Failure modes

**Conclusion**
- Summary of accuracy claim
- Recommended use cases
- Next steps

**Appendices**
- Raw data (CSV)
- Statistical methodology
- Equipment specifications
- Photos of test setup

### Publication Plan

**Internal (Immediately):**
- Share with engineering team
- Update pilot partner materials
- Inform capability contract decisions

**External (After Review):**
- Publish to GitHub repository (docs/VALIDATION_REPORT.md)
- Update README.md with accuracy claim
- Include in pilot onboarding materials
- Reference in marketing/sales materials

---

## Risk Assessment

### High Risks
1. **No access to reference equipment**
   - **Mitigation:** Partner with facility that owns Rapsodo/Stalker
   - **Alternative:** Purchase Pocket Radar ($300-400)

2. **Accuracy worse than acceptable (MAE > 3 mph)**
   - **Mitigation:** Diagnose failure modes, improve detection/tracking
   - **Alternative:** Document limitations, narrow operating envelope

3. **Detection rate too low (< 80%)**
   - **Mitigation:** Improve detection parameters, lighting requirements
   - **Alternative:** Document known failure cases, provide workarounds

### Medium Risks
4. **Inconsistent results across sessions**
   - **Mitigation:** Standardize setup procedure, calibration verification
   - **Root cause:** Investigate calibration drift, environmental factors

5. **Velocity range-dependent accuracy**
   - **Mitigation:** Document operating envelope by speed range
   - **Communication:** Be transparent about validated ranges

### Low Risks
6. **Pitcher fatigue affecting results**
   - **Mitigation:** Limit session length, multiple sessions
   - **Note:** Natural variation, not a PitchTracker issue

---

## Timeline and Resources

### Phase 1: Equipment Acquisition (Week 1)
- **Action:** Purchase Pocket Radar or arrange Rapsodo facility partnership
- **Cost:** $300-400 (Pocket Radar) or $0 (partnership)
- **Owner:** Founder

### Phase 2: Test Execution (Weeks 2-3)
- **Action:** Conduct 6+ validation sessions (3 pitchers × 2 sessions)
- **Time:** 2 hours per session (setup + 100 pitches + export)
- **Owner:** Engineering + QA

### Phase 3: Analysis (Week 4)
- **Action:** Statistical analysis, report writing
- **Time:** 20-30 hours
- **Owner:** Engineering

### Phase 4: Publication (Week 5)
- **Action:** Review, publish, update materials
- **Time:** 5-10 hours
- **Owner:** Product + Engineering

**Total Timeline:** 5 weeks
**Total Cost:** $300-400 (if purchasing Pocket Radar)

---

## Success Criteria

### Validation Complete When:
- [ ] 300+ pitches captured with both systems
- [ ] 3+ pitchers tested (different velocity profiles)
- [ ] MAE and error bounds calculated
- [ ] Operating envelope defined
- [ ] Validation report written and reviewed
- [ ] Published to documentation

### Validation Successful When:
- [ ] MAE < 2.0 mph (acceptable) or < 1.5 mph (good)
- [ ] Detection rate > 90%
- [ ] Operating envelope clearly defined
- [ ] Failure modes documented
- [ ] Results reproducible across sessions

---

## Next Steps After Validation

1. **Update Marketing Claims**
   - README.md: "Velocity accurate to ±X mph"
   - Pilot materials: Reference validation report

2. **Inform Pilot Partners**
   - Share validation results
   - Set expectations based on operating envelope
   - Provide troubleshooting guide for edge cases

3. **Continuous Improvement**
   - Use validation data to improve detection algorithms
   - Expand validation to location accuracy (future)
   - Re-validate after significant algorithm changes

4. **Competitive Positioning**
   - Compare accuracy to known competitors (if data available)
   - Highlight transparency in validation methodology

---

**Document Status:** READY FOR EXECUTION
**Owner:** Engineering Lead
**Approver:** Founder
**Next Action:** Acquire reference equipment (Pocket Radar or facility partnership)
