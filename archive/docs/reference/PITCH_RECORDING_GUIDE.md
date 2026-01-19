# Pitch Recording & Training Guide

This guide covers what pitches to record, how to organize them, and how to use them for system training and validation.

## Pre-Recording Setup

### 1. Verify System is Ready
```bash
# Check calibration exists
python -c "from configs.settings import AppConfig; c=AppConfig.load(); print(f'Calibration loaded: baseline={c.stereo.baseline_ft:.3f}ft')"

# Test camera capture
python test_coaching_app.py  # Verify both cameras working
```

### 2. Prepare Recording Environment
- ✅ Good lighting (no shadows, even illumination)
- ✅ Clear background (no clutter in strike zone area)
- ✅ Cameras positioned at agreed angles
- ✅ Mound distance correct (60.5 ft for regulation)
- ✅ Strike zone properly positioned

## What Pitches to Record

### Target Distribution (100 pitches)

#### By Location (Primary Priority)
Record pitches across all strike zone locations:

**Grid Pattern (9 zones):**
```
High-Inside    High-Middle    High-Outside
[HI: 10]       [HM: 10]       [HO: 10]

Mid-Inside     Middle         Mid-Outside
[MI: 10]       [MM: 10]       [MO: 10]

Low-Inside     Low-Middle     Low-Outside
[LI: 10]       [LM: 10]       [LO: 10]

Just Outside (Balls)
[OUT: 10]
```

**Total: 100 pitches covering entire strike zone + edges**

#### By Velocity (Secondary Priority)
Mix of speeds across recordings:
- 🔴 **Hard (80+ mph):** 30 pitches
- 🟡 **Medium (70-80 mph):** 40 pitches
- 🟢 **Soft (60-70 mph):** 30 pitches

#### By Movement/Spin (Tertiary Priority)
If possible, vary:
- Fastballs (straight)
- Breaking balls (curves, sliders)
- Change-ups
- Different release points

**Note:** Focus first on location coverage, velocity second, movement third.

## Recording Protocol

### Before Each Session

1. **Launch coaching app:**
   ```bash
   python test_coaching_app.py
   ```

2. **Start session** with proper camera selection

3. **Verify preview:**
   - Both camera feeds visible
   - Strike zone overlay aligned
   - Ball clearly visible in both views

### During Recording

#### For Each Pitch:
1. **Announce target:** "High-inside, hard"
2. **Pitcher ready:** Wait for cameras to stabilize
3. **Throw pitch**
4. **Immediately note:**
   - Intended location
   - Estimated velocity
   - Whether it was a strike/ball
   - Any issues (missed detection, lighting problem, etc.)

#### Recording Log Template:
```
Pitch #, Intended Location, Velocity, Result, Notes
1, HI (High-Inside), Hard, Strike, Good detection
2, HM (High-Middle), Medium, Strike, Ball slightly blurred
3, OUT (Outside), Soft, Ball, Detection worked
...
```

**Save log as:** `recordings/session_YYYYMMDD_log.csv`

### Quality Criteria for Good Recordings

✅ **Good Recording:**
- Ball detected in BOTH cameras throughout flight
- No occlusions or obstructions
- Trajectory looks smooth
- Velocity seems reasonable
- Strike zone call makes sense

❌ **Bad Recording (mark for review):**
- Ball lost in one or both cameras
- Obvious detection errors (jumps, gaps)
- Weird velocity (too high/low)
- Trajectory doesn't make physical sense

### Handling Detection Failures

If ball not detected:
1. Note pitch number and issue
2. Check lighting - adjust if needed
3. Verify ball color contrast with background
4. Try throwing slightly slower
5. If persistent, mark camera location issue

**After 5 consecutive failures:** Stop and troubleshoot
- Check camera feeds for clarity
- Verify ROI zones still aligned
- Review calibration parameters

## Post-Recording Analysis

### 1. Initial Data Review (Same Day)

#### Count Successful Detections:
```bash
# Review session data
python -c "
from pathlib import Path
import json

# Look for recorded pitch data
session_dir = Path('recordings/session_YYYYMMDD')
if session_dir.exists():
    pitches = list(session_dir.glob('pitch_*.json'))
    print(f'Recorded: {len(pitches)} pitches')

    # Count complete detections (both cameras saw ball)
    complete = 0
    for p in pitches:
        data = json.load(p.open())
        if data.get('left_detections') and data.get('right_detections'):
            complete += 1

    print(f'Complete detections: {complete}/{len(pitches)} ({complete/len(pitches)*100:.1f}%)')
else:
    print('Session directory not found')
"
```

