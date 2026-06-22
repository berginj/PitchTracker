# TAG Sports Device Integration - Accelerated Plan with Physical Device

**Date:** March 26, 2026
**Status:** Partnership planning concept pending TAG feedback; validation examples are illustrative until reference testing is complete
**Impact:** Can build working integration + validate accuracy + create demo BEFORE TAG Sports outreach
**Timeline:** 1-2 weeks to working demo

---

## Strategic Advantage: You Have the Hardware

**This transforms the partnership approach from:**
- ❌ "We have specifications, let's partner" (theoretical)

**To:**
- ✅ "We've built a working integration with your device, here's the demo" (proven)

**Benefits:**
1. **Stronger negotiating position** - You've de-risked the integration (it works)
2. **Faster partnership discussions** - Show working demo, not just specs
3. **Validation completed** - TAG device becomes your reference equipment for velocity accuracy
4. **UX compliance gaps closed** - Addresses critical validation requirement from compliance review

---

## Phase 1: Reverse-Engineer TAG Device Data (Days 1-2)

### Step 1: Explore TAG Sports Mobile App

**Goal:** Understand how TAG Sports stores and exports data

**Actions:**

**A. Check for Export Feature (Existing)**
1. Open TAG Sports app on your phone
2. Navigate to Profile / Settings / Sessions
3. Look for: "Export", "Share", "Download", or similar
4. **If export exists:**
   - Export a test session
   - Examine the file format (likely JSON, CSV, or custom format)
   - Document the schema
5. **If no export:**
   - We'll need to work with app's internal data (see Step B)

**B. Analyze App Data Storage (If No Export)**
1. **iOS (if applicable):**
   - Connect iPhone to Mac
   - Use iMazezing or similar tool to browse app sandbox
   - Look for: `Documents/`, `Library/`, database files (.sqlite, .realm, .json)

2. **Android (if applicable):**
   - Enable USB debugging
   - Use `adb` to pull app data: `adb pull /data/data/com.tagsports.app/`
   - Examine databases or JSON files

3. **Bluetooth Data Sniffing (Advanced):**
   - Use Bluetooth packet sniffer (Wireshark with Bluetooth adapter, or Nordic nRF Connect app)
   - Capture data while TAG device is actively measuring
   - Analyze BLE characteristics and data format

**C. Document TAG Data Format**

Create: `TAG_SPORTS_DATA_FORMAT_ANALYSIS.md`

**Template:**
```markdown
# TAG Sports Data Format Analysis

**Device:** TAG One [Model/Version]
**App:** TAG Sports [iOS/Android Version]
**Analysis Date:** March 26, 2026

## Export Format (if available)

**File Type:** JSON / CSV / XML / Other
**File Name Pattern:** [Describe]
**Sample Export:** [Paste sample data]

## Data Schema

### Session Level:
- session_id: [Type, example]
- date: [Format]
- location: [Type]
- total_pitches: [Type]
- avg_speed_mph: [Type]
- [Other fields...]

### Pitch Level:
- pitch_number: [Type]
- timestamp: [Format]
- speed_mph: [Type]
- [Other fields...]

## Gaps vs. Our Spec

- ✅ Fields that match our JSON schema
- ⚠️ Fields that differ (mapping required)
- ❌ Fields we expected but don't exist
```

**Deliverable:** Understanding of actual TAG data format (may differ from our spec)

**Time:** 3-4 hours

---

### Step 2: Create Test Dataset from Your TAG Device

**Goal:** Capture real TAG Sports data for integration testing

**Actions:**

1. **Run Practice Session with TAG Device**
   - Throw 20-30 pitches (or have someone throw)
   - TAG device measures each pitch
   - TAG app records session

2. **Export Session Data**
   - Use app's export feature (if exists)
   - OR: Extract from app data storage
   - Save as: `test_data/TAG_export_real_session_001.json` (or appropriate format)

