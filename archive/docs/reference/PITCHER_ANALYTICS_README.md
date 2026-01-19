# PitcherAnalytics - README for Web App Team

**Quick reference for integrating with PitchTracker data**

## Overview

PitcherAnalytics receives pitch tracking data from PitchTracker (desktop app) and displays analytics in a web interface.

---

## Quick Start

### 1. Understand the Data Format

PitchTracker generates JSON files with this structure:

```
session-2026-01-16_001/
├── manifest.json           # Session metadata
├── session_summary.json    # All pitches aggregated
├── session_summary.csv     # CSV version
└── pitch-001/
    └── manifest.json       # Individual pitch data
```

**Full spec:** See `PITCHER_ANALYTICS_INTEGRATION.md` in PitchTracker repo

---

### 2. Get Test Data

**Option A: Generate from PitchTracker**
```powershell
# Export session data
python export_ml_submission.py \
  --session-dir "data/sessions/session-2026-01-16_001" \
  --output "test-data.zip" \
  --type telemetry_only \
  --pitcher-id "test-pitcher"
```

**Option B: Use Sample Data (create manually)**

`sample-session/manifest.json`:
```json
{
  "schema_version": "1.2.0",
  "session": "sample-session",
  "created_utc": "2026-01-16T12:00:00Z",
  "mode": "bullpen",
  "session_summary": "session_summary.json"
}
```

`sample-session/session_summary.json`:
```json
{
  "session_id": "sample-session",
  "total_pitches": 3,
  "strikes": 2,
  "balls": 1,
  "strike_percentage": 66.7,
  "average_speed_mph": 85.0,
  "pitches": [
    {
      "pitch_id": "sample-pitch-001",
      "timestamp_utc": "2026-01-16T12:01:00Z",
      "is_strike": true,
      "zone_row": 1,
      "zone_col": 1,
      "speed_mph": 87.0,
      "rotation_rpm": 2200,
      "run_in": 2.5,
      "rise_in": 1.8
    },
    {
      "pitch_id": "sample-pitch-002",
      "timestamp_utc": "2026-01-16T12:02:00Z",
      "is_strike": true,
      "zone_row": 0,
      "zone_col": 2,
      "speed_mph": 85.0,
      "rotation_rpm": 2150,
      "run_in": 3.1,
      "rise_in": 0.9
    },
    {
      "pitch_id": "sample-pitch-003",
      "timestamp_utc": "2026-01-16T12:03:00Z",
      "is_strike": false,
      "zone_row": null,
      "zone_col": null,
      "speed_mph": 83.0,
      "rotation_rpm": 2000,
      "run_in": 4.2,
      "rise_in": -0.5
    }
  ]
}
```

---

### 3. Database Schema

**PostgreSQL recommended:**

```sql
CREATE TABLE sessions (
  id SERIAL PRIMARY KEY,
  pitcher_id VARCHAR(255),
  session_id VARCHAR(255) UNIQUE,
  created_utc TIMESTAMP,
  total_pitches INTEGER,
  strikes INTEGER,
  balls INTEGER,
  strike_percentage DECIMAL(5,2),
  average_speed_mph DECIMAL(5,2)
);

CREATE TABLE pitches (
  id SERIAL PRIMARY KEY,
  session_id INTEGER REFERENCES sessions(id),
  pitch_id VARCHAR(255) UNIQUE,
  timestamp_utc TIMESTAMP,
  is_strike BOOLEAN,
  zone_row INTEGER,
  zone_col INTEGER,
  speed_mph DECIMAL(5,2),
  rotation_rpm DECIMAL(7,2),
  run_in DECIMAL(5,2),
  rise_in DECIMAL(5,2)
);
```

---

### 4. API Endpoint Example

**Express.js:**

```javascript
// POST /api/upload-session
const multer = require('multer');
const upload = multer({ dest: 'uploads/' });
const unzipper = require('unzipper');

app.post('/api/upload-session', upload.single('sessionZip'), async (req, res) => {
  const zipPath = req.file.path;

  // Extract ZIP
  await fs.createReadStream(zipPath)
    .pipe(unzipper.Extract({ path: `temp/${req.body.pitcher_id}` }))
    .promise();

  // Parse session data
  const summary = JSON.parse(
    fs.readFileSync(`temp/${req.body.pitcher_id}/session_summary.json`, 'utf8')
  );

  // Store in database
  const session = await db.sessions.create({
    pitcher_id: req.body.pitcher_id,
    session_id: summary.session_id,
    total_pitches: summary.total_pitches,
    strike_percentage: summary.strike_percentage,
    average_speed_mph: summary.average_speed_mph
  });

  // Store pitches
  for (const pitch of summary.pitches) {
    await db.pitches.create({
      session_id: session.id,
      pitch_id: pitch.pitch_id,
      is_strike: pitch.is_strike,
      speed_mph: pitch.speed_mph,
      // ... other fields
    });
  }

  res.json({ success: true, session_id: session.id });
});
```

