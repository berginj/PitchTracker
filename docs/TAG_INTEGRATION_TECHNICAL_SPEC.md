# TAG Sports Integration - Technical Specification

**Document Type:** Technical Design & Implementation Plan
**Date:** March 26, 2026
**Version:** 1.0 (MVP Specification)
**Status:** SPECULATIVE — no partnership agreement, no MOU signed, no production
implementation. Specifications are complete; Phase 1 implementation is 2–4 weeks
of remaining engineering work. Do not present this as an active or shipped
integration. See `docs/tag_partnership/TAG_IMPLEMENTATION_STATUS.md` for the
authoritative implementation gap summary.
**Owner:** Engineering Lead

---

## Executive Summary

This document defines the **technical architecture** for integrating TAG Sports consumer data with PitchTracker facility systems. The MVP focuses on **manual data export/import** (Phase 1), with future phases enabling cloud sync and mobile app integration.

**Goal:** Enable athletes to export practice data from TAG Sports app and import into PitchTracker facility sessions, providing coaches with baseline performance history.

**Timeline:** 2-4 weeks development (2 weeks PitchTracker side, 2 weeks TAG Sports side)

---

## Phase 1: MVP - Manual Export/Import

### Architecture Overview

```
[Athlete's Phone]                    [Facility Computer]
     |                                      |
TAG Sports App                      PitchTracker App
     |                                      |
     v                                      v
"Export to                          "Import TAG Sports
 PitchTracker"                       Data" Feature
     |                                      |
     v                                      |
TAG_export_                                 |
 athlete_name_                              |
 2026-03-20.json ────── Transfer ──────────>│
     (via email/USB/cloud)                  |
                                            v
                                    Parse & Validate
                                            |
                                            v
                                    Store in Pitcher Profile
                                            |
                                            v
                                    Display in "Practice History"
```

---

## Data Contract Specification

### TAG Sports Export Format (JSON Schema v1.0)

**File Naming Convention:** `TAG_export_{athlete_name}_{YYYY-MM-DD}.json`