3. **Create Multiple Test Cases**
   - Session with 10 pitches (small dataset)
   - Session with 50+ pitches (normal dataset)
   - Session with 100+ pitches (large dataset)
   - Session with varied velocities (40-80 mph range)

**Deliverable:** 3-5 real TAG Sports export files for testing

**Time:** 1-2 hours (includes practice session)

---

## Phase 2: Build TAG Sports Import Integration (Days 3-7)

### Step 3: Adapt Import Service to Real TAG Format

**Current State:**
- `app/services/tag_sports_integration.py` exists (assumes our spec)
- Needs adaptation to **actual TAG format** (from Step 1)

**Actions:**

1. **Update JSON Schema Parsing**
   - Modify `_parse_sessions()` to match real TAG format
   - Modify `_parse_athlete_data()` if fields differ
   - Add format detection (support both TAG's format AND our proposed spec)

2. **Add Format Converter (If TAG Format Differs)**
```python
def _convert_tag_native_to_standard(self, tag_data: dict) -> dict:
    """Convert TAG Sports native format to PitchTracker standard format.

    Args:
        tag_data: Data in TAG's actual format

    Returns:
        Data in PitchTracker standard format (matching our spec)
    """
    # Map TAG's fields → Our standard fields
    converted = {
        "schema_version": "1.0",
        "athlete": {
            "tag_user_id": tag_data.get("user_id") or tag_data.get("athlete_id"),
            "name": tag_data.get("name") or tag_data.get("athlete_name"),
            # Map other fields...
        },
        "sessions": [
            # Convert each TAG session to our format
        ]
    }
    return converted
```

3. **Test with Real TAG Data**
```python
# Test import with your real TAG export
service = TagSportsIntegrationService()
result = service.import_from_file(Path("test_data/TAG_export_real_session_001.json"))

assert result.success == True
assert result.sessions_imported > 0
print(f"✅ Imported {result.pitches_imported} real TAG pitches")
```

**Deliverable:** Import service that works with REAL TAG Sports data

**Time:** 1-2 days (depending on format differences)

---

### Step 4: Build Import UI Dialog

**Goal:** Create functional import dialog for TAG Sports data

**File:** `ui/coaching/dialogs/import_tag_data_dialog.py`

**Implementation Priority (2-3 days):**

**Day 1: Basic Dialog**
```python
class ImportTagDataDialog(QtWidgets.QDialog):
    """Dialog for importing TAG Sports practice data."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Import TAG Sports Practice Data")
        self.resize(600, 400)

        # Build UI:
        # - File browser button
        # - File path display
        # - Preview area (show athlete name, session count, pitch count)
        # - Import button (disabled until valid file selected)
        # - Cancel button

    def _browse_file(self):
        """Open file dialog to select TAG Sports export."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select TAG Sports Export",
            str(Path.home() / "Downloads"),
            "All Files (*.*);;JSON Files (*.json);;CSV Files (*.csv)"
        )
        # Parse file, show preview

    def _preview_file(self):
        """Preview TAG data before import."""
        # Use TagSportsIntegrationService to parse
        # Display: Athlete name, sessions, pitches, date range, avg velocity

    def _import_data(self):
        """Actually import the TAG data."""
        # Merge with pitcher profile
        # Show success message
        # Emit signal that import completed
```

**Day 2-3: Integration with Session Start**
- Add "Import TAG Sports Data" button to Session Start Dialog
- Wire button to open ImportTagDataDialog
- Handle import result (update pitcher profile, refresh UI)

**Testing:**
1. Test with your real TAG export files
2. Test error cases (invalid file, missing fields)
3. Test success flow (import → see data in profile)

**Deliverable:** Working import dialog tested with real TAG data

**Time:** 2-3 days

---

### Step 5: Build Practice History Display

**Goal:** Show imported TAG data in PitchTracker UI

**Implementation (1-2 days):**

**Option A: Add Tab to Existing Pitcher Profile View**
- Extend pitcher profile dialog/window
- Add "Practice History (TAG Sports)" tab
- Display sessions in list/table
- Show summary statistics

**Option B: Add Panel to Coach Dashboard**
- Small panel showing TAG practice activity
- "Last session: Mar 25 (2 days ago)"
- "Recent avg: 71.4 mph (↗ trending up)"
- Click to view full history

**Quick Implementation:**
```python
class TagPracticeHistoryWidget(QtWidgets.QWidget):
    """Display TAG Sports practice history."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self._build_ui()

    def _build_ui(self):
        layout = QtWidgets.QVBoxLayout(self)

        # Header
        header = QtWidgets.QLabel("🏠 Practice History (TAG Sports)")
        layout.addWidget(header)

        # Summary stats
        self._summary_label = QtWidgets.QLabel()
        layout.addWidget(self._summary_label)

        # Session list
        self._session_list = QtWidgets.QListWidget()
        layout.addWidget(self._session_list)

    def load_tag_sessions(self, tag_sessions):
        """Load TAG Sports sessions into widget."""
        # Display each session with date, location, pitch count, avg velocity
        for session in tag_sessions:
            item_text = f"{session.date.strftime('%b %d, %Y')} - {session.location} ({session.total_pitches} pitches)\nAvg: {session.avg_speed_mph:.1f} mph | Max: {session.max_speed_mph:.1f} mph"
            self._session_list.addItem(item_text)
```

**Deliverable:** Visual display of TAG practice data in PitchTracker UI

**Time:** 1-2 days

---

## Phase 3: Velocity Validation with TAG Device (Days 8-10)

### Step 6: Run Cross-Validation Tests

**Goal:** Use TAG device as reference to validate PitchTracker velocity accuracy

**This solves TWO problems:**
1. ✅ Addresses critical UX compliance gap (validation required)
2. ✅ Proves TAG integration value (cross-validation feature)

**Test Protocol:**

**Setup:**
```
[Pitcher]  ------ 60.5 ft ------ [Home Plate]
              (Mound)
    |                                  |
    v                                  v
[TAG Sports Device]            [PitchTracker Cameras]
   (positioned to                  (behind plate,
    measure velocity)                dual stereo)
```

**Procedure:**
1. **Session 1: Baseline (30 pitches)**
   - Position TAG device per manufacturer specs
   - Set up PitchTracker (cameras calibrated)
   - Pitcher throws 30 pitches
   - **Record both:**
     - TAG Sports app: Velocity for each pitch
     - PitchTracker: Velocity from stereo tracking

2. **Session 2: Varied Speeds (30 pitches)**
   - Mix of slow (55-65 mph), medium (65-75 mph), fast (75-85 mph)
   - Record both systems

3. **Session 3: Extended Test (50 pitches)**
   - Normal session intensity
   - Record both systems

**Data Collection:**

Create spreadsheet: `validation_data/tag_vs_pitchtracker_validation.csv`

```csv
pitch_num,tag_device_mph,pitchtracker_mph,difference_mph,percent_error
1,72.3,71.8,0.5,0.69%
2,74.1,73.9,0.2,0.27%
3,71.5,72.1,-0.6,0.84%
...
```

**Analysis (Use Python script):**
```python
import pandas as pd
import numpy as np

# Load data
df = pd.read_csv("validation_data/tag_vs_pitchtracker_validation.csv")

# Calculate metrics
mae = np.mean(np.abs(df['difference_mph']))
rmse = np.sqrt(np.mean(df['difference_mph']**2))
bias = np.mean(df['difference_mph'])  # Systematic over/under
correlation = df['tag_device_mph'].corr(df['pitchtracker_mph'])

print(f"Mean Absolute Error: {mae:.2f} mph")
print(f"RMSE: {rmse:.2f} mph")
print(f"Bias: {bias:.2f} mph")
print(f"Correlation: {correlation:.3f}")

# 95% confidence interval
std = np.std(df['difference_mph'])
ci_95 = 1.96 * std
print(f"95% CI: ±{ci_95:.2f} mph")
```

**Deliverable:** Validation report showing PitchTracker accuracy vs. TAG Sports device

**Target:** MAE <1.5 mph (excellent), <2.0 mph (acceptable)

**Time:** 2-3 days (includes 3 test sessions + analysis)

---

### Step 7: Publish Validation Report

**Create:** `docs/VELOCITY_VALIDATION_REPORT_TAG_DEVICE.md`

**Contents:**
```markdown
# PitchTracker Velocity Validation Report

**Validation Date:** March 26-28, 2026
**Reference Equipment:** TAG Sports TAG One (Model: [Your model])
**Test Protocol:** VELOCITY_VALIDATION_PROTOCOL.md
**Total Pitches:** 110

## Executive Summary

PitchTracker velocity measurements were validated against TAG Sports TAG One
portable radar gun across 110 pitches.

**Results:**
- Mean Absolute Error (MAE): [X.XX] mph
- 95% Confidence Interval: ±[X.XX] mph
- Correlation: [0.9XX]
- Bias: [+/-X.XX] mph (systematic over/under-reading)

**Conclusion:** PitchTracker velocity measurements are within ±[X] mph of TAG Sports
device across the tested range (55-85 mph).

## Methodology

[Describe setup, positioning, test protocol]

## Results

[Include scatter plot, Bland-Altman plot, error distribution]

## Operating Envelope

Validated conditions:
- Pitch speed range: 55-85 mph
- Distance: 60.5 feet (MLB regulation)
- Lighting: Indoor facility (estimated 800-1000 lux)
- Ball type: Standard baseball (5 oz, 9" circumference)
- Camera resolution: 1280×720 @ 30 FPS

## Known Limitations

- Validation limited to 110 pitches (single pitcher)
- TAG Sports device accuracy: ±1-2 mph (per manufacturer, unverified)
- Both systems may have similar systematic errors
- Future validation against professional systems (Rapsodo, TrackMan) recommended

## Appendix

[Raw data CSV, analysis code]
```

**Why This is Powerful:**
1. ✅ Addresses critical UX compliance gap (validation required)
2. ✅ Shows TAG Sports that integration is real (used their device)
3. ✅ Demonstrates cross-validation feature (TAG + PitchTracker working together)
4. ✅ Publishable (can add to README.md, pilot materials)

**Time:** 1 day (write report after analysis)

---

## Phase 4: Build Working Demo for TAG Sports (Days 11-14)

### Step 8: Create Demo Video / Live Demo

**Goal:** Show TAG Sports leadership a working integration

**Demo Flow (5-7 minutes):**

**Part 1: TAG Device Data Export (1 minute)**
- Show TAG Sports app on phone
- Navigate to session history
- "Here's my practice session from yesterday: 45 pitches, 71.2 mph avg"
- Export data (if feature exists) OR show data file you extracted
- "TAG Sports records my practice data. Now watch what happens at the facility..."

**Part 2: PitchTracker Import (1 minute)**
- Show PitchTracker on PC
- Click "Import TAG Sports Data" button
- Select your real TAG export file
- Preview shows: "John Doe, 3 sessions, 145 pitches, 71.4 mph avg"
- Click "Import"
- Success message: "✅ Imported TAG Sports data"

**Part 3: Practice History Display (1 minute)**
- Navigate to Pitcher Profile
- Show "Practice History (TAG Sports)" tab
- "Here's my home practice from this week"
- Shows sessions: Mar 20 (45 pitches, 71.2 mph), Mar 22 (48 pitches, 72.1 mph)
- "Coach can see I've been working on velocity at home"

**Part 4: Cross-Validation (2 minutes)**
- Show facility session starting
- "Now I'm throwing at the facility with PitchTracker cameras AND my TAG device"
- Show both systems measuring simultaneously:
  - Pitch #1: TAG: 73.2 mph, PitchTracker: 73.1 mph (0.1 mph difference ✅)
  - Pitch #2: TAG: 74.5 mph, PitchTracker: 74.3 mph (0.2 mph difference ✅)
- "Both systems agree - this builds trust"

**Part 5: Value Proposition (1-2 minutes)**
- "For athletes: Practice data follows them from home to facility"
- "For facilities: See practice baseline, attract TAG users"
- "For TAG Sports: Referral revenue ($90K-135K/year), competitive moat, dual-mode device value"
- "For everyone: Data continuity, validated accuracy, better training"

**Part 6: Partnership Ask (1 minute)**
- "This is Phase 1 (working now). Let's talk about Phase 2-4:"
  - Cloud sync (automatic, seamless)
  - Bluetooth PC ingest (TAG device as facility peripheral)
  - Bidirectional insights (PitchTracker analysis in TAG app)
- "90-day pilot, low risk, high upside. Interested?"

**Recording Options:**
- **Screen recording:** OBS Studio (free), Camtasia, or Loom
- **Voiceover:** Narrate as you demonstrate
- **Length:** 5-7 minutes (short attention span friendly)

**Deliverable:** Demo video showing working TAG integration

**Time:** 4-6 hours (setup, recording, editing, export)

---

## Phase 5: Enhanced Partnership Outreach (Day 15+)

### Step 9: Package Demo with Partnership Materials

**Updated Outreach Email:**

```
Subject: Partnership Opportunity: TAG Sports + PitchTracker - WORKING DEMO INCLUDED

Hi [TAG Contact],

I've been using your TAG Sports device and built a working integration with PitchTracker
(our professional facility pitch tracking system). I'm reaching out to propose a partnership.

🎥 WORKING DEMO (5 minutes): [Link to demo video]

See the integration in action:
• TAG Sports practice data imports into PitchTracker
• Coaches see athletes' home practice before facility sessions
• Cross-validation: TAG device + PitchTracker cameras measure simultaneously (±0.3 mph agreement!)
• Data continuity from home → facility

THE OPPORTUNITY
───────────────
Your 10,000+ TAG users practice at home. Many join training facilities. Currently their
TAG data stays in your app. We've solved this.

Integration enables:
• Athletes: Data follows them (practice → facility)
• Facilities: See TAG practice baseline, attract your users
• TAG Sports: Referral fees ($90K-135K/year), competitive moat, network effects

DEEP INTEGRATION ROADMAP
────────────────────────
✅ Phase 1: Import/export (WORKING NOW - see demo)
→ Phase 2: Cloud sync (automatic, 8-12 weeks)
→ Phase 3: Bluetooth PC ingest (TAG device works at facility, 6-8 weeks)
→ Phase 4: Bidirectional insights (PitchTracker analysis in TAG app, 8-12 weeks)

Phase 3 (Bluetooth) is the game-changer:
• Athletes bring TAG devices to facilities
• Devices pair with facility PCs via Bluetooth
• Real-time velocity streaming + cross-validation
• Parents watch live from TAG app
→ Makes TAG the ONLY consumer radar that "levels up" to professional facility use

VALIDATION RESULTS (Included in package)
────────────────────────────────────────
We validated PitchTracker against your TAG device:
• 110 pitches tested
• MAE: [X.XX] mph (PitchTracker vs. TAG agreement)
• 95% CI: ±[X.XX] mph
• Correlation: [0.9XX]

Both systems show strong agreement. This proves the integration works AND validates
our accuracy.

PARTNERSHIP PACKAGE (Google Drive)
──────────────────────────────────
🔗 [Link to full package]

Includes:
• Working demo video (5 min - WATCH THIS FIRST)
• Validation report (TAG device as reference)
• Business case (40 pages - $90K-135K referral revenue opportunity)
• Technical specs (50 pages - Bluetooth + Cloud API architecture)
• Product screenshots (12 images - show PitchTracker quality)
• Integration mockups (4 images - show future vision)

NEXT STEPS
──────────
30-minute discovery call to discuss partnership?

Available times:
• [Option 1]
• [Option 2]
• [Option 3]

This integration is already working. Let's talk about scaling it together.

Best,
[Your Name]
Founder, PitchTracker
[Email] | [Phone]

P.S. I'm a TAG Sports user myself - love the device. Wanted to make it work at
professional facilities too. That's why I built this integration.
```

---

## Timeline: Working Demo in 2 Weeks

| Days | Phase | Deliverable | Status |
|------|-------|-------------|--------|
| **1-2** | Reverse-engineer TAG format | Data format analysis doc | ⏰ START NOW |
| **3-5** | Build import service | Working JSON import | 2-3 days |
| **6-7** | Build import UI | Functional dialog | 2 days |
| **8-10** | Execute validation | 110 pitch comparison | 3 days |
| **11** | Publish validation report | Accuracy claims with evidence | 1 day |
| **12-14** | Create demo | 5-7 min video + screenshots | 2-3 days |
| **15** | **OUTREACH TO TAG SPORTS** | Email with working demo | ✅ |

**Total: 2 weeks to working demo + validation + partnership outreach**

---

## Immediate Actions (TODAY)

### Action 1: Examine Your TAG Device and App (2-3 hours)

**Do this now:**

1. **Open TAG Sports App**
   - [ ] Navigate to your session history
   - [ ] Look for Export / Share / Download button
   - [ ] If found: Export a session, examine the file
   - [ ] Document what you find

2. **Check TAG Device Info**
   - [ ] Model number (TAG One, TAG One Pro, etc.)
   - [ ] Firmware version (if visible in app)
   - [ ] Battery level (ensure charged for testing)

3. **Plan Test Session**
   - [ ] Schedule time to throw 20-30 pitches with TAG device
   - [ ] Have PitchTracker ready to record simultaneously
   - [ ] Goal: Capture dual measurements (TAG + PitchTracker)

**Report Back:**
- Does TAG app have export feature?
- What format is the data?
- Can you share a sample export (anonymized)?

---

### Action 2: Capture Real TAG Data (1-2 hours)

**If TAG app has export:**
1. Export your most recent session
2. Share the file format with me
3. I'll help you adapt the import service to match

**If TAG app doesn't have export:**
1. We'll explore app data storage (iOS/Android methods)
2. OR: Use Bluetooth sniffing to capture device data
3. OR: Contact TAG Sports support: "How can I export my data?"

---

### Action 3: Test Session with Both Systems (1-2 hours)

**Run a test session:**
1. Set up PitchTracker (cameras ready)
2. Set up TAG device (positioned for measurement)
3. Throw 10-20 pitches (or have someone throw)
4. **Record:**
   - TAG Sports app: Note velocity for each pitch
   - PitchTracker: Note velocity from stereo tracking
5. Create comparison table (pitch #, TAG mph, PitchTracker mph, difference)

**This gives you:**
- ✅ First validation data (even if small sample)
- ✅ Proof that integration concept works
- ✅ Real-world test of both systems simultaneously

---

## Next Steps (After Initial Investigation)

**Once you've examined TAG device and captured data:**

**Option A: TAG App Has Export Feature**
→ I'll help you build import adapter for TAG's format (1-2 days)
→ Build UI dialog (2-3 days)
→ Create working demo (1 day)
→ **Ready for TAG outreach in 4-6 days**

**Option B: TAG App Doesn't Have Export**
→ We'll reverse-engineer the data format (2-3 days)
→ Build import from extracted data (2-3 days)
→ Build UI dialog (2-3 days)
→ **Ready for TAG outreach in 7-9 days**

**Option C: TAG Bluetooth Direct Integration**
→ Skip export/import entirely
→ Connect TAG device to PC via Bluetooth (if supported)
→ Build BLE listener service (3-5 days)
→ Stream real-time velocity to PitchTracker
→ **Ultimate demo: Live TAG device streaming** (1-2 weeks)

---

## Value of Having TAG Device

### Immediate Benefits

1. **Validation Reference** ($300-400 value)
   - Don't need to buy Pocket Radar
   - TAG device IS your validation reference
   - Closes critical UX compliance gap (validation required)

2. **Integration Testing** (Priceless)
   - Build with real device, not assumptions
   - Test import with actual TAG data format
   - Verify cross-validation actually works

3. **Stronger Partnership Position**
   - "We're TAG Sports users ourselves"
   - "We've built and tested the integration"
   - "Here's a working demo with YOUR device"

4. **Faster Development**
   - No guessing about data format
   - No waiting for TAG Sports to provide sample data
   - Immediate iteration based on real device behavior

5. **Demo Credibility**
   - Show YOUR TAG device connected/importing
   - Show YOUR practice sessions
   - "I use TAG Sports, love it, wanted it to work at facilities too"

---

## Questions for You (To Proceed)

**Please investigate and report back:**

1. **TAG Sports App Export:**
   - Does the TAG app have an "Export" or "Share Data" feature?
   - If yes, what format? (JSON, CSV, proprietary?)
   - Can you export a sample session and share the file structure?

2. **TAG Device Model:**
   - What model do you have? (TAG One, TAG One Pro, other?)
   - What firmware version (if visible in app)?
   - iOS or Android app?

3. **Your Usage:**
   - How many sessions do you have in TAG app?
   - What velocity range (helps with validation test planning)?
   - Do you have access to a pitcher for test sessions (or will you throw yourself)?

4. **Integration Preference:**
   - Do you want to build import/export first (Phase 1, easier)?
   - Or go straight to Bluetooth integration (Phase 3, more impressive but harder)?

5. **Timeline:**
   - How quickly do you want to reach out to TAG Sports?
   - OK with 2-week timeline to build working demo?
   - Or need faster (we can do minimum demo in 1 week)?

---

## Recommended Path Forward

**My Strong Recommendation:**

**Week 1 (Days 1-7):**
- TODAY: Examine TAG device, check for export feature
- Days 2-3: Reverse-engineer data format, build import adapter
- Days 4-5: Build basic import UI dialog
- Days 6-7: Test with real TAG data, iterate

**Week 2 (Days 8-14):**
- Days 8-10: Run validation tests (TAG vs. PitchTracker, 50-100 pitches)
- Day 11: Analyze results, publish validation report
- Days 12-14: Create demo video, package materials

**Day 15: Outreach to TAG Sports with:**
- ✅ Working demo video (shows real integration)
- ✅ Validation report (proves accuracy with their device)
- ✅ Your TAG device in demo ("I'm a customer, built this for myself")

**This is a MUCH stronger position than just specs.**

---

## What to Do Right Now (Next 2 Hours)

1. **Open TAG Sports App**
   - Explore all menus, settings, profile screens
   - Look for export/share/download features
   - Screenshot anything relevant

2. **Check Device Info**
   - Model number
   - Battery level (charge if needed)
   - Firmware version (if shown)

3. **Plan Test Session**
   - When can you throw 20-30 pitches?
   - Or who can throw for validation?
   - Where (backyard, cage, facility)?

4. **Report Back**
   - Tell me what you found about export capability
   - Share sample data if you can export
   - I'll adapt the integration code to match TAG's actual format

**Let me know what you discover about the TAG device/app, and I'll create the specific implementation plan for YOUR TAG Sports data format.**

---

**Status:** ✅ Plan ready, waiting for TAG device analysis
**Next:** You investigate TAG app (2 hours), report findings
**Then:** I help build working integration (4-7 days)
**Result:** Working demo + validation for TAG Sports outreach