**Target:** >90% complete detection rate

#### Create Coverage Heatmap:
Check which zones are well-covered:
```
Zone Coverage:
HI: ████████░░ 8/10
HM: ██████████ 10/10
HO: ██████░░░░ 6/10
MI: ██████████ 10/10
MM: ██████████ 10/10
MO: ████████░░ 8/10
LI: ████░░░░░░ 4/10  ⚠️ Need more
LM: ██████████ 10/10
LO: ██████░░░░ 6/10
OUT: ██████████ 10/10
```

**Action:** Identify under-covered zones and plan additional recording session

### 2. Quality Analysis (Next Day)

#### Analyze Detection Accuracy:

**Create analysis script:**
```python
# analysis/review_recordings.py
from pathlib import Path
import json
import numpy as np

session = Path('recordings/session_20260117')
pitches = sorted(session.glob('pitch_*.json'))

results = {
    'total': len(pitches),
    'complete': 0,
    'velocities': [],
    'trajectories': [],
    'issues': []
}

for pitch_file in pitches:
    data = json.load(pitch_file.open())

    # Check completeness
    if data.get('left_detections') and data.get('right_detections'):
        results['complete'] += 1

        # Extract velocity
        if 'velocity_mph' in data:
            results['velocities'].append(data['velocity_mph'])

        # Check trajectory quality
        trajectory = data.get('trajectory_3d', [])
        if len(trajectory) < 10:
            results['issues'].append(f"{pitch_file.name}: Short trajectory ({len(trajectory)} points)")
    else:
        results['issues'].append(f"{pitch_file.name}: Incomplete detection")

# Statistics
print(f"Total Pitches: {results['total']}")
print(f"Complete Detections: {results['complete']} ({results['complete']/results['total']*100:.1f}%)")

if results['velocities']:
    velocities = np.array(results['velocities'])
    print(f"\nVelocity Stats:")
    print(f"  Mean: {velocities.mean():.1f} mph")
    print(f"  Std:  {velocities.std():.1f} mph")
    print(f"  Min:  {velocities.min():.1f} mph")
    print(f"  Max:  {velocities.max():.1f} mph")

if results['issues']:
    print(f"\nIssues Found: {len(results['issues'])}")
    for issue in results['issues'][:10]:  # Show first 10
        print(f"  - {issue}")
```

Run analysis:
```bash
python analysis/review_recordings.py
```

#### Validate Physical Plausibility:

Check for unrealistic values:
- **Velocity:** Should be 50-100 mph for typical pitchers
- **Release point:** Should be near mound location
- **Impact point:** Should be near strike zone height
- **Flight time:** Should be ~400-500ms for 60 ft

**Flag outliers for manual review**

### 3. Training Data Preparation

#### Organize by Quality Tiers:

**Tier 1 - Training Set (70 pitches):**
- Clean detection in both cameras
- Complete trajectory
- Reasonable velocity
- Covers all 9 zones

**Tier 2 - Validation Set (20 pitches):**
- Good quality
- Held out from training
- Test generalization

**Tier 3 - Test Set (10 pitches):**
- Best quality
- Final evaluation only
- Never used for tuning

#### Create Dataset Structure:
```
recordings/
├── dataset_20260117/
│   ├── train/
│   │   ├── high_inside/
│   │   │   ├── pitch_001.json
│   │   │   ├── pitch_001_left.mp4
│   │   │   └── pitch_001_right.mp4
│   │   ├── high_middle/
│   │   ├── ...
│   │   └── metadata.json
│   ├── val/
│   │   └── ...
│   └── test/
│       └── ...
```

#### Label Data:
For each pitch, create ground truth labels:
```json
{
  "pitch_id": "pitch_001",
  "timestamp": "2026-01-17T14:30:00",
  "labels": {
    "zone": "high_inside",
    "velocity_mph": 75.3,
    "release_point": [0.5, 6.2, 60.5],
    "strike": true,
    "detection_quality": "excellent",
    "notes": "Clean trajectory, good lighting"
  },
  "measurements": {
    "trajectory_3d": [...],
    "left_detections": [...],
    "right_detections": [...]
  }
}
```