**Schema:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["schema_version", "export_metadata", "athlete", "sessions"],
  "properties": {
    "schema_version": {
      "type": "string",
      "const": "1.0",
      "description": "TAG Sports export format version"
    },
    "export_metadata": {
      "type": "object",
      "required": ["export_date", "export_source"],
      "properties": {
        "export_date": {
          "type": "string",
          "format": "date-time",
          "description": "When export was generated (ISO 8601)"
        },
        "export_source": {
          "type": "string",
          "enum": ["TAG_Sports_iOS", "TAG_Sports_Android"],
          "description": "Which TAG Sports app generated export"
        },
        "app_version": {
          "type": "string",
          "description": "TAG Sports app version (e.g., '2.1.3')"
        }
      }
    },
    "athlete": {
      "type": "object",
      "required": ["tag_user_id", "name"],
      "properties": {
        "tag_user_id": {
          "type": "string",
          "description": "Unique TAG Sports user ID (UUID or alphanumeric)"
        },
        "name": {
          "type": "string",
          "description": "Athlete's full name"
        },
        "birth_year": {
          "type": "integer",
          "minimum": 1900,
          "maximum": 2030,
          "description": "Birth year (for age calculation)"
        },
        "throws": {
          "type": "string",
          "enum": ["right", "left", "both"],
          "description": "Throwing hand"
        },
        "position": {
          "type": "string",
          "description": "Primary position (pitcher, infielder, etc.)"
        },
        "email": {
          "type": "string",
          "format": "email",
          "description": "Contact email (optional, for facility communication)"
        }
      }
    },
    "sessions": {
      "type": "array",
      "description": "List of practice sessions",
      "items": {
        "type": "object",
        "required": ["session_id", "date", "pitches"],
        "properties": {
          "session_id": {
            "type": "string",
            "description": "Unique session ID (TAG Sports internal ID)"
          },
          "date": {
            "type": "string",
            "format": "date-time",
            "description": "Session date/time (ISO 8601)"
          },
          "location": {
            "type": "string",
            "description": "Free-text location (e.g., 'Backyard practice')"
          },
          "session_type": {
            "type": "string",
            "enum": ["practice", "bullpen", "game", "warmup", "other"],
            "description": "Type of session"
          },
          "notes": {
            "type": "string",
            "description": "Athlete's session notes"
          },
          "pitches": {
            "type": "array",
            "description": "Individual pitch measurements",
            "items": {
              "type": "object",
              "required": ["pitch_number", "timestamp", "speed_mph"],
              "properties": {
                "pitch_number": {
                  "type": "integer",
                  "minimum": 1,
                  "description": "Pitch number in session (1, 2, 3...)"
                },
                "timestamp": {
                  "type": "string",
                  "format": "date-time",
                  "description": "Pitch timestamp (ISO 8601)"
                },
                "speed_mph": {
                  "type": "number",
                  "minimum": 20,
                  "maximum": 120,
                  "description": "Measured pitch speed (mph)"
                },
                "pitch_type": {
                  "type": "string",
                  "description": "Athlete-tagged pitch type (e.g., 'Fastball', 'Curveball')"
                },
                "notes": {
                  "type": "string",
                  "description": "Pitch-specific notes"
                },
                "video_url": {
                  "type": "string",
                  "format": "uri",
                  "description": "Optional: URL to video recording (if TAG Sports stores video)"
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
                "description": "Total pitches in session"
              },
              "avg_speed_mph": {
                "type": "number",
                "description": "Average pitch speed"
              },
              "max_speed_mph": {
                "type": "number",
                "description": "Maximum pitch speed"
              },
              "min_speed_mph": {
                "type": "number",
                "description": "Minimum pitch speed"
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

### Example Export File

**File:** `TAG_export_john_doe_2026-03-20.json`

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
      "session_id": "tag_session_001",
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
          "pitch_type": "Fastball"
        }
      ],
      "summary": {
        "total_pitches": 45,
        "avg_speed_mph": 71.2,
        "max_speed_mph": 74.8,
        "min_speed_mph": 65.1
      }
    }
  ]
}
```

---

## PitchTracker Implementation

### Feature: Import TAG Sports Data

**Location:** `ui/coaching/dialogs/import_tag_data_dialog.py` (NEW)

**User Workflow:**
1. Operator clicks "Import TAG Sports Data" button (in Session Start Dialog or Team Manager)
2. Dialog opens: "Select TAG Sports export file"
3. User browses to JSON file (from email, USB, Downloads folder)
4. PitchTracker validates JSON against schema
5. If valid: Parse athlete info and session data
6. Create or update pitcher profile with TAG Sports data
7. Display confirmation: "Imported 3 sessions (145 pitches) for John Doe"
8. Show in "Practice History" tab

**UI Components:**
```
┌────────────────────────────────────────────────────┐
│  Import TAG Sports Practice Data                  │
├────────────────────────────────────────────────────┤
│                                                    │
│  Select TAG Sports export file:                   │
│  ┌────────────────────────────────────────┐       │
│  │ TAG_export_john_doe_2026-03-20.json  │ Browse │
│  └────────────────────────────────────────┘       │
│                                                    │
│  Preview:                                         │
│  ┌────────────────────────────────────────────┐  │
│  │ Athlete: John Doe (tag_abc123xyz)          │  │
│  │ Sessions: 3                                │  │
│  │ Total Pitches: 145                         │  │
│  │ Date Range: Mar 15-20, 2026                │  │
│  │ Avg Velocity: 71.4 mph                     │  │
│  │ Max Velocity: 76.2 mph                     │  │
│  └────────────────────────────────────────────┘  │
│                                                    │
│  Import to pitcher profile:                       │
│  ┌────────────────────────────────────────┐       │
│  │ Create new: John Doe              ▼   │       │
│  └────────────────────────────────────────┘       │
│  (or select existing profile)                     │
│                                                    │
│  [Cancel]                    [Import Data]        │
└────────────────────────────────────────────────────┘
```

**Validation:**
- Check schema_version = "1.0" (compatible)
- Validate all required fields present
- Validate pitch speeds in reasonable range (20-120 mph)
- Validate dates are valid ISO 8601
- Check for duplicate session imports (prevent re-importing same data)

**Error Handling:**
- Invalid JSON → Show error: "File is not valid TAG Sports export"
- Missing required fields → Show error: "Export file is incomplete (missing: X, Y, Z)"
- Corrupt data → Show error: "Export file is corrupted. Try exporting again from TAG Sports."
- Already imported → Show warning: "This data was already imported on [date]. Import again?"

---

### Data Storage (PitchTracker Side)

**Pitcher Profile Extension:**

Add TAG Sports data to existing pitcher profile:

```python
# contracts/types.py - Extend PitcherProfile

@dataclass
class TagSportsSession:
    """TAG Sports practice session data."""
    tag_session_id: str
    date: datetime
    location: str
    session_type: str  # practice, bullpen, game, warmup, other
    total_pitches: int
    avg_speed_mph: float
    max_speed_mph: float
    min_speed_mph: float
    pitches: List[TagSportsPitch]
    notes: str = ""

@dataclass
class TagSportsPitch:
    """Individual TAG Sports pitch."""
    pitch_number: int
    timestamp: datetime
    speed_mph: float
    pitch_type: str = ""  # athlete-tagged type
    notes: str = ""

@dataclass
class PitcherProfile:
    """Existing pitcher profile - EXTENDED."""
    pitcher_id: str
    name: str
    throws: str  # right, left, both
    birth_year: int
    # ... existing fields ...

    # NEW: TAG Sports integration
    tag_user_id: Optional[str] = None  # Link to TAG Sports account
    tag_sessions: List[TagSportsSession] = field(default_factory=list)
    tag_import_history: List[TagImportRecord] = field(default_factory=list)

@dataclass
class TagImportRecord:
    """Record of TAG Sports data import."""
    import_date: datetime
    sessions_imported: int
    pitches_imported: int
    date_range: Tuple[datetime, datetime]
    source_file: str
```

**Storage Location:** `data/pitchers/{pitcher_id}/tag_sports_history.json`

---

### UI Integration Points

#### 1. Session Start Dialog Enhancement

**Add Button:** "Import TAG Sports Data" (below "Select Pitcher")

**Workflow:**
1. Operator selects pitcher from dropdown
2. Clicks "Import TAG Sports Data" button
3. Import dialog opens (file browser)
4. Selects JSON file, clicks Import
5. Data validates and imports
6. Session Start Dialog shows: "✅ TAG Sports data imported (3 sessions, 145 pitches)"

---

#### 2. Pitcher Profile View Enhancement

**Add Tab:** "Practice History (TAG Sports)"

**Display:**
```
┌────────────────────────────────────────────────────┐
│  John Doe - Pitcher Profile                       │
├────────────────────────────────────────────────────┤
│  [Facility Sessions] [Practice History (TAG)]     │
├────────────────────────────────────────────────────┤
│                                                    │
│  Practice History (TAG Sports)                    │
│  ────────────────────────────────────────────     │
│                                                    │
│  📊 Summary (Last 30 Days)                        │
│   • Total Sessions: 12                            │
│   • Total Pitches: 487                            │
│   • Avg Velocity: 71.4 mph                        │
│   • Max Velocity: 76.2 mph                        │
│   • Velocity Trend: ↗ +1.3 mph/week              │
│                                                    │
│  📅 Recent Sessions                               │
│  ┌──────────────────────────────────────────────┐ │
│  │ Mar 20, 2026 - Backyard (45 pitches)        │ │
│  │ Avg: 71.2 mph | Max: 74.8 mph                │ │
│  │ Notes: Working on changeup grip              │ │
│  │ [View Details]                               │ │
│  └──────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │ Mar 18, 2026 - Local cage (52 pitches)      │ │
│  │ Avg: 70.8 mph | Max: 73.9 mph                │ │
│  │ [View Details]                               │ │
│  └──────────────────────────────────────────────┘ │
│  ┌──────────────────────────────────────────────┐ │
│  │ Mar 15, 2026 - Team practice (48 pitches)   │ │
│  │ Avg: 71.1 mph | Max: 75.2 mph                │ │
│  │ [View Details]                               │ │
│  └──────────────────────────────────────────────┘ │
│                                                    │
│  [Import More TAG Data]  [Export All Data]       │
└────────────────────────────────────────────────────┘
```

---

#### 3. Coach Dashboard Enhancement

**Add Panel:** "Athlete Practice Activity (TAG Sports)"

**Display in Coaching Session:**
```
┌────────────────────────────────────────────┐
│  🏠 Home Practice (TAG Sports)            │
├────────────────────────────────────────────┤
│  Last Session: Mar 20 (3 days ago)        │
│  Recent Avg: 71.4 mph (↗ trending up)     │
│  Total Pitches (30d): 487                  │
│                                            │
│  💡 Coaching Insight:                     │
│  Velocity up 1.3 mph/week in home         │
│  practice. Expecting similar gains in     │
│  facility training.                        │
└────────────────────────────────────────────┘
```

**Purpose:** Give coaches context about athlete's home practice before facility session starts.

---

#### 4. Analytics Dashboard Enhancement

**Add Comparison Chart:** "Facility vs. Practice Velocity Trends"

**Display:**
```
Velocity Over Time (Facility + Practice)
─────────────────────────────────────────
mph
75 │                              ●  (Facility)
   │                          ●  ●
   │                     ●
70 │    ○  ○  ○  ○  ○  ○           (Practice - TAG)
   │ ○
   │
65 │
   └────────────────────────────────────→ Date
    Mar 1        Mar 15        Mar 30

Legend:
● Facility sessions (PitchTracker 3D tracking)
○ Practice sessions (TAG Sports at-home)
```

**Insight:** "Athlete maintains 70-71 mph at home (TAG), improves to 73-75 mph at facility (PitchTracker). Facility training showing +3-4 mph velocity gains."

---

## PitchTracker Implementation Details

### File: `app/services/tag_sports_integration.py` (NEW)

```python
"""TAG Sports data integration service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional

from contracts.types import PitcherProfile
from loguru import logger


@dataclass
class TagSportsImportResult:
    """Result of TAG Sports data import."""
    success: bool
    athlete_name: str
    tag_user_id: str
    sessions_imported: int
    pitches_imported: int
    errors: List[str]
    warnings: List[str]


class TagSportsIntegrationService:
    """Service for importing TAG Sports practice data."""

    SUPPORTED_SCHEMA_VERSIONS = ["1.0"]

    def import_from_file(self, file_path: Path) -> TagSportsImportResult:
        """Import TAG Sports data from JSON export file.

        Args:
            file_path: Path to TAG Sports export JSON file

        Returns:
            Import result with success status and statistics

        Raises:
            ValueError: If file is invalid or schema unsupported
        """
        try:
            # Read and parse JSON
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)

            # Validate schema version
            schema_version = data.get("schema_version")
            if schema_version not in self.SUPPORTED_SCHEMA_VERSIONS:
                raise ValueError(
                    f"Unsupported schema version: {schema_version}. "
                    f"Supported: {self.SUPPORTED_SCHEMA_VERSIONS}"
                )

            # Validate required fields
            self._validate_required_fields(data)

            # Extract athlete info
            athlete = data["athlete"]
            sessions = data["sessions"]

            # Convert to PitchTracker format
            tag_sessions = self._convert_sessions(sessions)

            # Build result
            total_pitches = sum(s["summary"]["total_pitches"] for s in sessions if "summary" in s)

            return TagSportsImportResult(
                success=True,
                athlete_name=athlete["name"],
                tag_user_id=athlete["tag_user_id"],
                sessions_imported=len(sessions),
                pitches_imported=total_pitches,
                errors=[],
                warnings=[]
            )

        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON file: {e}")
            return TagSportsImportResult(
                success=False,
                athlete_name="",
                tag_user_id="",
                sessions_imported=0,
                pitches_imported=0,
                errors=[f"Invalid JSON file: {e}"],
                warnings=[]
            )
        except Exception as e:
            logger.exception(f"Import failed: {e}")
            return TagSportsImportResult(
                success=False,
                athlete_name="",
                tag_user_id="",
                sessions_imported=0,
                pitches_imported=0,
                errors=[str(e)],
                warnings=[]
            )

    def _validate_required_fields(self, data: dict) -> None:
        """Validate required fields in TAG Sports export."""
        required = ["schema_version", "export_metadata", "athlete", "sessions"]
        missing = [field for field in required if field not in data]
        if missing:
            raise ValueError(f"Missing required fields: {', '.join(missing)}")

        # Validate athlete required fields
        athlete = data["athlete"]
        athlete_required = ["tag_user_id", "name"]
        missing = [field for field in athlete_required if field not in athlete]
        if missing:
            raise ValueError(f"Missing athlete fields: {', '.join(missing)}")

    def _convert_sessions(self, sessions: List[dict]) -> List[TagSportsSession]:
        """Convert TAG Sports sessions to PitchTracker format."""
        # Implementation: Parse sessions, create TagSportsSession objects
        # Store in pitcher profile
        pass

    def merge_with_pitcher_profile(
        self,
        tag_data: TagSportsImportResult,
        pitcher_profile: PitcherProfile
    ) -> PitcherProfile:
        """Merge TAG Sports data into existing pitcher profile.

        Args:
            tag_data: Imported TAG Sports data
            pitcher_profile: Existing PitchTracker pitcher profile

        Returns:
            Updated pitcher profile with TAG Sports data
        """
        # Implementation: Append TAG sessions, update TAG user ID
        # Handle duplicate session detection (by date + pitch count)
        pass
```

---

### File: `ui/coaching/dialogs/import_tag_data_dialog.py` (NEW)

```python
"""Dialog for importing TAG Sports practice data."""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6 import QtWidgets, QtCore

from app.services.tag_sports_integration import TagSportsIntegrationService
from ui.themes import get_style_manager, show_message_dialog


class ImportTagDataDialog(QtWidgets.QDialog):
    """Dialog for importing TAG Sports export files."""

    import_completed = QtCore.Signal(str, int, int)  # (athlete_name, sessions, pitches)

    def __init__(self, parent: Optional[QtWidgets.QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("Import TAG Sports Practice Data")
        self.resize(600, 400)
        self._style_manager = get_style_manager()

        self._integration_service = TagSportsIntegrationService()
        self._selected_file: Optional[Path] = None
        self._import_result = None

        self._build_ui()

    def _build_ui(self) -> None:
        """Build dialog UI."""
        layout = QtWidgets.QVBoxLayout(self)

        # File selection
        file_group = QtWidgets.QGroupBox("Select TAG Sports Export File")
        file_layout = QtWidgets.QHBoxLayout()

        self._file_path_edit = QtWidgets.QLineEdit()
        self._file_path_edit.setReadOnly(True)
        self._file_path_edit.setPlaceholderText("No file selected")

        browse_btn = QtWidgets.QPushButton("Browse...")
        browse_btn.clicked.connect(self._browse_file)

        file_layout.addWidget(self._file_path_edit)
        file_layout.addWidget(browse_btn)
        file_group.setLayout(file_layout)

        # Preview area
        preview_group = QtWidgets.QGroupBox("Preview")
        preview_layout = QtWidgets.QVBoxLayout()

        self._preview_text = QtWidgets.QTextEdit()
        self._preview_text.setReadOnly(True)
        self._preview_text.setMaximumHeight(200)
        self._preview_text.setPlaceholderText(
            "Select a TAG Sports export file to preview data..."
        )

        preview_layout.addWidget(self._preview_text)
        preview_group.setLayout(preview_layout)

        # Buttons
        button_layout = QtWidgets.QHBoxLayout()
        button_layout.addStretch()

        cancel_btn = QtWidgets.QPushButton("Cancel")
        cancel_btn.clicked.connect(self.reject)

        self._import_btn = QtWidgets.QPushButton("Import Data")
        self._import_btn.clicked.connect(self._import_data)
        self._import_btn.setEnabled(False)
        self._style_manager.style_button(self._import_btn, "primary")

        button_layout.addWidget(cancel_btn)
        button_layout.addWidget(self._import_btn)

        # Main layout
        layout.addWidget(file_group)
        layout.addWidget(preview_group)
        layout.addLayout(button_layout)

    def _browse_file(self) -> None:
        """Browse for TAG Sports export file."""
        file_path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self,
            "Select TAG Sports Export File",
            str(Path.home() / "Downloads"),
            "TAG Sports Export (*.json);;All Files (*.*)"
        )

        if not file_path:
            return

        self._selected_file = Path(file_path)
        self._file_path_edit.setText(str(self._selected_file))

        # Preview file
        self._preview_file()

    def _preview_file(self) -> None:
        """Preview TAG Sports data from selected file."""
        if not self._selected_file:
            return

        try:
            # Attempt import (validation only, don't persist)
            result = self._integration_service.import_from_file(self._selected_file)

            if result.success:
                # Show preview
                preview_text = f"""
Athlete: {result.athlete_name}
TAG User ID: {result.tag_user_id}
Sessions: {result.sessions_imported}
Total Pitches: {result.pitches_imported}

✅ File is valid and ready to import.
"""
                self._preview_text.setPlainText(preview_text)
                self._import_btn.setEnabled(True)
                self._import_result = result

            else:
                # Show errors
                error_text = "❌ Import Failed:\n\n" + "\n".join(result.errors)
                self._preview_text.setPlainText(error_text)
                self._import_btn.setEnabled(False)

        except Exception as e:
            error_text = f"❌ Failed to read file:\n\n{str(e)}"
            self._preview_text.setPlainText(error_text)
            self._import_btn.setEnabled(False)

    def _import_data(self) -> None:
        """Import TAG Sports data into PitchTracker."""
        if not self._import_result or not self._import_result.success:
            return

        # TODO: Merge data into pitcher profile
        # TODO: Store import record

        show_message_dialog(
            self,
            "Import Successful",
            f"Imported {self._import_result.sessions_imported} sessions "
            f"({self._import_result.pitches_imported} pitches) for "
            f"{self._import_result.athlete_name}.",
            tone="success"
        )

        self.import_completed.emit(
            self._import_result.athlete_name,
            self._import_result.sessions_imported,
            self._import_result.pitches_imported
        )

        self.accept()
```

---

## TAG Sports Implementation (Recommended)

### Feature: Export to PitchTracker

**Location:** TAG Sports mobile app (iOS/Android)

**User Workflow:**
1. Athlete navigates to Profile or Sessions screen
2. Taps "Export to PitchTracker" button
3. App generates JSON export file
4. Share sheet appears: "Email, Save to Files, AirDrop, etc."
5. Athlete selects method (email to coach, save to iCloud, etc.)
6. Confirmation: "Data exported. Share this file with your facility coach."

**UI Mock:**
```
┌────────────────────────────────────┐
│  John Doe                          │
│  TAG Sports User Profile           │
├────────────────────────────────────┤
│                                    │
│  📊 Practice Stats (30 days)      │
│   • 12 sessions                    │
│   • 487 pitches                    │
│   • 71.4 mph avg                   │
│                                    │
│  ┌──────────────────────────────┐ │
│  │ Export to PitchTracker       │ │
│  │ Share your practice data     │ │
│  │ with your facility coach     │ │
│  └──────────────────────────────┘ │
│                                    │
│  Recent Sessions:                  │
│  • Mar 20 - Backyard (45 pitches) │
│  • Mar 18 - Cage (52 pitches)     │
│  • Mar 15 - Practice (48 pitches) │
└────────────────────────────────────┘
```

**Implementation Notes:**
- Generate JSON matching schema defined above
- Include last 90 days of sessions (balance detail vs. file size)
- File size estimate: ~50-100 KB for 90 days of data (minimal)
- Support email, iCloud, Google Drive, direct file sharing

---

## Testing & Validation

### Test Cases (PitchTracker Side)

**Unit Tests:**
- [ ] Valid TAG Sports JSON → successful import
- [ ] Invalid JSON → error message
- [ ] Missing required fields → error message
- [ ] Unsupported schema version → error message
- [ ] Duplicate session import → warning, skip duplicates
- [ ] Malformed data (invalid speeds, dates) → validation error

**Integration Tests:**
- [ ] Import TAG data → creates pitcher profile if new
- [ ] Import TAG data → merges with existing profile
- [ ] Import TAG data → displays in Practice History tab
- [ ] Import TAG data → shows in coach dashboard
- [ ] Import TAG data → appears in trend analysis charts

**UI Tests:**
- [ ] Import dialog opens from Session Start Dialog
- [ ] File browser filters .json files
- [ ] Preview shows correct athlete info
- [ ] Import button enables/disables correctly
- [ ] Error messages display properly

---

### Test Cases (TAG Sports Side - Recommended)

**Unit Tests:**
- [ ] Export generates valid JSON (passes schema validation)
- [ ] All required fields populated
- [ ] Date formats are ISO 8601
- [ ] Pitch speeds in valid range (20-120 mph)

**Integration Tests:**
- [ ] Export button appears in correct screens
- [ ] Export file generates within 2 seconds
- [ ] Share sheet appears with export file
- [ ] File can be emailed, saved, shared
- [ ] Re-exporting updates data (not duplicate)

---

## Security & Privacy

### Data Privacy Principles

1. **Athlete Consent Required:**
   - Athletes must explicitly consent to data export
   - TAG Sports app shows consent dialog before export
   - Athletes control who receives their data

2. **No Automatic Sync (MVP):**
   - Manual export/import only (athlete controls transfer)
   - No background data sharing without consent

3. **Data Minimization:**
   - Export only includes performance data (speed, dates, pitch counts)
   - No personal info beyond name, birth year, throwing hand
   - Email optional (athlete can omit)

4. **Facility Access Control:**
   - Only facilities where athlete enrolls can access data
   - No cross-facility data sharing without consent
   - Athletes can request data deletion from PitchTracker at any time

### Compliance Considerations

**COPPA (Children's Online Privacy Protection Act):**
- TAG Sports likely already COPPA-compliant (youth athletes)
- PitchTracker must also be COPPA-compliant if handling data from users <13
- Parental consent required for athletes under 13

**GDPR (if applicable):**
- Athletes have right to data export (already provided by TAG Sports)
- Athletes have right to data deletion (both platforms must honor)
- Data processing agreement between TAG Sports and PitchTracker

**CCPA (California):**
- California athletes have enhanced privacy rights
- Clear disclosure of data sharing between TAG and PitchTracker
- Opt-out mechanism if athlete doesn't want data shared

**Recommendation:** Consult with privacy attorney before public launch (cost: $2,000-5,000)

---

## Performance Considerations

### File Size Estimation

**Typical TAG Sports Export:**
- 90 days of practice sessions
- 10-15 sessions
- 30-50 pitches per session
- Total: 300-750 pitches

**JSON File Size:** ~50-100 KB (minimal)

**Import Performance:**
- Parse time: <100ms
- Validation time: <50ms
- Store time: <200ms
- **Total:** <500ms (fast, no noticeable delay)

### Storage Impact (PitchTracker Side)

**Per Pitcher with TAG Sports Data:**
- 90 days practice history: ~100 KB
- 1,000 pitchers: ~100 MB total
- **Impact:** Negligible (PitchTracker session data is GB-scale)

---

## Rollout Plan

### Phase 1: Internal Testing (Week 1-2)

- [ ] PitchTracker implements import feature
- [ ] Create sample TAG Sports export file (mock data)
- [ ] Test import workflow end-to-end
- [ ] UI/UX refinement

### Phase 2: TAG Sports Development (Week 3-4)

- [ ] TAG Sports implements export feature
- [ ] Both teams test with real TAG Sports app data
- [ ] Iterate on data format based on testing

### Phase 3: Beta Testing (Week 5-6)

- [ ] Recruit 5-10 athletes using TAG Sports + PitchTracker facilities
- [ ] Test export → import workflow
- [ ] Gather feedback, fix bugs

### Phase 4: Public Launch (Week 7-8)

- [ ] TAG Sports app update with export feature
- [ ] PitchTracker v1.6.0 with import feature
- [ ] Press release and co-marketing
- [ ] Monitor adoption and issues

---

## Success Criteria

### MVP Success (Month 3)

- [ ] TAG Sports export feature ships in app update
- [ ] PitchTracker import feature ships in v1.6.0
- [ ] 50+ athletes use export→import workflow
- [ ] <5% error rate (valid exports import successfully)
- [ ] Net Promoter Score ≥8 from athletes

### Partnership Success (Year 1)

- [ ] 100+ facilities with TAG integration
- [ ] 1,000+ athletes with unified profiles
- [ ] $50K+ referral revenue to TAG Sports
- [ ] $100K+ facility sales driven by TAG partnership
- [ ] 20%+ of new PitchTracker facilities cite TAG as decision factor

---

**Document Status:** READY FOR DEVELOPMENT (pending TAG Sports partnership approval)
**Owner:** Engineering Lead
**Next Action:** Await partnership MOU, begin implementation planning
**Last Updated:** March 26, 2026
