# Cloud Submission Quick Guide

> **TL;DR:** Package your PitchTracker sessions for cloud ML training. Two options: Full (videos + data, trains all models) or Telemetry-only (data only, privacy-preserving, trains 2 of 5 models).

---

## Quick Decision Tree

```
Do you want to train visual ML models (ball detector, field segmentation, pose)?
├─ YES → Use FULL package
│         ✓ Enables all 5 automation models
│         ✓ 95% setup time reduction achievable
│         ⚠ Requires player consent for video
│         Size: ~4-5 GB per session
│
└─ NO  → Use TELEMETRY-ONLY package
          ✓ Privacy-preserving (no player visuals)
          ✓ Enables trajectory + calibration models
          ✗ Cannot train visual models
          Size: ~50-100 MB per session (50x smaller)
```

---

## Two Submission Variants

### Variant 1: Full Package (Recommended for Initial Data Collection)

**What's Included:**
- ✅ Session videos (continuous recording)
- ✅ Pitch videos (individual clips)
- ✅ Key frames (PNG at critical moments)
- ✅ All detections (pixel coordinates)
- ✅ All observations (3D trajectory)
- ✅ Calibration metadata
- ✅ Performance metrics

**ML Models Enabled:**
1. ✅ Ball detector (eliminate HSV tuning)
2. ✅ Field segmentation (auto-detect ROIs)
3. ✅ Batter pose estimation (auto-calculate strike zone)
4. ✅ Trajectory models
5. ✅ Self-calibration

**Result:** 100% of 18-month automation roadmap enabled

**Size:** ~4-5 GB per session (20 pitches)

**Privacy:** Requires player consent, video shows player/facility

### Variant 2: Telemetry-Only (Privacy-Preserving)

**What's Included:**
- ✅ All detections (pixel coordinates, NO frames)
- ✅ All observations (3D trajectory)
- ✅ Calibration metadata
- ✅ Performance metrics
- ❌ Session videos
- ❌ Pitch videos
- ❌ Key frame images

**ML Models Enabled:**
1. ❌ Ball detector (requires video)
2. ❌ Field segmentation (requires video)
3. ❌ Batter pose estimation (requires video)
4. ✅ Trajectory models
5. ✅ Self-calibration

**Result:** 40% of automation roadmap enabled (2 of 5 models)

**Size:** ~50-100 MB per session (50x smaller)

**Privacy:** No player visuals, only numeric data

---

## When to Use Which Variant

### Use FULL Package When:

✅ **Training all automation models is priority**
- Need ball detector to eliminate HSV tuning
- Need field segmentation to auto-detect ROIs
- Need pose estimation to auto-calculate strike zone
- Want maximum setup time reduction (30 min → <2 min)

✅ **Player consent obtained for video sharing**
- Player agrees to video use for ML training
- Consent documents signed and stored
- Privacy policy reviewed and accepted

✅ **Bandwidth and storage available**
- Network can handle 4-5 GB uploads
- Cloud storage budget allows larger files
- Upload time acceptable (~30 min on fast connection)

✅ **Privacy concerns addressed**
- Face blurring implemented if needed
- Facility branding acceptable
- Retention limits agreed upon

**Expected Outcome:** Complete automation roadmap in 18 months, 95% setup time reduction

### Use TELEMETRY-ONLY When:

✅ **Privacy is highest priority**
- Player prefers no video sharing
- Facility does not allow video recording
- Privacy policy restricts visual data
- Only coaching videos retained locally

✅ **Bandwidth or storage limited**
- Slow internet connection (50x faster upload)
- Cloud storage budget constraints
- Need to submit many sessions quickly

✅ **Only trajectory/calibration models needed**
- Already have working ball detector
- Manual ROI/strike zone acceptable
- Focus on trajectory accuracy improvement
- Calibration refinement priority

✅ **After visual models trained**
- Ball detector already trained from other data
- Field segmentation model available
- Pose estimation model available
- Now collecting data for model improvement only

**Expected Outcome:** Trajectory accuracy and calibration improvements, but manual setup remains for visual tasks

---

## Export Commands

### Full Package Export

```powershell
python export_ml_submission.py \
  --session-dir "recordings\session-2026-01-16_001" \
  --output "ml-submission-full.zip" \
  --type full \
  --pitcher-id "anonymous-123" \
  --location "Indoor Facility A" \
  --player-consent
```

**Output:**
```
Collecting files for full submission...
Total size: 4327.8 MB
Total files: 1247
Creating ZIP package: ml-submission-full.zip
  Added 1247 files...
Package created: ml-submission-full.zip
Calculating checksum...
SHA256: abc123...
Creating submission manifest...

✓ ML submission package complete!
  Type: full
  Size: 4327.8 MB
  Files: 1247
  Package: ml-submission-full.zip
  Manifest: ml-submission-full.manifest.json

  Enables: All 5 ML models (100% of automation roadmap)
    ✓ Ball detector
    ✓ Field segmentation
    ✓ Batter pose estimation
    ✓ Trajectory models
    ✓ Self-calibration
```