## Training Use Cases

### 1. Detector Threshold Tuning

**Goal:** Optimize ball detection sensitivity

**Process:**
1. Run detector on training set with various thresholds
2. Measure precision/recall for ball detection
3. Find optimal threshold that maximizes F1 score
4. Validate on validation set

**Script template:**
```python
# training/tune_detector.py
thresholds = np.linspace(0.3, 0.9, 13)
results = []

for thresh in thresholds:
    detector.set_threshold(thresh)

    tp, fp, fn = 0, 0, 0
    for pitch in training_set:
        detected = detector.detect(pitch)
        ground_truth = pitch.labels['ball_positions']

        # Compare detected vs ground truth
        # ... calculate tp, fp, fn

    precision = tp / (tp + fp)
    recall = tp / (tp + fn)
    f1 = 2 * precision * recall / (precision + recall)

    results.append({'threshold': thresh, 'f1': f1, 'precision': precision, 'recall': recall})

# Find best threshold
best = max(results, key=lambda x: x['f1'])
print(f"Optimal threshold: {best['threshold']:.2f} (F1={best['f1']:.3f})")
```

### 2. Triangulation Accuracy Analysis

**Goal:** Measure 3D reconstruction error

**Process:**
1. For pitches with known trajectories (measured independently)
2. Compare PitchTracker 3D output to ground truth
3. Calculate RMS error in (x, y, z)
4. Identify systematic biases

### 3. Strike Zone Classification

**Goal:** Improve strike/ball accuracy

**Process:**
1. Use recorded pitches with manual strike/ball labels
2. Train classifier on trajectory endpoints
3. Evaluate on validation set
4. Adjust strike zone boundaries if needed

### 4. Velocity Estimation Calibration

**Goal:** Validate velocity measurements

**Process:**
1. Compare PitchTracker velocity to radar gun (if available)
2. Calculate bias and error
3. Apply calibration correction if needed

### 5. Robustness Testing

**Goal:** Find failure modes

**Test scenarios:**
- Different lighting conditions
- Various ball types/colors
- Partial occlusions
- Fast vs slow pitches
- Different trajectories

## Quality Benchmarks

After recording and analysis, aim for:

| Metric | Target | Excellent |
|--------|--------|-----------|
| Detection Rate | >85% | >95% |
| Velocity Accuracy | ±3 mph | ±1 mph |
| Location Accuracy | ±3 inches | ±1 inch |
| Strike Zone Accuracy | >90% | >95% |
| Complete Trajectories | >80% | >95% |

## Troubleshooting

### Low Detection Rate (<85%)

**Check:**
- Camera exposure settings
- Ball color contrast
- ROI zones properly aligned
- Lighting conditions
- Camera focus

### High Velocity Variance

**Check:**
- Frame rate stable at 30 FPS
- Timestamp synchronization
- Calibration baseline accurate
- Trajectory smoothing settings

### Poor Strike Zone Accuracy

**Check:**
- Strike zone dimensions correct
- ROI alignment to plate
- Triangulation calibration
- Release point detection

## Next Steps After Recording

1. **Immediate (Same Day):**
   - Review detection rate
   - Note any obvious issues
   - Back up recorded data

2. **Next Day:**
   - Run quality analysis
   - Identify coverage gaps
   - Plan additional recording if needed

3. **Within Week:**
   - Label training data
   - Run baseline accuracy tests
   - Document findings

4. **Ongoing:**
   - Use data for system improvements
   - Add to regression test suite
   - Compare against new recordings

## Data Management

### Backup Strategy:
```bash
# Compress session data
tar -czf recordings_20260117.tar.gz recordings/session_20260117/

# Copy to backup location
cp recordings_20260117.tar.gz /backup/pitchtracker/
```

### Version Control:
- Keep raw recordings separate from processed data
- Track analysis scripts in git
- Document any manual corrections
- Maintain chain of custody for labeled data

## Contact & Support

If you encounter issues:
- Check logs in `logs/pitchtracker.log`
- Review camera validation guide
- Document unexpected behavior
- Save problem recordings for debugging
