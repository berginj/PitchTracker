# TAG Sports Device Investigation - Quick Start Checklist

**Purpose:** Understand your TAG device capabilities for integration
**Time Required:** 1-2 hours
**Priority:** ⏰ DO THIS NOW (blocks everything else)

---

## ✅ Investigation Checklist (Complete and Report Back)

### Part 1: TAG Sports App Exploration (30-45 minutes)

**Open your TAG Sports app and check:**

- [ ] **App Version**
  - Location: Settings or About screen
  - Note version number: ________________
  - Platform: ☐ iOS  ☐ Android

- [ ] **Device Info**
  - TAG device model: ________________
  - Firmware version (if shown): ________________
  - Battery level: ________%
  - Last sync date: ________________

- [ ] **Session History**
  - How many sessions do you have? ________
  - Date range: ________ to ________
  - Total pitches recorded: ________ (approximate)

- [ ] **Export Feature Search**
  - Check these screens:
    - [ ] Profile screen
    - [ ] Session list screen
    - [ ] Individual session detail screen
    - [ ] Settings screen
    - [ ] Share/Export section (if exists)
    - [ ] More/... menu

  - **Found export feature?**
    - ☐ YES - Location: ________________
    - ☐ NO - No export found

- [ ] **If Export Exists:**
  - [ ] Tap export on a test session
  - [ ] Note what happens:
    - Does it generate a file? ☐ Yes ☐ No
    - Does it open share sheet? ☐ Yes ☐ No
    - What formats offered? ☐ Email ☐ Save to Files ☐ Cloud ☐ Other: ________

  - [ ] **Export a sample session:**
    - Select smallest session (10-20 pitches)
    - Export to Files / Email to yourself
    - **File name:** ________________
    - **File type:** ☐ .json ☐ .csv ☐ .txt ☐ .xml ☐ Other: ________
    - **File size:** ________ KB

  - [ ] **Open exported file:**
    - Can you open it in text editor? ☐ Yes ☐ No
    - If yes, paste first 20-30 lines here (or email to yourself)

- [ ] **If NO Export:**
  - [ ] Check app settings for "Data Export", "Backup", "Download Data"
  - [ ] Check if app syncs to cloud (iCloud, Google Drive, TAG Sports cloud)
  - [ ] Note: We'll need to extract data differently (see Part 2)

---

### Part 2: Data Format Analysis (If Export Exists) (15-30 minutes)

**If you successfully exported a file:**

- [ ] **Open in text editor** (Notepad, VS Code, TextEdit)

