# Pattern Detection System - User Guide

## Overview

The Pattern Detection System analyzes recorded pitch videos to automatically detect pitch types and anomalies. It provides comprehensive insights into pitcher performance, consistency, and mechanics through statistical analysis.

## Features

### Pitch Type Classification
- **Heuristic Rules**: MLB-standard classification (Fastball, Slider, Curveball, Changeup, etc.)
- **K-means Clustering**: Automatic discovery of pitcher-specific patterns
- **Hybrid Approach**: Combines both methods for robust classification

### Anomaly Detection
- **Speed Anomalies**: Unusual fast/slow pitches (Z-score + IQR methods)
- **Movement Anomalies**: Unusual horizontal/vertical break
- **Trajectory Quality**: Poor detection quality, insufficient samples
- **Multi-method Validation**: High-confidence detection using ensemble

### Pitcher Profiles
- **Baseline Metrics**: Velocity, movement, strike percentage distributions
- **Comparison**: Compare current session to pitcher's baseline
- **Opt-in**: Profiles created explicitly by user (privacy-respecting)
- **Storage**: `configs/pitcher_profiles/{pitcher_id}.json`

### Reports
- **JSON**: Machine-readable with complete analysis data
- **HTML**: Visual report with embedded charts (velocity, movement, heatmap, repertoire)
- **Self-contained**: No external dependencies, works offline

## Quick Start

### UI Workflow (Recommended)

**NEW (2026-01-19):** Pattern detection is now integrated into the UI! No command-line knowledge required.

1. **Record a pitching session** (existing workflow)
2. **Click "Analyze Patterns"** in the Session Summary dialog
3. **Click "Run Analysis"** in the Pattern Analysis dialog
4. **View results** across 4 tabs:
   - **Summary**: Pitch counts, velocity, strikes, consistency, repertoire
   - **Anomalies**: Unusual pitches with recommendations
   - **Pitch Types**: Classification results with confidence scores
   - **Baseline**: Comparison to pitcher's historical performance (if profile exists)
5. **Optional actions**:
   - Click "Open HTML Report" to view charts in browser
   - Click "Export JSON" to save analysis data
   - Click "Create Pitcher Profile" to track this pitcher over time

**Time:** ~30 seconds from session end to viewing results ⚡

---

### CLI Workflow (Advanced)

For automated workflows, scripting, or batch processing:

```bash
# Basic analysis
python -m analysis.cli analyze-session --session recordings/session-2026-01-19_001

# With baseline comparison
python -m analysis.cli analyze-session --session recordings/session-2026-01-19_001 --pitcher john_doe
```

**Output:**
- `recordings/session-2026-01-19_001/analysis_report.json`
- `recordings/session-2026-01-19_001/analysis_report.html`

### Create Pitcher Profile

**UI Method** (easiest):
1. Click "Analyze Patterns" on any session
2. Click "Create Pitcher Profile" button
3. Enter pitcher name
4. Profile created and baseline comparison appears on next analysis

**CLI Method** (for batch creation from multiple sessions):
```bash
# Create profile from multiple sessions
python -m analysis.cli create-profile --pitcher john_doe --sessions "recordings/session-2026-01-*"

# Profile saved to: configs/pitcher_profiles/john_doe.json
```

### List Profiles

**UI Method**: Saved profiles appear in coaching session start dialog

**CLI Method**:
```bash
python -m analysis.cli list-profiles
```

## When to Use UI vs CLI

### Use UI When:
- ✅ You're a coach analyzing sessions after practice
- ✅ You want instant visual feedback with charts
- ✅ You're not familiar with command-line tools
- ✅ You want one-click analysis workflow
- ✅ You prefer interactive exploration of results

### Use CLI When:
- ✅ You're analyzing many sessions at once (batch processing)
- ✅ You're automating analysis in scripts
- ✅ You want to integrate analysis into other workflows
- ✅ You're analyzing sessions from another computer
- ✅ You need programmatic access to analysis results

**Recommendation:** Start with the UI. Use CLI only if you need automation or batch processing.

## Report Contents

### Executive Summary
- Total pitches analyzed
- Anomalies detected count
- Pitch types identified
- Average velocity
- Strike percentage

### Pitch Classification
- Repertoire breakdown (pie chart)
- Pitch type percentages
- Average velocity per type
- Movement characteristics

### Anomaly Report
- Pitch ID and type
- Severity (low, medium, high)
- Detailed diagnostics
- Recommendations for each anomaly

### Visualizations
1. **Velocity Chart**: Pitch-by-pitch velocity with anomalies highlighted
2. **Movement Chart**: Scatter plot of run_in vs rise_in, colored by pitch type
3. **Strike Zone Heatmap**: 3×3 grid showing location distribution
4. **Repertoire Pie Chart**: Pitch type distribution

### Baseline Comparison (if profile exists)
- Current vs baseline velocity
- Current vs baseline strike percentage
- Status indicators (normal, slightly above/below, significantly above/below)

## Data Requirements

**Minimum Requirements:**
- 5 pitches for single-session analysis
- 10 pitches for cross-session trends
- Complete pitch data: velocity, movement (run_in, rise_in), trajectory

**Graceful Degradation:**
- If < 5 pitches: Error report with recommendations
- If missing velocity: Labeled as "Unknown", skip velocity analysis
- If missing movement: Speed-only classification
- If no profile: Skip baseline comparison (not an error)

## Performance