### Telemetry-Only Export

```powershell
python export_ml_submission.py \
  --session-dir "recordings\session-2026-01-16_001" \
  --output "ml-submission-telemetry.zip" \
  --type telemetry_only \
  --pitcher-id "anonymous-123" \
  --location "Indoor Facility A" \
  --reason privacy_preserving \
  --player-consent \
  --anonymized
```

**Output:**
```
Collecting files for telemetry_only submission...
Total size: 87.3 MB
Total files: 142
Creating ZIP package: ml-submission-telemetry.zip
  Added 142 files...
Package created: ml-submission-telemetry.zip
Calculating checksum...
SHA256: def456...
Creating submission manifest...

✓ ML submission package complete!
  Type: telemetry_only
  Size: 87.3 MB
  Files: 142
  Package: ml-submission-telemetry.zip
  Manifest: ml-submission-telemetry.manifest.json

  Enables: 2 of 5 ML models (40% of automation roadmap)
    ✓ Trajectory models
    ✓ Self-calibration
    ✗ Ball detector (requires videos)
    ✗ Field segmentation (requires videos)
    ✗ Batter pose estimation (requires videos)
```

---

## Command-Line Options

| Option | Required | Description | Example |
|--------|----------|-------------|---------|
| `--session-dir` | Yes | Session directory path | `recordings\session-001` |
| `--output` | Yes | Output ZIP file path | `ml-submission.zip` |
| `--type` | Yes | Submission type | `full` or `telemetry_only` |
| `--rig-id` | No | Unique rig identifier | `rig-001` |
| `--location` | No | Recording location | `Indoor Facility A` |
| `--pitcher-id` | No | Anonymous pitcher ID | `anonymous-123` |
| `--operator` | No | Coach/operator ID | `coach-456` |
| `--player-consent` | No | Flag: player consent obtained | (flag, no value) |
| `--anonymized` | No | Flag: data anonymized | (flag, no value) |
| `--retention-days` | No | Data retention period | `730` (default) |
| `--reason` | No | Reason for telemetry-only | `privacy_preserving` |

---

## Package Contents

### Full Package Structure

```
ml-submission-{session-id}-full.zip
├── submission_manifest.json          # Metadata
├── session/
│   ├── manifest.json
│   ├── session_summary.json
│   ├── session_left.avi              # ← VIDEO
│   ├── session_right.avi             # ← VIDEO
│   ├── session_left_timestamps.csv
│   ├── session_right_timestamps.csv
│   └── calibration/
│       ├── stereo_geometry.json
│       ├── intrinsics_left.json
│       ├── intrinsics_right.json
│       └── roi_annotations.json
└── pitches/
    ├── pitch-001/
    │   ├── manifest.json
    │   ├── left.avi                  # ← VIDEO
    │   ├── right.avi                 # ← VIDEO
    │   ├── left_timestamps.csv
    │   ├── right_timestamps.csv
    │   ├── detections/
    │   │   ├── left_detections.json
    │   │   └── right_detections.json
    │   ├── observations/
    │   │   └── stereo_observations.json
    │   └── frames/                   # ← KEY FRAMES
    │       ├── left/*.png
    │       └── right/*.png
    └── ...
```

### Telemetry-Only Package Structure

```
ml-submission-{session-id}-telemetry.zip
├── submission_manifest.json          # Metadata
├── session/
│   ├── manifest.json
│   ├── session_summary.json
│   └── calibration/
│       ├── stereo_geometry.json
│       ├── intrinsics_left.json
│       ├── intrinsics_right.json
│       └── roi_annotations.json
└── pitches/
    ├── pitch-001/
    │   ├── manifest.json
    │   ├── detections/
    │   │   ├── left_detections.json
    │   │   └── right_detections.json
    │   └── observations/
    │       └── stereo_observations.json
    └── ...
```

**Note:** Telemetry-only omits all `.avi` video files and `.png` frame files.

---

## Submission Manifest

Every package includes `submission_manifest.json`:

```json
{
  "schema_version": "1.2.0",
  "app_version": "1.2.0",
  "submission_id": "ml-submission-20260116-123456",
  "submission_type": "full",
  "created_utc": "2026-01-16T12:34:56Z",
  "session": {
    "session_id": "session-2026-01-16_001",
    "started_utc": "2026-01-16T12:00:00Z",
    "ended_utc": "2026-01-16T12:30:00Z",
    "pitch_count": 20
  },
  "source": {
    "app": "PitchTracker",
    "rig_id": "rig-001",
    "location": "Indoor Facility A",
    "pitcher_id": "player-anonymous-123",
    "operator": "coach-456"
  },
  "data_manifest": {
    "videos": {
      "session_videos": true,
      "pitch_videos": true,
      "key_frames": true
    },
    "telemetry": {
      "detections": true,
      "observations": true,
      "calibration": true,
      "performance_metrics": true
    }
  },
  "size_bytes": 4294967296,
  "checksum_sha256": "abc123...",
  "intended_use": [
    "ball_detector_training",
    "field_segmentation_training",
    "pose_estimation_training",
    "trajectory_model_training",
    "self_calibration_training"
  ],
  "privacy": {
    "player_consent": true,
    "anonymized": true,
    "retention_days": 730
  }
}
```

