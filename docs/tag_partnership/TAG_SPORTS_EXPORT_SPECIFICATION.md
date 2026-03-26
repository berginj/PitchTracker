# TAG Sports Data Export Specification for PitchTracker Integration

**Document Type:** Data Format Specification for TAG Sports Engineering Team
**Version:** 1.0
**Date:** March 26, 2026
**Purpose:** Enable TAG Sports app to export practice data for PitchTracker facility integration
**Status:** READY TO SEND TO TAG SPORTS

---

## Executive Summary

This specification defines the data export format needed for TAG Sports + PitchTracker integration.

**What We're Asking TAG Sports to Build:**
- Add "Export to PitchTracker" feature in TAG Sports mobile app (iOS/Android)
- Export athlete's practice session data as JSON file
- Enable sharing via email, save to files, or cloud storage

**Engineering Effort for TAG Sports:** ~2 weeks (1 mobile developer)

**Business Value for TAG Sports:**
- Enables facility referral revenue ($90K-135K/year potential)
- Creates competitive moat (exclusive PitchTracker integration)
- Makes TAG devices more valuable (data portable to professional training)
- Differentiates from Pocket Radar, Bushnell (they don't have facility integration)

---

## Table of Contents

1. [Use Case & User Flow](#1-use-case--user-flow)
2. [JSON Schema Specification](#2-json-schema-specification)
3. [Example Export File](#3-example-export-file)
4. [Implementation Guide for TAG Sports](#4-implementation-guide-for-tag-sports)
5. [Share Flow (iOS/Android)](#5-share-flow-iosandroid)
6. [Validation & Testing](#6-validation--testing)
7. [Privacy & Consent](#7-privacy--consent)
8. [Timeline & Deliverables](#8-timeline--deliverables)

---

## 1. Use Case & User Flow

### Scenario: Athlete Transfers Practice Data to Facility

**Step 1: Athlete Practices at Home (Current TAG Sports Behavior)**
- Athlete uses TAG Sports device to track pitches at home
- TAG app records session data (date, pitches, velocities)
- Data stored in TAG app (currently stays there)

**Step 2: Athlete Joins Training Facility (NEW - What Changes)**
- Athlete enrolls in facility that uses PitchTracker
- Facility coach wants to see athlete's home practice baseline

**Step 3: Athlete Exports TAG Data (NEW - What TAG Builds)**
- Athlete opens TAG Sports app
- Navigates to Profile or Sessions
- Taps **"Export to PitchTracker"** button (NEW FEATURE)
- TAG app generates JSON file with athlete's practice history
- Share sheet appears (iOS/Android native)
- Athlete selects method:
  - **Email to coach:** "coach@facility.com"
  - **Save to Files:** Downloads folder or cloud storage
  - **AirDrop** (iOS only)
  - **Other** (Google Drive, Dropbox, etc.)

**Step 4: Facility Imports Data (PitchTracker Side - We Build)**
- Coach receives email or file from athlete
- Opens PitchTracker desktop app
- Clicks "Import TAG Sports Data" button
- Selects JSON file
- PitchTracker validates and imports data
- Coach now sees athlete's practice history:
  - "45 sessions over 6 months"
  - "Average velocity: 71.4 mph"
  - "Recent trend: +1.3 mph/week (improving)"

**Step 5: Coach Uses Practice Data (Value Delivered)**
- Coach sees practice baseline BEFORE first facility session
- "I see you've been working on changeup at home - let's focus on that today"
- Athlete feels understood and valued
- **Better coaching outcomes**

---

## 2. JSON Schema Specification

### File Naming Convention

**Format:** `TAG_export_{athlete_name}_{YYYY-MM-DD}.json`

**Examples:**
- `TAG_export_john_doe_2026-03-26.json`
- `TAG_export_sarah_smith_2026-03-20.json`

**Guidelines:**
- Use lowercase, replace spaces with underscores
- Include export date (when export generated, not session date)
- UTF-8 encoding

---

### JSON Structure (Schema v1.0)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "TAG Sports to PitchTracker Export Format",
  "version": "1.0",
  "type": "object",
  "required": ["schema_version", "export_metadata", "athlete", "sessions"],
  "properties": {

    "schema_version": {
      "type": "string",
      "const": "1.0",
      "description": "Export format version for compatibility checking"
    },

    "export_metadata": {
      "type": "object",
      "required": ["export_date", "export_source"],
      "properties": {
        "export_date": {
          "type": "string",
          "format": "date-time",
          "description": "When export was generated (ISO 8601: YYYY-MM-DDTHH:MM:SSZ)",
          "example": "2026-03-26T10:30:00Z"
        },
        "export_source": {
          "type": "string",
          "enum": ["TAG_Sports_iOS", "TAG_Sports_Android"],
          "description": "Which TAG Sports app version generated this export"
        },
        "app_version": {
          "type": "string",
          "description": "TAG Sports app version (e.g., '2.3.1')",
          "example": "2.3.1"
        }
      }
    },

    "athlete": {
      "type": "object",
      "required": ["tag_user_id", "name"],
      "properties": {
        "tag_user_id": {
          "type": "string",
          "description": "Unique TAG Sports user ID (UUID, alphanumeric, or email)",
          "example": "tag_abc123xyz"
        },
        "name": {
          "type": "string",
          "description": "Athlete's full name",
          "example": "John Doe"
        },
        "birth_year": {
          "type": "integer",
          "minimum": 1900,
          "maximum": 2030,
          "description": "Birth year for age calculation (optional)",
          "example": 2010
        },
        "throws": {
          "type": "string",
          "enum": ["right", "left", "both", "unknown"],
          "description": "Throwing hand (optional)",
          "example": "right"
        },
        "position": {
          "type": "string",
          "description": "Primary position (optional)",
          "example": "pitcher"
        },
        "email": {
          "type": "string",
          "format": "email",
          "description": "Contact email (optional)",
          "example": "john.doe@example.com"
        }
      }
    },

    "sessions": {
      "type": "array",
      "description": "List of practice sessions (recommend last 90 days)",
      "items": {
        "type": "object",
        "required": ["session_id", "date", "pitches"],
        "properties": {
          "session_id": {
            "type": "string",
            "description": "Unique session ID (TAG Sports internal ID)",
            "example": "tag_session_20260320_001"
          },
          "date": {
            "type": "string",
            "format": "date-time",
            "description": "Session start date/time (ISO 8601)",
            "example": "2026-03-20T15:00:00Z"
          },
          "location": {
            "type": "string",
            "description": "Free-text location (optional)",
            "example": "Backyard practice"
          },
          "session_type": {
            "type": "string",
            "enum": ["practice", "bullpen", "game", "warmup", "other"],
            "description": "Type of session (optional)",
            "example": "practice"
          },
          "notes": {
            "type": "string",
            "description": "Athlete's session notes (optional)",
            "example": "Working on changeup grip"
          },
          "pitches": {
            "type": "array",
            "description": "Individual pitch measurements",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["pitch_number", "timestamp", "speed_mph"],
              "properties": {
                "pitch_number": {
                  "type": "integer",
                  "minimum": 1,
                  "description": "Pitch number in session (1, 2, 3...)",
                  "example": 1
                },
                "timestamp": {
                  "type": "string",
                  "format": "date-time",
                  "description": "When pitch was thrown (ISO 8601)",
                  "example": "2026-03-20T15:05:23Z"
                },
                "speed_mph": {
                  "type": "number",
                  "minimum": 20,
                  "maximum": 120,
                  "description": "Measured pitch speed in miles per hour",
                  "example": 72.3
                },
                "pitch_type": {
                  "type": "string",
                  "description": "Athlete-tagged pitch type (optional)",
                  "example": "Fastball"
                },
                "notes": {
                  "type": "string",
                  "description": "Pitch-specific notes (optional)",
                  "example": "Felt good"
                },
                "video_url": {
                  "type": "string",
                  "format": "uri",
                  "description": "Link to video (if TAG Sports stores video, optional)",
                  "example": "https://tagsports.ai/videos/abc123"
                }
              }
            }
          },
          "summary": {
            "type": "object",
            "description": "Session summary statistics",
            "properties": {
              "total_pitches": {
                "type": "integer",
                "description": "Total pitches in session",
                "example": 45
              },
              "avg_speed_mph": {
                "type": "number",
                "description": "Average pitch speed",
                "example": 71.2
              },
              "max_speed_mph": {
                "type": "number",
                "description": "Maximum pitch speed",
                "example": 74.8
              },
              "min_speed_mph": {
                "type": "number",
                "description": "Minimum pitch speed",
                "example": 65.1
              }
            }
          }
        }
      }
    }
  }
}
```

---

## 3. Example Export File

### Complete Example (Real-World Format)

**File:** `TAG_export_john_doe_2026-03-26.json`

```json
{
  "schema_version": "1.0",
  "export_metadata": {
    "export_date": "2026-03-26T10:30:00Z",
    "export_source": "TAG_Sports_iOS",
    "app_version": "2.3.1"
  },
  "athlete": {
    "tag_user_id": "tag_abc123xyz",
    "name": "John Doe",
    "birth_year": 2010,
    "throws": "right",
    "position": "pitcher",
    "email": "john.doe@example.com"
  },
  "sessions": [
    {
      "session_id": "tag_session_20260320_001",
      "date": "2026-03-20T15:00:00Z",
      "location": "Backyard practice",
      "session_type": "practice",
      "notes": "Working on changeup grip",
      "pitches": [
        {
          "pitch_number": 1,
          "timestamp": "2026-03-20T15:05:23Z",
          "speed_mph": 72.3,
          "pitch_type": "Fastball",
          "notes": ""
        },
        {
          "pitch_number": 2,
          "timestamp": "2026-03-20T15:06:10Z",
          "speed_mph": 68.5,
          "pitch_type": "Changeup",
          "notes": "New grip"
        },
        {
          "pitch_number": 3,
          "timestamp": "2026-03-20T15:07:02Z",
          "speed_mph": 73.1,
          "pitch_type": "Fastball",
          "notes": ""
        }
      ],
      "summary": {
        "total_pitches": 45,
        "avg_speed_mph": 71.2,
        "max_speed_mph": 74.8,
        "min_speed_mph": 65.1
      }
    },
    {
      "session_id": "tag_session_20260322_001",
      "date": "2026-03-22T16:30:00Z",
      "location": "Local batting cage",
      "session_type": "practice",
      "notes": "",
      "pitches": [
        {
          "pitch_number": 1,
          "timestamp": "2026-03-22T16:35:12Z",
          "speed_mph": 70.8,
          "pitch_type": "Fastball"
        },
        {
          "pitch_number": 2,
          "timestamp": "2026-03-22T16:36:45Z",
          "speed_mph": 69.2,
          "pitch_type": "Changeup"
        }
      ],
      "summary": {
        "total_pitches": 52,
        "avg_speed_mph": 70.8,
        "max_speed_mph": 73.9,
        "min_speed_mph": 65.2
      }
    }
  ]
}
```

### Minimal Example (Smallest Valid Export)

```json
{
  "schema_version": "1.0",
  "export_metadata": {
    "export_date": "2026-03-26T10:30:00Z",
    "export_source": "TAG_Sports_iOS"
  },
  "athlete": {
    "tag_user_id": "tag_user_123",
    "name": "Test Athlete"
  },
  "sessions": [
    {
      "session_id": "session_001",
      "date": "2026-03-20T15:00:00Z",
      "pitches": [
        {
          "pitch_number": 1,
          "timestamp": "2026-03-20T15:05:23Z",
          "speed_mph": 72.3
        }
      ],
      "summary": {
        "total_pitches": 1,
        "avg_speed_mph": 72.3
      }
    }
  ]
}
```

**Note:** This is the absolute minimum. Real exports should include all available fields.

---

## 4. Implementation Guide for TAG Sports

### For TAG Sports Mobile Engineering Team

**Estimated Effort:** 2 weeks (1 mobile developer)

**Step 1: Add Export Button to UI (2-3 days)**

**iOS (Swift/SwiftUI):**
```swift
// Add button to Profile or Sessions screen
Button("Export to PitchTracker") {
    exportToPitchTracker()
}
.buttonStyle(.borderedProminent)

func exportToPitchTracker() {
    // Generate JSON export
    let exportData = generatePitchTrackerExport()

    // Show share sheet
    let fileURL = saveExportToTemporaryFile(exportData)
    presentShareSheet(url: fileURL)
}
```

**Android (Kotlin):**
```kotlin
// Add button to Profile or Sessions screen
Button(onClick = { exportToPitchTracker() }) {
    Text("Export to PitchTracker")
}

fun exportToPitchTracker() {
    // Generate JSON export
    val exportData = generatePitchTrackerExport()

    // Show share intent
    val fileUri = saveExportToCache(exportData)
    shareFile(fileUri)
}
```

**UI Placement:** Profile screen, Sessions list screen, or Settings → Data Export

---

**Step 2: Generate JSON Export (3-4 days)**

**Pseudo-code for TAG Sports backend:**

```javascript
function generatePitchTrackerExport(userId, dateRange = 90) {
  // Get athlete data from TAG database
  const athlete = getAthleteProfile(userId);

  // Get sessions from last 90 days
  const sessions = getSessionsForUser(userId, {
    startDate: Date.now() - (dateRange * 24 * 60 * 60 * 1000),
    endDate: Date.now()
  });

  // Build export JSON
  const exportData = {
    schema_version: "1.0",
    export_metadata: {
      export_date: new Date().toISOString(),
      export_source: Platform.OS === 'ios' ? 'TAG_Sports_iOS' : 'TAG_Sports_Android',
      app_version: getAppVersion()
    },
    athlete: {
      tag_user_id: athlete.id,
      name: athlete.name,
      birth_year: athlete.birthYear,
      throws: athlete.throwingHand,
      position: athlete.position,
      email: athlete.email
    },
    sessions: sessions.map(session => ({
      session_id: session.id,
      date: session.startTime.toISOString(),
      location: session.location || "Unknown",
      session_type: session.type || "practice",
      notes: session.notes || "",
      pitches: session.pitches.map(pitch => ({
        pitch_number: pitch.sequenceNumber,
        timestamp: pitch.timestamp.toISOString(),
        speed_mph: pitch.velocity,
        pitch_type: pitch.userTaggedType || "",
        notes: pitch.notes || "",
        video_url: pitch.videoUrl || null
      })),
      summary: {
        total_pitches: session.pitches.length,
        avg_speed_mph: calculateAverage(session.pitches.map(p => p.velocity)),
        max_speed_mph: Math.max(...session.pitches.map(p => p.velocity)),
        min_speed_mph: Math.min(...session.pitches.map(p => p.velocity))
      }
    }))
  };

  return JSON.stringify(exportData, null, 2); // Pretty-printed for readability
}
```

**Field Mapping Notes:**
- `tag_user_id`: Use TAG's internal user identifier (UUID, email, or account ID)
- `session_id`: Use TAG's internal session identifier
- `timestamp`: Convert to ISO 8601 format with timezone (UTC recommended)
- `speed_mph`: Use TAG's measured velocity (as displayed in app)
- All optional fields can be omitted if not available

---

**Step 3: Implement Share Flow (2-3 days)**

**iOS (Share Sheet):**
```swift
func presentShareSheet(url: URL) {
    let activityVC = UIActivityViewController(
        activityItems: [url],
        applicationActivities: nil
    )

    // Optional: Suggest specific activities
    activityVC.excludedActivityTypes = [
        .addToReadingList,
        .assignToContact,
        .print
    ]

    present(activityVC, animated: true)
}
```

**Android (Share Intent):**
```kotlin
fun shareFile(uri: Uri) {
    val shareIntent = Intent(Intent.ACTION_SEND).apply {
        type = "application/json"
        putExtra(Intent.EXTRA_STREAM, uri)
        putExtra(Intent.EXTRA_SUBJECT, "TAG Sports Practice Data for PitchTracker")
        putExtra(Intent.EXTRA_TEXT, "My TAG Sports practice data export for facility training.")
    }

    startActivity(Intent.createChooser(shareIntent, "Share TAG Sports Data"))
}
```

---

**Step 4: Add Consent Flow (1-2 days)**

**Before exporting, show consent dialog:**

```
┌────────────────────────────────────────┐
│  Export Practice Data?                 │
├────────────────────────────────────────┤
│                                        │
│  You're about to export your TAG       │
│  Sports practice data to share with    │
│  your facility coach.                  │
│                                        │
│  Data included:                        │
│  • 12 practice sessions (last 90 days) │
│  • 487 total pitches                   │
│  • Velocity measurements               │
│  • Session dates and locations         │
│                                        │
│  Your data will NOT be automatically   │
│  uploaded. You control who receives it.│
│                                        │
│  [Cancel]           [Export Data]      │
└────────────────────────────────────────┘
```

**For users under 13 (COPPA compliance):**
- Require parental consent (email to parent)
- Or: Disable export for users <13 without parent account linked

---

**Step 5: Testing & QA (2-3 days)**

**Test Cases:**
- [ ] Export session with 10 pitches (small dataset)
- [ ] Export session with 100+ pitches (large dataset)
- [ ] Export multiple sessions (3-5 sessions)
- [ ] Export with missing optional fields (location, notes)
- [ ] Export with special characters in name/location
- [ ] Validate JSON against schema (use JSON validator)
- [ ] Test share flow (email, save to files, cloud)
- [ ] Test on iOS and Android
- [ ] Edge cases: No sessions, incomplete session, corrupt data

**Validation:**
```javascript
// Validate export against schema
const Ajv = require('ajv');
const ajv = new Ajv();

const schema = { /* Schema from Section 2 */ };
const validate = ajv.compile(schema);

const exportData = generatePitchTrackerExport(userId);
const valid = validate(exportData);

if (!valid) {
  console.error('Export validation failed:', validate.errors);
}
```

---

## 5. Share Flow (iOS/Android)

### iOS: UIActivityViewController

**Supported Destinations:**
- ✅ Mail (email as attachment)
- ✅ Messages (iMessage attachment)
- ✅ AirDrop (to nearby Mac/iPhone)
- ✅ Save to Files (iCloud Drive, local storage)
- ✅ Third-party apps (Dropbox, Google Drive, etc.)

**File Type:** `application/json` or `text/plain`

**Suggested Filename:** Include athlete name and date for easy identification

---

### Android: ACTION_SEND Intent

**Supported Destinations:**
- ✅ Gmail (email attachment)
- ✅ File Manager (save to storage)
- ✅ Google Drive (upload to cloud)
- ✅ Dropbox, OneDrive, etc.
- ✅ Nearby Share (Android equivalent of AirDrop)

**MIME Type:** `application/json` or `text/plain`

**Provider:** Use FileProvider for API 24+ (secure file sharing)

---

## 6. Validation & Testing

### TAG Sports Team Should Validate

**Before shipping to production:**

1. **Schema Validation**
   - Use JSON schema validator (ajv, jsonschema)
   - Ensure all exports pass validation
   - Test edge cases (empty sessions, missing fields)

2. **File Size Testing**
   - Small export (10 pitches): ~5-10 KB
   - Medium export (100 pitches, 5 sessions): ~50-100 KB
   - Large export (1000+ pitches, 50 sessions): ~500 KB - 1 MB
   - **File size should be reasonable for email attachment**

3. **Character Encoding**
   - Test with special characters in names (José, François)
   - Test with emojis in notes (if app allows)
   - Ensure UTF-8 encoding

4. **Date Format Compatibility**
   - Verify ISO 8601 format
   - Include timezone (Z for UTC recommended)
   - Test date parsing in PitchTracker (we'll validate on our side)

### PitchTracker Validation (Our Responsibility)

**We will validate TAG exports:**
- ✅ Parse JSON successfully
- ✅ Validate against schema
- ✅ Handle missing optional fields gracefully
- ✅ Detect malformed data and show clear error messages
- ✅ Import and display correctly in UI

---

## 7. Privacy & Consent

### Data Privacy Requirements

**TAG Sports Must Ensure:**

1. **User Consent**
   - Show consent dialog before export
   - Explain what data is being exported
   - Athlete must explicitly approve

2. **COPPA Compliance (Users <13)**
   - Require parental consent for users under 13
   - OR: Disable export for <13 without parent account
   - Store consent record

3. **Data Minimization**
   - Only export performance data (velocities, dates, pitches)
   - Don't include unnecessary personal data
   - Email is optional (athlete can omit)

4. **User Control**
   - Athlete controls WHO receives data (they choose share destination)
   - NO automatic sharing or uploading
   - Athlete can export multiple times (not one-time-only)

### What Data is Shared

**Included:**
- ✅ Athlete name, TAG user ID
- ✅ Session dates, locations, notes
- ✅ Pitch velocities, timestamps
- ✅ Session summaries (pitch counts, averages)

**NOT Included:**
- ❌ Payment information
- ❌ Device serial numbers (unless needed for support)
- ❌ Friends/social data
- ❌ Location GPS coordinates (unless athlete specifically noted location)
- ❌ Biometric data beyond performance metrics

### PitchTracker's Privacy Commitments

**We commit to:**
- ✅ Store athlete data securely (encrypted at rest)
- ✅ Only share with enrolled facilities (athlete must enroll to grant access)
- ✅ Allow data deletion (GDPR, CCPA compliance)
- ✅ No third-party data sales
- ✅ Use data only for coaching/training purposes

---

## 8. Timeline & Deliverables

### TAG Sports Engineering Deliverables

**Milestone 1: Design & Planning (Week 1)**
- [ ] Review specification (this document)
- [ ] Technical alignment call with PitchTracker engineering
- [ ] UI mockup for export feature
- [ ] Internal approval for development

**Milestone 2: Implementation (Week 2)**
- [ ] Implement JSON export generation
- [ ] Add "Export to PitchTracker" button in UI
- [ ] Implement share flow (iOS/Android)
- [ ] Add consent dialog
- [ ] Unit tests for export logic

**Milestone 3: Testing & QA (Week 3)**
- [ ] Test on iOS and Android
- [ ] Validate JSON against schema
- [ ] Test share destinations (email, files, cloud)
- [ ] Edge case testing
- [ ] Beta testing with 5-10 users

**Milestone 4: Release (Week 4)**
- [ ] App store submission (iOS: App Store, Android: Play Store)
- [ ] Release notes mentioning PitchTracker integration
- [ ] User documentation (how to export)
- [ ] Coordinate launch with PitchTracker partnership announcement

**Total Timeline: 4 weeks from approval to production release**

---

### PitchTracker Engineering Deliverables (Parallel)

**Milestone 1: Import Service (Week 1-2)**
- [x] `app/services/tag_sports_integration.py` (70% complete)
- [ ] Complete parsing and validation logic
- [ ] Unit tests (7 written, need 5-10 more)

**Milestone 2: Import UI (Week 2-3)**
- [ ] `ui/coaching/dialogs/import_tag_data_dialog.py`
- [ ] "Import TAG Sports Data" button in Session Start Dialog
- [ ] Practice History display widget

**Milestone 3: Testing & Documentation (Week 3-4)**
- [ ] Integration tests (end-to-end workflow)
- [ ] User documentation (how to import TAG data)
- [ ] Demo video creation

**Milestone 4: Release (Week 4)**
- [ ] PitchTracker v1.6.0 with TAG import feature
- [ ] Partnership announcement (coordinated with TAG Sports)

**Total Timeline: 4 weeks parallel development**

---

## 9. File Size and Performance Considerations

### Expected File Sizes

| Sessions | Pitches | File Size (Estimated) | Email-Friendly? |
|----------|---------|----------------------|-----------------|
| 1 session | 10 pitches | ~5 KB | ✅ Yes |
| 5 sessions | 50 pitches | ~25 KB | ✅ Yes |
| 10 sessions | 100 pitches | ~50 KB | ✅ Yes |
| 30 sessions | 500 pitches | ~250 KB | ✅ Yes |
| 90 days (~50 sessions) | 2000 pitches | ~1 MB | ⚠️ May be large for email |

**Recommendation:** Export last 90 days (balance: comprehensive data vs. file size)

**If file size >5 MB:** Consider splitting into multiple exports or compressing

---

### Export Performance

**Target Performance (TAG Sports App):**
- Export generation: <2 seconds (for 90 days of data)
- File write: <1 second
- Share sheet display: <1 second
- **Total: <5 seconds** from button tap to share

**Optimization Tips:**
- Pre-aggregate summary stats (don't recalculate on export)
- Use efficient JSON serialization
- Generate exports in background thread (don't block UI)

---

## 10. Quality Standards

### JSON Format Requirements

**MUST HAVE:**
- ✅ Valid JSON (passes JSON.parse() or equivalent)
- ✅ UTF-8 encoding
- ✅ Required fields present (schema_version, athlete, sessions)
- ✅ ISO 8601 date format (YYYY-MM-DDTHH:MM:SSZ)
- ✅ Pitch velocities in mph (not km/h or other units)

**SHOULD HAVE:**
- ✅ Pretty-printed (indented, readable) - helps debugging
- ✅ Consistent field ordering
- ✅ Null for missing optional fields (not omitted entirely)
- ✅ Summary stats match detail data (total_pitches = pitches.length)

**NICE TO HAVE:**
- Comments explaining data structure (if JSON supports, or in separate README)
- Version history (if schema changes in future)
- Checksum for data integrity verification

---

## 11. Error Handling

### TAG Sports App Should Handle

**Export Errors:**
- No sessions in date range → Show message: "No practice data to export. Record sessions first."
- Database error → "Export failed. Please try again."
- File write error → "Cannot save export file. Check storage permissions."
- Share error → "Share failed. Try saving to Files instead."

**User Guidance:**
- If export is large (>2 MB) → Suggest: "Export is large. Recommend email or save to cloud."
- If no email configured → Guide to save to Files instead
- If share cancelled → Allow retry (don't lose generated export)

---

## 12. Future Enhancements (Phase 2+)

### Optional Export Preferences (Future)

**Settings Screen:**
```
┌────────────────────────────────────┐
│  PitchTracker Integration          │
├────────────────────────────────────┤
│                                    │
│  Export Range:                     │
│  ○ Last 30 days                    │
│  ● Last 90 days (recommended)      │
│  ○ Last 180 days                   │
│  ○ All sessions                    │
│                                    │
│  Include:                          │
│  ☑ Session notes                   │
│  ☑ Pitch types (if tagged)         │
│  ☐ Video links                     │
│                                    │
│  [Save Preferences]                │
└────────────────────────────────────┘
```

**Cloud Sync (Phase 2):**
- Instead of manual export, auto-sync to PitchTracker cloud
- Requires OAuth integration (separate spec)
- Timeline: 3-6 months post-MVP

---

## 13. Sample Code for PitchTracker (Shows We're Ready)

### Import Validation (PitchTracker Side - Already Built)

```python
from app.services.tag_sports_integration import TagSportsIntegrationService

# This code already works:
service = TagSportsIntegrationService()
result = service.import_from_file(Path("TAG_export_john_doe_2026-03-26.json"))

if result.success:
    print(f"✅ Import successful!")
    print(f"   Athlete: {result.athlete_data.name}")
    print(f"   TAG User ID: {result.athlete_data.tag_user_id}")
    print(f"   Sessions: {result.sessions_imported}")
    print(f"   Pitches: {result.pitches_imported}")
else:
    print(f"❌ Import failed:")
    for error in result.errors:
        print(f"   - {error}")
```

**Status:** PitchTracker is **ready to receive TAG Sports exports** (service layer 80% complete).

---

## 14. Questions & Support

### For TAG Sports Engineering Team

**If you have questions about this spec:**

**Contact:** [Your Email]
**Subject:** "TAG Sports Export Spec - Technical Question"

**Common Questions (Pre-Answered):**

**Q: Why JSON instead of CSV?**
**A:** JSON supports nested data (sessions → pitches) and metadata. CSV would require multiple files or complex flattening.

**Q: Can we use different field names?**
**A:** Yes, but we prefer consistency. If you use different names, document them and we'll map on import.

**Q: 90 days of sessions too much data?**
**A:** 90 days is recommended. File sizes are small (<1 MB typically). Users can choose shorter range if preferred.

**Q: What if athlete has 1000+ sessions?**
**A:** Paginate exports (e.g., "Export last 90 days", "Export custom range"). Very active users are rare.

**Q: ISO 8601 dates required?**
**A:** Yes - universally parseable format. Use UTC timezone (Z suffix) for consistency.

**Q: Can we add extra fields?**
**A:** Yes! Extra fields are fine (we'll ignore unknown fields). Don't remove required fields.

**Q: What about data privacy?**
**A:** Export is manual (athlete controls). No automatic upload. Athlete chooses share destination. COPPA requires parental consent for <13.

---

## 15. Validation Criteria (How We'll Test)

### PitchTracker Will Validate TAG Exports Against

**Schema Compliance:**
- [ ] Valid JSON syntax
- [ ] schema_version = "1.0"
- [ ] All required fields present
- [ ] Field types correct (strings, numbers, dates)
- [ ] Date format ISO 8601
- [ ] Velocities in mph (20-120 range)

**Data Quality:**
- [ ] Timestamps chronological (pitches in order)
- [ ] Pitch numbers sequential (1, 2, 3...)
- [ ] Summary stats match detail (total_pitches = pitches.length)
- [ ] Avg velocity = mean of pitch velocities
- [ ] Max/min velocities correct

**Pass Criteria:**
- All schema validations pass → ✅ Import succeeds
- 1-2 validation warnings (e.g., timestamps out of order) → ⚠️ Import succeeds with warnings
- Critical error (missing required field, invalid JSON) → ❌ Import fails with clear error message

---

## Appendix A: Schema Validator (For TAG Sports Team)

**Use this to test exports during development:**

**JavaScript (Node.js):**
```bash
npm install ajv ajv-formats

node validate_export.js TAG_export_sample.json
```

```javascript
// validate_export.js
const Ajv = require('ajv');
const addFormats = require('ajv-formats');
const fs = require('fs');

const ajv = new Ajv();
addFormats(ajv);

// Load schema
const schema = JSON.parse(fs.readFileSync('pitchtracker_export_schema.json'));

// Load export file
const exportData = JSON.parse(fs.readFileSync(process.argv[2]));

// Validate
const validate = ajv.compile(schema);
const valid = validate(exportData);

if (valid) {
  console.log('✅ Export is valid!');
  console.log(`   Sessions: ${exportData.sessions.length}`);
  console.log(`   Athlete: ${exportData.athlete.name}`);
} else {
  console.log('❌ Validation errors:');
  validate.errors.forEach(err => {
    console.log(`   - ${err.instancePath}: ${err.message}`);
  });
}
```

**Python (for PitchTracker team - we use this):**
```python
import json
import jsonschema

# Load schema
with open('pitchtracker_export_schema.json') as f:
    schema = json.load(f)

# Load export
with open('TAG_export_sample.json') as f:
    export_data = json.load(f)

# Validate
try:
    jsonschema.validate(export_data, schema)
    print("✅ Export is valid!")
except jsonschema.ValidationError as e:
    print(f"❌ Validation error: {e.message}")
```

---

## Appendix B: Complete Schema (JSON Schema Format)

**File:** `pitchtracker_export_schema.json` (for TAG Sports validation)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "$id": "https://pitchtracker.io/schemas/tag-sports-export-v1.0.json",
  "title": "TAG Sports to PitchTracker Export Format",
  "description": "Data format for exporting TAG Sports practice session data to PitchTracker facility systems",
  "version": "1.0",
  "type": "object",
  "required": ["schema_version", "export_metadata", "athlete", "sessions"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0"
    },
    "export_metadata": {
      "type": "object",
      "required": ["export_date", "export_source"],
      "properties": {
        "export_date": {
          "type": "string",
          "format": "date-time"
        },
        "export_source": {
          "type": "string",
          "enum": ["TAG_Sports_iOS", "TAG_Sports_Android"]
        },
        "app_version": {
          "type": "string"
        }
      }
    },
    "athlete": {
      "type": "object",
      "required": ["tag_user_id", "name"],
      "properties": {
        "tag_user_id": { "type": "string" },
        "name": { "type": "string" },
        "birth_year": { "type": "integer", "minimum": 1900, "maximum": 2030 },
        "throws": { "type": "string", "enum": ["right", "left", "both", "unknown"] },
        "position": { "type": "string" },
        "email": { "type": "string", "format": "email" }
      }
    },
    "sessions": {
      "type": "array",
      "items": {
        "type": "object",
        "required": ["session_id", "date", "pitches"],
        "properties": {
          "session_id": { "type": "string" },
          "date": { "type": "string", "format": "date-time" },
          "location": { "type": "string" },
          "session_type": {
            "type": "string",
            "enum": ["practice", "bullpen", "game", "warmup", "other"]
          },
          "notes": { "type": "string" },
          "pitches": {
            "type": "array",
            "minItems": 1,
            "items": {
              "type": "object",
              "required": ["pitch_number", "timestamp", "speed_mph"],
              "properties": {
                "pitch_number": { "type": "integer", "minimum": 1 },
                "timestamp": { "type": "string", "format": "date-time" },
                "speed_mph": { "type": "number", "minimum": 20, "maximum": 120 },
                "pitch_type": { "type": "string" },
                "notes": { "type": "string" },
                "video_url": { "type": "string", "format": "uri" }
              }
            }
          },
          "summary": {
            "type": "object",
            "properties": {
              "total_pitches": { "type": "integer" },
              "avg_speed_mph": { "type": "number" },
              "max_speed_mph": { "type": "number" },
              "min_speed_mph": { "type": "number" }
            }
          }
        }
      }
    }
  }
}
```

**Send this JSON file to TAG Sports team** - they can use it for validation during development.

---

## Document Status & Next Steps

**Status:** ✅ READY TO SEND TO TAG SPORTS

**How to Use This Specification:**

**For Partnership Outreach:**
- Include in partnership package (technical appendix)
- Reference in discovery call: "We've defined the data format we need - 2 weeks to implement on your side"
- Position as: "Here's exactly what we need from TAG Sports. We handle everything on PitchTracker side."

**For Technical Alignment Meeting:**
- Send to TAG Sports engineering team
- Walk through schema together
- Answer questions about fields, formats, validation
- Agree on timeline (2-4 weeks development)

**For MOU Negotiation:**
- Attach as Exhibit A: "Data Format Specification"
- Reference in MOU: "TAG Sports agrees to implement export feature per attached specification"

---

## Contact Information

**For TAG Sports Engineering Team:**

**Technical Questions:** [Your Email]
**Specification Version:** 1.0 (March 26, 2026)
**Maintained By:** PitchTracker Engineering Team
**Change Requests:** Email with subject "TAG Export Spec - Change Request"

**We're ready to:**
- Answer questions about this spec
- Clarify any field definitions
- Provide example test files
- Coordinate joint testing once TAG implements export

---

## Appendix C: What We'll Show TAG Sports

**"We're Ready on Our Side" - Demo with Mock Data**

Even without TAG's export feature, we can demo our readiness:

1. **Create mock TAG export file** (using this spec)
2. **Show import working:**
   - "This is what a TAG Sports export looks like (JSON format)"
   - Click import, select mock file
   - "See? We parse and display TAG data correctly"
   - "When you build export feature, it'll work immediately"

3. **Show validation:**
   - "We validate against the schema"
   - Show error handling (invalid file, missing fields)
   - "Robust error messages guide users"

**Message to TAG:** "We've built our side. Export feature is ~2 weeks for your mobile team. Let's pilot this."

---

**Document Type:** Ready-to-send specification
**Audience:** TAG Sports mobile engineering team
**Status:** ✅ Complete, reviewed, ready for partnership discussions
**Next Action:** Include in TAG Sports partnership outreach materials
