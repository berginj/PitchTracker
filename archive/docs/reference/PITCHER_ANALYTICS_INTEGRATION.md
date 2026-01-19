# PitcherAnalytics Integration Guide

**Integration between PitchTracker (desktop app) and PitcherAnalytics (web app)**

## Overview

This document describes how PitcherAnalytics (https://github.com/berginj/PitcherAnalytics) can receive and display pitch data from PitchTracker.

---

## Data Flow Architecture

```
┌─────────────────┐
│  PitchTracker   │
│  (Desktop App)  │
└────────┬────────┘
         │
         │ Records Sessions
         ├──────────────────────────────┐
         │                              │
         v                              v
┌─────────────────┐           ┌──────────────────┐
│  Local Storage  │           │  Cloud Storage   │
│  data/sessions/ │───────>   │  (Upload)        │
└─────────────────┘           └─────────┬────────┘
                                        │
                                        v
                              ┌──────────────────┐
                              │ PitcherAnalytics │
                              │  (Web App)       │
                              └──────────────────┘
```

---

## Data Locations

### PitchTracker Output Directory

**Default Location:** `C:\Users\{username}\App\PitchTracker\data\sessions\`

**Configurable in:** `configs/default.yaml` under `recording.session_dir`

### Session Directory Structure

```
data/sessions/
├── session-2026-01-16_001/
│   ├── manifest.json                    # Session metadata
│   ├── session_summary.json             # All pitches summary
│   ├── session_summary.csv              # CSV format summary
│   ├── session_left.avi                 # Full session left camera video
│   ├── session_right.avi                # Full session right camera video
│   ├── session_left_timestamps.csv      # Left camera frame timestamps
│   ├── session_right_timestamps.csv     # Right camera frame timestamps
│   │
│   ├── session-2026-01-16_001-pitch-001/
│   │   ├── manifest.json                # Pitch metadata & trajectory
│   │   ├── left.avi                     # Pitch video (left camera)
│   │   ├── right.avi                    # Pitch video (right camera)
│   │   ├── left_timestamps.csv          # Frame timestamps
│   │   └── right_timestamps.csv         # Frame timestamps
│   │
│   ├── session-2026-01-16_001-pitch-002/
│   │   └── ... (same structure)
│   │
│   └── ... (more pitches)
│
└── session-2026-01-16_002/
    └── ... (same structure)
```

---

## Data Formats

### 1. Session Manifest (`manifest.json`)

**Purpose:** Session-level metadata

```json
{
  "schema_version": "1.2.0",
  "app_version": "1.0.0",
  "rig_id": null,
  "created_utc": "2026-01-16T12:34:56Z",
  "pitch_id": "session-2026-01-16_001-pitch-020",
  "session": "session-2026-01-16_001",
  "mode": "bullpen",
  "measured_speed_mph": 85.5,
  "config_path": "configs/default.yaml",
  "calibration_profile_id": null,
  "session_summary": "session_summary.json",
  "session_summary_csv": "session_summary.csv",
  "session_left_video": "session_left.avi",
  "session_right_video": "session_right.avi",
  "session_left_timestamps": "session_left_timestamps.csv",
  "session_right_timestamps": "session_right_timestamps.csv"
}
```

### 2. Pitch Manifest (`{pitch_id}/manifest.json`)

**Purpose:** Individual pitch data with trajectory analysis

```json
{
  "schema_version": "1.2.0",
  "app_version": "1.0.0",
  "rig_id": null,
  "created_utc": "2026-01-16T12:35:22Z",
  "pitch_id": "session-2026-01-16_001-pitch-001",
  "t_start_ns": 1234567890000000,
  "t_end_ns": 1234568400000000,
  "is_strike": true,
  "zone_row": 1,
  "zone_col": 1,
  "run_in": 2.3,
  "rise_in": 1.7,
  "measured_speed_mph": 85.5,
  "rotation_rpm": 2200.0,
  "trajectory": {
    "plate_crossing_xyz_ft": [0.5, 2.8, 0.0],
    "plate_crossing_t_ns": 1234568200000000,
    "model": "physics_drag",
    "expected_error_ft": 0.08,
    "confidence": 0.95
  },
  "left_video": "left.avi",
  "right_video": "right.avi",
  "left_timestamps": "left_timestamps.csv",
  "right_timestamps": "right_timestamps.csv",
  "config_path": "configs/default.yaml",
  "performance_metrics": {
    "detection_quality": {
      "stereo_observations": 38,
      "detection_rate_hz": 30.2
    },
    "timing_accuracy": {
      "pre_roll_frames_captured": 15,
      "duration_ns": 510000000,
      "start_ns": 1234567890000000,
      "end_ns": 1234568400000000
    }
  }
}
```

### 3. Session Summary (`session_summary.json`)

**Purpose:** Aggregated statistics for all pitches in session

```json
{
  "session_id": "session-2026-01-16_001",
  "created_utc": "2026-01-16T12:34:56Z",
  "total_pitches": 20,
  "strikes": 14,
  "balls": 6,
  "strike_percentage": 70.0,
  "average_speed_mph": 84.2,
  "max_speed_mph": 88.5,
  "min_speed_mph": 80.1,
  "average_rotation_rpm": 2150.0,
  "pitches": [
    {
      "pitch_id": "session-2026-01-16_001-pitch-001",
      "timestamp_utc": "2026-01-16T12:35:22Z",
      "is_strike": true,
      "zone_row": 1,
      "zone_col": 1,
      "speed_mph": 85.5,
      "rotation_rpm": 2200.0,
      "run_in": 2.3,
      "rise_in": 1.7
    },
    {
      "pitch_id": "session-2026-01-16_001-pitch-002",
      "timestamp_utc": "2026-01-16T12:36:15Z",
      "is_strike": false,
      "zone_row": null,
      "zone_col": null,
      "speed_mph": 83.2,
      "rotation_rpm": 2050.0,
      "run_in": 3.1,
      "rise_in": 0.8
    }
  ]
}
```

### 4. Session Summary CSV (`session_summary.csv`)

**Purpose:** Spreadsheet-compatible summary

```csv
pitch_id,timestamp_utc,is_strike,zone_row,zone_col,speed_mph,rotation_rpm,run_in,rise_in
session-2026-01-16_001-pitch-001,2026-01-16T12:35:22Z,true,1,1,85.5,2200.0,2.3,1.7
session-2026-01-16_001-pitch-002,2026-01-16T12:36:15Z,false,,,83.2,2050.0,3.1,0.8
...
```

---

## Integration Methods

### Method 1: Local File System Access (Desktop Only)

**Use Case:** PitcherAnalytics runs as desktop Electron app

**Implementation:**
```javascript
// Node.js backend
const fs = require('fs');
const path = require('path');

// Default PitchTracker data directory
const dataDir = 'C:\\Users\\{username}\\App\\PitchTracker\\data\\sessions';

// Read all sessions
function loadSessions() {
  const sessions = fs.readdirSync(dataDir);
  return sessions.map(sessionId => {
    const manifestPath = path.join(dataDir, sessionId, 'manifest.json');
    const manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
    return {
      sessionId,
      manifest,
      summaryPath: path.join(dataDir, sessionId, manifest.session_summary)
    };
  });
}

// Read session summary
function loadSessionSummary(sessionId) {
  const summaryPath = path.join(dataDir, sessionId, 'session_summary.json');
  return JSON.parse(fs.readFileSync(summaryPath, 'utf8'));
}

// Read pitch data
function loadPitch(sessionId, pitchId) {
  const pitchDir = path.join(dataDir, sessionId, pitchId);
  const manifestPath = path.join(pitchDir, 'manifest.json');
  return JSON.parse(fs.readFileSync(manifestPath, 'utf8'));
}
```

---

### Method 2: Manual Upload (Web App)

**Use Case:** PitcherAnalytics is a web app, user manually uploads data

**Implementation:**

#### PitchTracker Export Script (Already Exists)

```powershell
# Export session data for web upload
python export_ml_submission.py `
  --session-dir "data\sessions\session-2026-01-16_001" `
  --output "session-export.zip" `
  --type telemetry_only `
  --pitcher-id "pitcher-123"
```

**Output:** ZIP file with:
- All manifest.json files
- session_summary.json/csv
- Calibration data
- NO videos (telemetry only)

#### Web App Upload Handler

```javascript
// Express.js backend
const multer = require('multer');
const upload = multer({ dest: 'uploads/' });
const unzipper = require('unzipper');

app.post('/api/upload-session', upload.single('sessionZip'), async (req, res) => {
  const zipPath = req.file.path;

  // Extract ZIP
  await fs.createReadStream(zipPath)
    .pipe(unzipper.Extract({ path: `sessions/${req.body.pitcher_id}` }))
    .promise();

  // Parse session data
  const manifest = JSON.parse(
    fs.readFileSync(`sessions/${req.body.pitcher_id}/manifest.json`, 'utf8')
  );

  const summary = JSON.parse(
    fs.readFileSync(`sessions/${req.body.pitcher_id}/session_summary.json`, 'utf8')
  );

  // Store in database
  await db.sessions.insert({
    pitcher_id: req.body.pitcher_id,
    session_id: manifest.session,
    created_utc: manifest.created_utc,
    total_pitches: summary.total_pitches,
    strike_percentage: summary.strike_percentage,
    average_speed_mph: summary.average_speed_mph
  });

  // Store pitch data
  for (const pitch of summary.pitches) {
    await db.pitches.insert({
      session_id: manifest.session,
      pitch_id: pitch.pitch_id,
      timestamp_utc: pitch.timestamp_utc,
      is_strike: pitch.is_strike,
      speed_mph: pitch.speed_mph,
      rotation_rpm: pitch.rotation_rpm,
      run_in: pitch.run_in,
      rise_in: pitch.rise_in
    });
  }

  res.json({ success: true, session_id: manifest.session });
});
```

---

### Method 3: Auto-Upload via API (Future)

**Use Case:** PitchTracker automatically uploads to web API

**Implementation:**

#### Add to PitchTracker (Future Enhancement)

```python
# app/pipeline/recording/cloud_sync.py (new file)

import requests
import json
from pathlib import Path

def upload_session(session_dir: Path, api_url: str, api_key: str):
    """Upload session data to PitcherAnalytics API."""

    # Read session data
    manifest_path = session_dir / "manifest.json"
    summary_path = session_dir / "session_summary.json"

    with open(manifest_path) as f:
        manifest = json.load(f)

    with open(summary_path) as f:
        summary = json.load(f)

    # Upload to API
    response = requests.post(
        f"{api_url}/api/sessions",
        headers={"Authorization": f"Bearer {api_key}"},
        json={
            "manifest": manifest,
            "summary": summary
        }
    )

    if response.status_code == 201:
        print(f"Session uploaded: {manifest['session']}")
        return response.json()
    else:
        raise Exception(f"Upload failed: {response.text}")
```

#### PitcherAnalytics API Endpoint

```javascript
// Express.js
app.post('/api/sessions', authenticateToken, async (req, res) => {
  const { manifest, summary } = req.body;

  // Validate schema
  if (manifest.schema_version !== '1.2.0') {
    return res.status(400).json({ error: 'Unsupported schema version' });
  }

  // Store session
  const session = await db.sessions.create({
    pitcher_id: req.user.pitcher_id,
    session_id: manifest.session,
    created_utc: manifest.created_utc,
    app_version: manifest.app_version,
    total_pitches: summary.total_pitches,
    strikes: summary.strikes,
    balls: summary.balls,
    strike_percentage: summary.strike_percentage,
    average_speed_mph: summary.average_speed_mph,
    max_speed_mph: summary.max_speed_mph
  });

  // Store pitches
  for (const pitch of summary.pitches) {
    await db.pitches.create({
      session_id: session.id,
      pitch_id: pitch.pitch_id,
      timestamp_utc: pitch.timestamp_utc,
      is_strike: pitch.is_strike,
      zone_row: pitch.zone_row,
      zone_col: pitch.zone_col,
      speed_mph: pitch.speed_mph,
      rotation_rpm: pitch.rotation_rpm,
      run_in: pitch.run_in,
      rise_in: pitch.rise_in
    });
  }

  res.status(201).json({ session_id: session.id });
});
```

---

## Database Schema for PitcherAnalytics

### Recommended Schema

```sql
-- Sessions table
CREATE TABLE sessions (
  id SERIAL PRIMARY KEY,
  pitcher_id VARCHAR(255) NOT NULL,
  session_id VARCHAR(255) UNIQUE NOT NULL,
  created_utc TIMESTAMP NOT NULL,
  app_version VARCHAR(50),
  mode VARCHAR(50),
  total_pitches INTEGER,
  strikes INTEGER,
  balls INTEGER,
  strike_percentage DECIMAL(5,2),
  average_speed_mph DECIMAL(5,2),
  max_speed_mph DECIMAL(5,2),
  min_speed_mph DECIMAL(5,2),
  average_rotation_rpm DECIMAL(7,2),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pitches table
CREATE TABLE pitches (
  id SERIAL PRIMARY KEY,
  session_id INTEGER REFERENCES sessions(id) ON DELETE CASCADE,
  pitch_id VARCHAR(255) UNIQUE NOT NULL,
  timestamp_utc TIMESTAMP NOT NULL,
  is_strike BOOLEAN,
  zone_row INTEGER,  -- 0-2
  zone_col INTEGER,  -- 0-2
  speed_mph DECIMAL(5,2),
  rotation_rpm DECIMAL(7,2),
  run_in DECIMAL(5,2),  -- Horizontal break (inches)
  rise_in DECIMAL(5,2), -- Vertical break (inches)
  plate_crossing_x_ft DECIMAL(6,3),
  plate_crossing_y_ft DECIMAL(6,3),
  plate_crossing_z_ft DECIMAL(6,3),
  trajectory_model VARCHAR(50),
  trajectory_confidence DECIMAL(4,3),
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Indexes for performance
CREATE INDEX idx_sessions_pitcher ON sessions(pitcher_id);
CREATE INDEX idx_sessions_created ON sessions(created_utc);
CREATE INDEX idx_pitches_session ON pitches(session_id);
CREATE INDEX idx_pitches_timestamp ON pitches(timestamp_utc);
```

---

## Example Queries

### Dashboard Statistics

```sql
-- Get pitcher summary
SELECT
  COUNT(DISTINCT s.session_id) as total_sessions,
  COUNT(p.id) as total_pitches,
  AVG(p.speed_mph) as avg_speed,
  MAX(p.speed_mph) as max_speed,
  AVG(p.rotation_rpm) as avg_spin,
  SUM(CASE WHEN p.is_strike THEN 1 ELSE 0 END)::FLOAT / COUNT(p.id) * 100 as strike_pct
FROM sessions s
JOIN pitches p ON p.session_id = s.id
WHERE s.pitcher_id = 'pitcher-123'
  AND s.created_utc >= NOW() - INTERVAL '30 days';

-- Heat map data (strike zone distribution)
SELECT
  zone_row,
  zone_col,
  COUNT(*) as pitch_count,
  AVG(speed_mph) as avg_speed
FROM pitches
WHERE session_id IN (
  SELECT id FROM sessions WHERE pitcher_id = 'pitcher-123'
)
  AND is_strike = true
GROUP BY zone_row, zone_col
ORDER BY zone_row, zone_col;

-- Speed trends over time
SELECT
  DATE(p.timestamp_utc) as date,
  AVG(p.speed_mph) as avg_speed,
  MAX(p.speed_mph) as max_speed,
  COUNT(*) as pitch_count
FROM pitches p
JOIN sessions s ON p.session_id = s.id
WHERE s.pitcher_id = 'pitcher-123'
GROUP BY DATE(p.timestamp_utc)
ORDER BY date;
```

---

## Frontend Components

### React Example: Session List

```jsx
// components/SessionList.jsx
import React, { useEffect, useState } from 'react';

function SessionList({ pitcherId }) {
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    fetch(`/api/pitchers/${pitcherId}/sessions`)
      .then(res => res.json())
      .then(data => setSessions(data));
  }, [pitcherId]);

  return (
    <div className="session-list">
      <h2>Training Sessions</h2>
      {sessions.map(session => (
        <div key={session.session_id} className="session-card">
          <h3>{new Date(session.created_utc).toLocaleDateString()}</h3>
          <div className="stats">
            <span>Pitches: {session.total_pitches}</span>
            <span>Strike%: {session.strike_percentage.toFixed(1)}%</span>
            <span>Avg Speed: {session.average_speed_mph.toFixed(1)} mph</span>
          </div>
          <button onClick={() => viewSession(session.session_id)}>
            View Details
          </button>
        </div>
      ))}
    </div>
  );
}
```

### React Example: Strike Zone Heat Map

```jsx
// components/StrikeZoneHeatMap.jsx
import React, { useEffect, useState } from 'react';

function StrikeZoneHeatMap({ sessionId }) {
  const [heatMapData, setHeatMapData] = useState([]);

  useEffect(() => {
    fetch(`/api/sessions/${sessionId}/heatmap`)
      .then(res => res.json())
      .then(data => setHeatMapData(data));
  }, [sessionId]);

  // Create 3x3 grid
  const grid = Array(3).fill(null).map(() => Array(3).fill(0));

  heatMapData.forEach(cell => {
    if (cell.zone_row !== null && cell.zone_col !== null) {
      grid[cell.zone_row][cell.zone_col] = cell.pitch_count;
    }
  });

  const maxCount = Math.max(...heatMapData.map(c => c.pitch_count));

  return (
    <div className="strike-zone">
      <h3>Strike Zone Heat Map</h3>
      <div className="zone-grid">
        {grid.map((row, rowIdx) => (
          <div key={rowIdx} className="zone-row">
            {row.map((count, colIdx) => (
              <div
                key={colIdx}
                className="zone-cell"
                style={{
                  backgroundColor: `rgba(33, 150, 243, ${count / maxCount})`
                }}
              >
                {count}
              </div>
            ))}
          </div>
        ))}
      </div>
      <div className="zone-labels">
        <span>Inside</span>
        <span>Middle</span>
        <span>Outside</span>
      </div>
    </div>
  );
}
```

---

## Testing the Integration

### 1. Generate Test Data

```powershell
# From PitchTracker
cd C:\Users\{username}\App\PitchTracker

# Run coaching app and record a test session
.\dist\PitchTracker\PitchTracker.exe

# Or use simulated backend for testing
python -m tests.integration.test_full_session
```

### 2. Export Session Data

```powershell
# Export for web upload
python export_ml_submission.py `
  --session-dir "data\sessions\session-2026-01-16_001" `
  --output "test-session.zip" `
  --type telemetry_only `
  --pitcher-id "test-pitcher"
```

### 3. Upload to PitcherAnalytics

```bash
# Test upload endpoint
curl -X POST http://localhost:3000/api/upload-session \
  -F "sessionZip=@test-session.zip" \
  -F "pitcher_id=test-pitcher"
```

### 4. Verify Data

```bash
# Get sessions
curl http://localhost:3000/api/pitchers/test-pitcher/sessions

# Get session details
curl http://localhost:3000/api/sessions/session-2026-01-16_001
```

---

## Troubleshooting

### Common Issues

**Issue:** "Schema version mismatch"
- **Solution:** Update PitcherAnalytics to support schema version 1.2.0
- **Check:** MANIFEST_SCHEMA.md in PitchTracker repository

**Issue:** "Missing fields in manifest"
- **Solution:** Older PitchTracker versions may not include all fields
- **Check:** `schema_version` field in manifest.json

**Issue:** "Cannot find session directory"
- **Solution:** Check `configs/default.yaml` for custom `recording.session_dir`
- **Default:** `data/sessions/`

**Issue:** "Videos are too large to upload"
- **Solution:** Use `--type telemetry_only` in export script
- **Alternative:** Store videos locally, upload only JSON/CSV

---

## Future Enhancements

### Phase 1: Manual Upload (Current)
- ✅ Export script exists
- ✅ ZIP file with telemetry data
- → Implement web upload UI

### Phase 2: Auto-Upload API
- Add cloud sync to PitchTracker
- Configure API endpoint in settings
- Auto-upload after each session

### Phase 3: Real-Time Sync
- WebSocket connection during session
- Live pitch updates in web dashboard
- Real-time coaching feedback

### Phase 4: Video Streaming
- Upload pitch videos (optionally)
- Video playback in web app
- Side-by-side comparison

---

## Contact

**PitchTracker Repository:** https://github.com/berginj/PitchTracker
**PitcherAnalytics Repository:** https://github.com/berginj/PitcherAnalytics

**Questions?** Open an issue in either repository.

---

**Schema Version:** 1.2.0
**Last Updated:** 2026-01-16