---

## Recommended Strategy

### Phase 1: Initial Data Collection (Weeks 1-4)

**Goal:** Collect diverse data for ball detector training

**Strategy:** Use FULL packages
- Record 50+ sessions across different conditions
- Varied lighting (indoor/outdoor, time of day)
- Different ball types if applicable
- Multiple camera angles/installations

**Outcome:** Sufficient data to train first automation model (ball detector)

### Phase 2: Ball Detector Training (Months 2-6)

**Goal:** Train and deploy ball detector model

**Strategy:** Continue FULL packages for model improvement
- Collect challenging cases (motion blur, poor lighting)
- Validate model performance across environments
- Gather edge cases for model refinement

**Outcome:** Ball detector deployed, HSV tuning eliminated

### Phase 3: Privacy-Preserving Collection (Months 7+)

**Goal:** Maintain data flow while preserving privacy

**Strategy:** Switch to TELEMETRY-ONLY for most sessions
- Ball detector already trained
- Focus on trajectory and calibration improvements
- Occasional FULL packages for visual model updates
- 50x smaller uploads, faster submission

**Outcome:** Ongoing model improvement without video privacy concerns

---

## Privacy Best Practices

### For Full Package Submissions

1. **Obtain Explicit Consent**
   ```
   [ ] Player signed video sharing consent form
   [ ] Parent/guardian consent (if minor)
   [ ] Facility permission obtained
   [ ] Privacy policy reviewed with player
   ```

2. **Anonymize Data**
   ```
   [ ] Player identified by anonymous ID only
   [ ] No names in metadata
   [ ] Facility branding acceptable or removed
   [ ] Background individuals not identifiable
   ```

3. **Set Retention Limits**
   ```
   [ ] Specify data retention period (default: 730 days)
   [ ] Document deletion policy
   [ ] Provide data access/deletion requests process
   ```

### For Telemetry-Only Submissions

1. **Confirm No Visual Data**
   ```
   [ ] Package contains no .avi files
   [ ] Package contains no .png files
   [ ] Only JSON/CSV metadata included
   ```

2. **Still Anonymize**
   ```
   [ ] Player identified by anonymous ID
   [ ] Biomechanics potentially identifying
   [ ] Consider if trajectory patterns reveal identity
   ```

---

## Troubleshooting

### Package Too Large

**Problem:** Full package is 10+ GB

**Solutions:**
- Reduce video resolution in `configs/default.yaml` (camera.width, camera.height)
- Reduce frame rate (camera.fps)
- Compress videos before packaging (lossy compression acceptable for some models)
- Use telemetry-only variant if visual models not needed

### Missing ML Training Data

**Problem:** Package missing detections/observations/frames

**Solutions:**
- Enable ML data collection in `configs/default.yaml`:
  ```yaml
  recording:
    save_detections: true
    save_observations: true
    save_training_frames: true
  ```
- Re-record session with ML features enabled
- Validate export: `python test_ml_data_export.py "session-dir"`

### Upload Fails

**Problem:** Package rejected by cloud API

**Solutions:**
- Check `submission_manifest.json` for errors
- Verify checksum matches package
- Ensure all required fields present
- Check package size limits
- Validate schema version compatibility

---

## Next Steps

1. **Enable ML data collection** in `configs/default.yaml`
2. **Record test session** with a few pitches
3. **Validate export:** `python test_ml_data_export.py "session-dir"`
4. **Create submission package:**
   - Full: `python export_ml_submission.py --type full ...`
   - Telemetry: `python export_ml_submission.py --type telemetry_only ...`
5. **Verify package contents** (unzip and inspect)
6. **Submit to cloud** (upload mechanism depends on your infrastructure)

---

## Related Documentation

- **[CLOUD_SUBMISSION_SCHEMA.md](CLOUD_SUBMISSION_SCHEMA.md)** - Complete schema specification
- **[ML_QUICK_REFERENCE.md](ML_QUICK_REFERENCE.md)** - ML features quick guide
- **[ML_TRAINING_DATA_STRATEGY.md](ML_TRAINING_DATA_STRATEGY.md)** - 18-month automation roadmap
- **[MANIFEST_SCHEMA.md](MANIFEST_SCHEMA.md)** - Data format reference

---

## Support

**Export Help:**
```powershell
python export_ml_submission.py --help
```

**Validate ML Data:**
```powershell
python test_ml_data_export.py "recordings\session-dir"
```

**Questions:** See [CLOUD_SUBMISSION_SCHEMA.md](CLOUD_SUBMISSION_SCHEMA.md) for detailed specification