- [ ] **Identify format:**
  - ☐ JSON (starts with `{` or `[`)
  - ☐ CSV (comma-separated values)
  - ☐ XML (starts with `<?xml` or `<`)
  - ☐ Binary/Unknown (can't read as text)

- [ ] **If JSON, look for these fields:**
  ```
  Does it have:
  - [ ] Session ID or identifier
  - [ ] Date/timestamp
  - [ ] Athlete name or user ID
  - [ ] Pitch list / array
  - [ ] Individual pitch speeds
  - [ ] Summary stats (avg, max, min velocity)
  ```

- [ ] **Copy sample data:**
  ```
  Paste a sanitized sample here (change name to "Test User"):




  ```

- [ ] **Note differences from our spec:**
  - Field names different? (e.g., "speed" vs "velocity", "user_id" vs "tag_user_id")
  - Structure different? (nested vs. flat)
  - Additional fields we didn't anticipate?

---

### Part 3: Bluetooth Capability Check (15-30 minutes)

**Goal:** Determine if TAG device can connect to PC (Phase 3 potential)

- [ ] **Check TAG App Settings:**
  - Look for: "Bluetooth", "Device Connection", "Pairing"
  - Can TAG device pair with multiple devices? ☐ Yes ☐ No ☐ Unknown
  - Current pairing: ☐ Phone only ☐ Can pair with other devices

- [ ] **Check PC Bluetooth (Windows):**
  - Open Settings → Bluetooth & devices
  - Is Bluetooth enabled? ☐ Yes ☐ No
  - If no: [ ] Enable Bluetooth
  - [ ] Click "Add device"
  - [ ] Put TAG device in pairing mode (check TAG manual)
  - [ ] Does TAG device appear in list? ☐ Yes ☐ No ☐ Didn't try

- [ ] **If TAG Appears in PC Bluetooth:**
  - [ ] Try to pair
  - Result: ☐ Paired successfully ☐ Failed ☐ Requires app authentication
  - Note: ________________

**Important:** TAG device may be locked to mobile app only (firmware limitation). If so, Bluetooth PC integration requires TAG Sports partnership and firmware update.

---

### Part 4: Test Session Planning (15 minutes)

**Logistics for validation testing:**

- [ ] **Who will throw pitches?**
  - ☐ You
  - ☐ Someone else (who: ________________)
  - ☐ Need to find pitcher

- [ ] **Where can you test?**
  - ☐ Backyard / driveway
  - ☐ Local batting cage
  - ☐ Baseball field
  - ☐ Indoor facility
  - Location: ________________

- [ ] **When can you test?**
  - Earliest date: ________________
  - Time needed: 1-2 hours (setup + 50-100 pitches)

- [ ] **Equipment check:**
  - [ ] TAG device charged and working
  - [ ] PitchTracker cameras set up
  - [ ] Tape measure (verify distance: 60.5 ft mound to plate)
  - [ ] Baseballs (consistent type)
  - [ ] Laptop/PC for PitchTracker

---

## What to Report Back (Email/Message)

**Please send me:**

1. **TAG App Export Status:**
   - "Export feature exists" or "No export feature found"
   - If exists: Sample exported file (email as attachment)

2. **Data Format:**
   - File type (.json, .csv, etc.)
   - Sample data (first 20-30 lines, sanitize your name)
   - OR: "Couldn't export, need alternative method"

3. **Device Info:**
   - TAG device model: ________________
   - App version: ________________
   - Platform: iOS or Android

4. **Test Session Timeline:**
   - When can you run test session? ________________
   - Who's throwing? ________________
   - Location: ________________

5. **Questions:**
   - Any blockers or concerns?
   - Prefer to build import/export first OR Bluetooth direct?

---

## Quick Wins (While Investigating)

**Even before building integration, you can use TAG device for validation:**

**Quick Validation Test (30 minutes):**
1. Set up PitchTracker session
2. Set up TAG device
3. Throw 10 pitches
4. Manually note:
   - Pitch 1: TAG: ____ mph, PitchTracker: ____ mph, Difference: ____
   - Pitch 2: TAG: ____ mph, PitchTracker: ____ mph, Difference: ____
   - (repeat for 10 pitches)

5. Calculate average difference:
   - If <0.5 mph: Excellent agreement ✅
   - If <1.0 mph: Good agreement ✅
   - If <2.0 mph: Acceptable ⚠️
   - If >2.0 mph: Investigation needed ❌

**This gives you immediate validation data** (even manual, better than nothing!)

---

## Expected Findings (Predictions)

**Most Likely Scenario:**
- TAG Sports app HAS export feature (email, save to files)
- Format is JSON or CSV
- Contains: session metadata, pitch list with speeds, summary stats
- Similar to our spec but field names differ slightly
- **Time to adapt:** 1-2 days

**Alternative Scenario:**
- TAG app NO export (data locked in app)
- We extract from app storage (Android easier than iOS)
- OR: We use Bluetooth sniffing to capture device data
- **Time to work around:** 2-4 days

**Best Case Scenario:**
- TAG app has export
- Format matches our spec almost exactly
- Import adapter takes <1 day
- **Working integration in 3-4 days**

---

## Next Message to Me Should Include:

```
TAG DEVICE INVESTIGATION RESULTS
─────────────────────────────────

App Version: [Your version]
Platform: [iOS/Android]
Device Model: [TAG One / TAG One Pro / etc.]

Export Feature:
[X] Found - Location: [Menu path]
[ ] Not found

If Export Found:
- File format: [JSON / CSV / Other]
- Sample data: [Paste or attach file]

Validation Test Timeline:
- Can test: [Date]
- Pitcher: [You / Other person]
- Location: [Where]

Questions:
- [Any blockers or concerns?]
```

---

**PRIORITY:** Investigate TAG device TODAY (1-2 hours)
**Report back:** Tonight or tomorrow morning
**Then:** I'll create specific implementation plan based on YOUR TAG device's actual capabilities

**This is the fastest path to working demo + validation + strong TAG Sports partnership position.** 🚀