| Component | 100 Pitches | 1000 Pitches |
|-----------|-------------|--------------|
| Classification | <1ms | <10ms |
| Anomaly Detection | <5ms | <50ms |
| JSON Generation | <5ms | <50ms |
| HTML + Charts | 50-100ms | 500-1000ms |
| **TOTAL** | **<120ms** | **<1200ms** |

**Target Met**: < 5 seconds for 100 pitches (actual: 0.12s)

## Algorithms

### Pitch Type Classification (Heuristic Rules)

```
Fastball (4-seam):  88+ mph, low movement (<5in total)
Sinker (2-seam):    88+ mph, downward + arm-side run
Cutter:             88+ mph, lateral break (>4in)
Slider:             80-88 mph, lateral break (>5in)
Curveball:          70-80 mph, downward break (<-3in rise)
Changeup:           75-85 mph, moderate downward (-1 to -4in)
```

### Anomaly Detection Thresholds

```
Z-score:            |z| > 3.0 (statistical outlier)
IQR:                Outside [Q1 - 1.5×IQR, Q3 + 1.5×IQR]
RMSE:               > 0.5 ft (trajectory error)
Inlier Ratio:       < 0.7 (too many outliers)
Sample Count:       < 10 (insufficient detections)
```

## Troubleshooting

### "Session summary not found"
- Ensure you're pointing to the correct session directory
- Check that `session_summary.json` exists in the directory

### "Insufficient data" error
- Record at least 5 pitches for analysis
- Use cross-session analysis if individual sessions are too short

### "No pitcher profile found"
- Create a profile first using `create-profile` command
- Profile must exist before baseline comparison

### Charts not displaying in HTML
- Charts are embedded as base64 PNG images
- Open HTML file in any modern web browser
- No internet connection required

## Command Reference

### analyze-session

```bash
python -m analysis.cli analyze-session \
    --session <path_to_session> \
    [--pitcher <pitcher_id>] \
    [--no-json] \
    [--no-html]
```

**Options:**
- `--session`: Path to session directory (required)
- `--pitcher`: Pitcher ID for baseline comparison (optional)
- `--no-json`: Skip JSON report generation
- `--no-html`: Skip HTML report generation

### create-profile

```bash
python -m analysis.cli create-profile \
    --pitcher <pitcher_id> \
    --sessions <pattern1> [<pattern2> ...]
```

**Options:**
- `--pitcher`: Pitcher ID (required)
- `--sessions`: Session directories or glob patterns (required, supports multiple)

**Examples:**
```bash
# Single session
python -m analysis.cli create-profile --pitcher john_doe --sessions recordings/session-001

# Multiple sessions (explicit)
python -m analysis.cli create-profile --pitcher john_doe --sessions recordings/session-001 recordings/session-002

# Glob pattern
python -m analysis.cli create-profile --pitcher john_doe --sessions "recordings/session-2026-01-*"
```

### list-profiles

```bash
python -m analysis.cli list-profiles
```

No options. Lists all available pitcher profiles with summary information.

## Advanced Usage

### Programmatic Access

```python
from pathlib import Path
from analysis.pattern_detection.detector import PatternDetector

# Initialize detector
detector = PatternDetector()

# Analyze session
session_dir = Path("recordings/session-2026-01-19_001")
report = detector.analyze_session(
    session_dir,
    pitcher_id="john_doe",
    output_json=True,
    output_html=True
)

# Access report data
print(f"Total pitches: {report.summary.total_pitches}")
print(f"Anomalies: {report.summary.anomalies_detected}")

# Create profile programmatically
detector.create_pitcher_profile(
    pitcher_id="john_doe",
    session_dirs=[Path("recordings/session-001"), Path("recordings/session-002")]
)
```

### Custom Thresholds

```python
# Adjust anomaly detection sensitivity
detector = PatternDetector(
    z_threshold=2.5,      # More sensitive (default: 3.0)
    iqr_multiplier=2.0    # Less sensitive (default: 1.5)
)
```

### Cross-Session Analysis

```bash
python -m analysis.cli analyze-sessions --sessions "recordings\session-2026-01-*"

# With custom output directory
python -m analysis.cli analyze-sessions --sessions "recordings\session-*" --output analysis_results
```

**Output:**
- `recordings\cross_session_analysis_2026-01-19.json`

**Analyses:**
- **Velocity Trends**: Linear regression on average velocity across sessions with trend direction
- **Strike Consistency**: Strike percentage and zone distribution tracking
- **Pitch Mix Evolution**: Pitch type distribution changes over time

## Future Enhancements

**Planned (not yet implemented):**
- Real-time pattern detection during live capture
- Advanced ML models for pitch classification
- Video replay integration
- Multi-pitcher comparison
- PDF export
- Cloud sync

**Current Status**: Phases 1-5 complete (Core algorithms, Profile management, Report generation, CLI integration, Cross-session analysis)

## Support

For issues or questions:
- Check `docs/COACHING_UI_REDESIGN.md` for related documentation
- Review session logs for error messages
- Ensure session data is complete (session_summary.json)

## Technical Details

**Architecture:**
- Pure statistical analysis (no ML inference)
- Modular design (classifier, anomaly detector, report generator separate)
- Opt-in pitcher profiles (privacy-respecting)
- Graceful degradation with missing data
- Fast performance (<120ms for 100 pitches)

**Data Sources:**
- `session_summary.json`: Pitch summaries
- `pitch_###/manifest.json`: Trajectory diagnostics
- `pitcher_profiles/*.json`: Baseline profiles

**Output Locations:**
- `recordings/{session}/analysis_report.json`
- `recordings/{session}/analysis_report.html`
- `configs/pitcher_profiles/{pitcher_id}.json`