---

### 5. Frontend Components

**React - Session List:**

```jsx
function SessionList({ pitcherId }) {
  const [sessions, setSessions] = useState([]);

  useEffect(() => {
    fetch(`/api/pitchers/${pitcherId}/sessions`)
      .then(res => res.json())
      .then(data => setSessions(data));
  }, [pitcherId]);

  return (
    <div>
      {sessions.map(s => (
        <div key={s.session_id}>
          <h3>{new Date(s.created_utc).toLocaleDateString()}</h3>
          <p>Pitches: {s.total_pitches}</p>
          <p>Strike%: {s.strike_percentage}%</p>
          <p>Avg Speed: {s.average_speed_mph} mph</p>
        </div>
      ))}
    </div>
  );
}
```

**React - Strike Zone Heat Map:**

```jsx
function StrikeZoneHeatMap({ sessionId }) {
  const [heatMap, setHeatMap] = useState([]);

  useEffect(() => {
    fetch(`/api/sessions/${sessionId}/heatmap`)
      .then(res => res.json())
      .then(data => setHeatMap(data));
  }, [sessionId]);

  // Create 3x3 grid
  const grid = Array(3).fill().map(() => Array(3).fill(0));
  heatMap.forEach(cell => {
    grid[cell.zone_row][cell.zone_col] = cell.pitch_count;
  });

  return (
    <div className="strike-zone">
      {grid.map((row, i) => (
        <div key={i} className="row">
          {row.map((count, j) => (
            <div key={j} className="cell">{count}</div>
          ))}
        </div>
      ))}
    </div>
  );
}
```

---

### 6. Testing

```bash
# Test upload endpoint
curl -X POST http://localhost:3000/api/upload-session \
  -F "sessionZip=@test-data.zip" \
  -F "pitcher_id=test-pitcher"

# Verify data
curl http://localhost:3000/api/pitchers/test-pitcher/sessions
```

---

## Data Fields Reference

### Key Metrics

| Field | Type | Description |
|-------|------|-------------|
| `speed_mph` | float | Pitch velocity (mph) |
| `rotation_rpm` | float | Spin rate (RPM) |
| `run_in` | float | Horizontal break (inches, + = right) |
| `rise_in` | float | Vertical break (inches, + = up) |
| `is_strike` | boolean | Crossed strike zone? |
| `zone_row` | 0-2 | Strike zone row (0=top, 1=middle, 2=bottom) |
| `zone_col` | 0-2 | Strike zone column (0=inside, 1=middle, 2=outside) |

### Strike Zone Grid

```
      Inside(0)  Middle(1)  Outside(2)
Top(0)    0,0       0,1        0,2
Mid(1)    1,0       1,1        1,2
Bot(2)    2,0       2,1        2,2
```

---

## Complete Documentation

**Full integration guide:**
https://github.com/berginj/PitchTracker/blob/main/PITCHER_ANALYTICS_INTEGRATION.md

**Includes:**
- Complete data format specifications
- Database schema recommendations
- Multiple integration methods (local, upload, API)
- Frontend component examples
- Troubleshooting guide

---

## Quick Wins

### 1. Dashboard Stats (Easy)
- Total pitches
- Strike percentage
- Average speed
- Speed trends over time

### 2. Strike Zone Heat Map (Easy)
- 3x3 grid visualization
- Color intensity by pitch count
- Filter by date range

### 3. Pitch Charts (Medium)
- Speed vs spin scatter plot
- Movement plots (run vs rise)
- Time series of velocity

### 4. Session Comparison (Medium)
- Compare multiple sessions
- Track improvement over time
- Identify patterns

---

## Next Steps

1. **Set up database** (PostgreSQL recommended)
2. **Create upload endpoint** (see example above)
3. **Test with sample data** (use sample JSON above)
4. **Build dashboard UI** (React components above)
5. **Deploy and test** with real PitchTracker data

---

## Questions?

**PitchTracker Repo:** https://github.com/berginj/PitchTracker
**Full Integration Guide:** PITCHER_ANALYTICS_INTEGRATION.md
**Data Schema Spec:** MANIFEST_SCHEMA.md

---

**TL;DR:** PitchTracker exports ZIP files with JSON data. Your web app:
1. Accepts ZIP upload
2. Extracts `session_summary.json`
3. Stores in database
4. Displays analytics dashboard

**Start here:** Create sample data (see section 2), build upload endpoint (section 4), test (section 6).
