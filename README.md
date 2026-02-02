# PitchTracker Quick Start (Windows)

## For End Users (Coaches)

If you received the installer, see [README_INSTALL.md](README_INSTALL.md) for installation instructions.

**Quick Install:**
1. Download `PitchTracker-Setup-v1.0.0.exe`
2. Run installer (requires Windows 10+)
3. Launch from Start Menu
4. Complete 6-step Setup Wizard

The application includes automatic updates - you'll be notified when new versions are available.

### 📚 User Documentation

**New to PitchTracker? Start here:**
- **[Quick Start Guide](docs/QUICK_START.md)** - Get up and running in 30 minutes
- **[FAQ](docs/user/FAQ.md)** - Frequently asked questions and answers
- **[Troubleshooting](docs/user/TROUBLESHOOTING.md)** - Common issues and solutions
- **[Calibration Tips](docs/user/CALIBRATION_TIPS.md)** - Camera setup and calibration

**For advanced usage:**
- **[Pattern Detection Guide](docs/PATTERN_DETECTION_GUIDE.md)** - **NEW (UI Integrated!)** - Analyze pitch types, detect anomalies, track pitcher baselines
- [Review Mode Guide](docs/REVIEW_TRAINING_MODE_DESIGN.md) - Analyze and tune past sessions
- [Current Status](docs/CURRENT_STATUS.md) - Project status and roadmap

**Pattern Detection Quick Start:**
1. Record a pitching session
2. Click **"Analyze Patterns"** in the Session Summary dialog
3. View results: pitch types, anomalies, velocity trends, and more
4. Create pitcher profiles to track performance over time

---

## Calibration Board Preparation

### Generate & Print ChArUco Board

Before running the Setup Wizard, you'll need to print a calibration board. Use the included generator:

```bash
# Generate default 5x6 board (30mm squares)
python generate_charuco.py

# Generate custom size board
python generate_charuco.py --cols 7 --rows 5 --size 25

# Generate for A4 paper (instead of US Letter)
python generate_charuco.py --paper a4
```

**Output:** `charuco_board.png` - ready to print!

**Printing Instructions:**
1. Open `charuco_board.png` in image viewer
2. Print at **100% scale** (CRITICAL - disable "Fit to Page")
3. Use **high quality** print mode
4. Print on **thick paper** or cardstock
5. Mount on **rigid surface** (foam board, wood)
6. Verify with ruler: squares should be 30mm ± 0.5mm

**Why ChArUco?**
- Works with partial occlusion (don't need entire board visible)
- Auto-detects board size and orientation
- More robust to lighting
- Can be used at varying distances

---

## For Developers

### First-Time Setup

**Detailed installation instructions:** [docs/INSTALLATION.md](docs/INSTALLATION.md)

**Quick setup:**
```bash
# 1. Install Python 3.10+ (https://www.python.org/downloads/)

# 2. Clone repository
git clone https://github.com/berginj/PitchTracker.git
cd PitchTracker

# 3. Install dependencies
pip install -r requirements.txt

# 4. Verify installation
python setup_validator.py

# 5. Run Setup Wizard
python launcher.py
```

**Alternative (PowerShell):**
```powershell
cd C:\Users\bergi\App\PitchTracker
.\setup.ps1
```

## Run
```powershell
.\run.ps1 -Backend uvc
```

If you only have an internal camera, use:
```powershell
.\run.ps1 -Backend opencv
```

## Notes
- Use the `Refresh Devices` button to populate cameras.
- The calibration wizard runs after startup; follow the steps or use Skip to reach the UI.
- Configure ROIs and strike zone settings before recording.
- Camera mount files are in `3dModels/`.
- Recording creates a session folder with per-pitch subfolders (left/right videos, timestamps, manifest).
- Recording also writes continuous session videos: `session_left.avi`, `session_right.avi`, and timestamp CSVs in the session folder.

## ARM Auto Config
On Windows ARM (e.g., Snapdragon), the UI auto-selects `configs/snapdragon.yaml` when no `--config` is provided. Use `--config configs/default.yaml` (or another file) to override.

## Tests
```powershell
python -m pytest
```

To run optional clip-based detection tests:
```powershell
$env:PITCHTRACKER_TEST_VIDEO="C:\path\to\left.avi"
python -m pytest tests/test_video_clip.py
```

**Test Coverage (as of 2026-01-27):**
- Pattern Detection: 45/45 tests (100% ✅)
- UI Integration: 13/13 tests (100% ✅)
- Core Pipeline: 287 tests (98%)
- Integration Tests: 26 tests (100% ✅)
- Memory/Stress Tests: 15 tests (100% ✅)
- **Total:** 389+ tests (98%+ passing)
- **Last Updated:** Calibration UX simplification complete

## Completed Features
- PySide6 UI with in-process pipeline service and recording/replay
- Lane + plate ROI calibration with strike-zone 3x3 overlay
- Classical detector with ROI cropping and optional ONNX ML detector
- Recording bundles with manifest, timestamps, and config snapshot
- Plate plane calibration tool with logging
- **Simplified Calibration UX (NEW - 2026-01-27):**
  - Redesigned calibration interface with progressive disclosure
  - Large camera previews (800×600) for better visibility
  - Simple READY/NOT READY status indicators
  - Visual progress bar showing capture count
  - 80% reduction in visible UI elements (advanced features collapsed by default)
  - Maintains 100% functionality with dramatically improved usability
- **Pattern Detection System (2026-01-19):**
  - Pitch classification (Fastball, Curveball, Slider, Changeup, Sinker, Cutter)
  - Anomaly detection (speed, movement, trajectory quality)
  - Pitcher profile management with baseline comparison
  - UI integration - "Analyze Patterns" button in Session Summary
  - JSON and HTML reports with embedded charts
  - Cross-session analysis (velocity trends, strike consistency, pitch mix)

## Performance Characteristics

**System Performance (as of v1.2.0, optimized 2026-01-18):**

| Metric | Performance | Details |
|--------|------------|---------|
| **Detection Rate** | 60-90 FPS | Per camera at 720p (2-3x faster than v1.1) |
| **Stereo Latency** | 15-20ms | Frame pairing to 3D triangulation (1.5-2x faster) |
| **Memory Usage** | ~100MB | Working set during active tracking (16% reduction) |
| **CPU Utilization** | ~35% | On 4-core system at 720p/60fps (42% reduction) |
| **Frame Retention** | >99% | Under normal operation (adaptive queue sizing) |

**Optimization Summary:**
- OpenCV-optimized detection algorithms (10-100x faster)
- Epipolar stereo matching (80-90% fewer match candidates)
- Memory-efficient background models (75% reduction per camera)
- Multi-threaded NumPy operations for multi-core systems
- Adaptive queue sizing for burst handling
- Strike zone caching for metrics computation

**Recommended Hardware:**
- **Minimum:** Intel i5-8th gen / AMD Ryzen 5 3000, 8GB RAM, Windows 10
- **Recommended:** Intel i7-10th gen / AMD Ryzen 7 5000, 16GB RAM, Windows 11
- **Optimal:** Intel i9 / AMD Ryzen 9, 32GB RAM, dedicated GPU (future)

**Camera Support:**
- Tested: 720p @ 60fps (dual UVC cameras)
- Supported: Up to 1080p @ 60fps (with recommended hardware)
- Future: 1080p @ 120fps (requires multiprocessing optimization)

For detailed optimization documentation, see:
- [PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md) - Detailed analysis and implementation
- [OPTIMIZATION_SUMMARY.md](docs/OPTIMIZATION_SUMMARY.md) - Complete implementation summary

## ML Detector
Set these in `configs/default.yaml` to use an ONNX model:
- `detector.type: ml`
- `detector.model_path: path\to\model.onnx`
- `detector.model_input_size: [640, 640]`
- `detector.model_conf_threshold: 0.25`
- `detector.model_class_id: 0`
- `detector.model_format: yolo_v5`

Quick validation:
```powershell
python -m detect.validate_ml --model models\ball.onnx --image samples\frame.png
```

## Building the Installer

To create a distributable installer for end users:

```powershell
# Install build tools (one-time setup)
pip install pyinstaller

# Download and install Inno Setup 6 from:
# https://jrsoftware.org/isdl.php

# Build installer (creates PitchTracker-Setup-v1.0.0.exe)
.\build_installer.ps1 -Clean
```

**Output:** `installer_output\PitchTracker-Setup-v1.0.0.exe` (~100-150 MB)

See [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) for detailed build documentation including:
- Prerequisites and dependencies
- Bundle size optimization
- Version management
- Testing checklist
- Distribution via GitHub Releases

**Auto-Update Mechanism:** The installer includes automatic update checking via GitHub Releases API. When you publish a new release with a tagged version (e.g., `v1.0.1`) and attach the installer as an asset, users will be notified and can install updates with one click.

---

## Documentation

### Core Documentation
- [README.md](README.md) - This quick start guide
- [README_INSTALL.md](README_INSTALL.md) - End-user installation guide
- [BUILD_INSTRUCTIONS.md](BUILD_INSTRUCTIONS.md) - Building the installer
- [CHANGELOG.md](CHANGELOG.md) - Version history and changes
- [REQ.md](REQ.md) - Requirements and specifications
- [MANIFEST_SCHEMA.md](MANIFEST_SCHEMA.md) - Session and pitch manifest schemas (v1.2.0)

### Architecture & Design
- [DESIGN_PRINCIPLES.md](DESIGN_PRINCIPLES.md) - System design principles
- [REFACTORING_PROGRESS.md](REFACTORING_PROGRESS.md) - Pipeline service refactoring

### Performance & Optimization (NEW - 2026-01-18)
- **[OPTIMIZATION_SUMMARY.md](docs/OPTIMIZATION_SUMMARY.md)** - Implementation summary ⭐ START HERE
- **[PERFORMANCE_OPTIMIZATION.md](docs/PERFORMANCE_OPTIMIZATION.md)** - Detailed analysis and roadmap
- **[PERFORMANCE_BENCHMARKS.md](docs/PERFORMANCE_BENCHMARKS.md)** - Benchmark results and methodology
- **[MEMORY_LEAK_TESTING.md](docs/MEMORY_LEAK_TESTING.md)** - Memory stability validation

**Performance Improvements (v1.2.0):**
- ✅ Detection: 30 FPS → 60-90 FPS (2-3x improvement)
- ✅ Stereo: 30ms → 15-20ms latency (1.5-2x improvement)
- ✅ Memory: 120MB → 100MB working set (16% reduction)
- ✅ CPU: 60% → 35% utilization (42% reduction)
- ✅ Overall: 3-5x end-to-end performance improvement

**Key Optimizations:**
- OpenCV algorithms (10-100x faster than pure Python)
- Epipolar stereo filtering (80-90% fewer match candidates)
- Memory-efficient background models (75% per-camera reduction)
- Lock-free error tracking (15-30% latency reduction)
- Adaptive queue sizing and strike zone caching

### Pitch Tracking V2
- **[PITCH_TRACKING_V2_GUIDE.md](PITCH_TRACKING_V2_GUIDE.md)** - Complete integration guide
- **[PITCH_TRACKING_V2_SUMMARY.md](PITCH_TRACKING_V2_SUMMARY.md)** - Quick V1 vs V2 comparison
- **[PITCH_TRACKING_V2_INTEGRATION.md](PITCH_TRACKING_V2_INTEGRATION.md)** - Integration changes
- **[PITCH_TRACKING_ANALYSIS.md](PITCH_TRACKING_ANALYSIS.md)** - V1 issues analysis (12 critical bugs)
- **[V2_TEST_RESULTS.md](V2_TEST_RESULTS.md)** - Test results (8/8 passing)
- **[V2_CLEANUP_TASKS.md](V2_CLEANUP_TASKS.md)** - Optional enhancements

**Key V2 Improvements:**
- Zero data loss (was ~16 frames/pitch in V1)
- Thread-safe operations
- Accurate timing (<33ms error vs ±330ms in V1)
- Pre-roll buffering that actually works
- Data validation and false trigger filtering

### ML Training & Automation (NEW)
- **[ML_QUICK_REFERENCE.md](ML_QUICK_REFERENCE.md)** - Quick start guide for ML features ⭐ START HERE
- **[CLOUD_SUBMISSION_GUIDE.md](CLOUD_SUBMISSION_GUIDE.md)** - Package data for cloud upload ⭐ EXPORT GUIDE
- **[ML_TRAINING_DATA_STRATEGY.md](ML_TRAINING_DATA_STRATEGY.md)** - 18-month automation roadmap
- **[ML_TRAINING_IMPLEMENTATION_GUIDE.md](ML_TRAINING_IMPLEMENTATION_GUIDE.md)** - Week 1 implementation details
- **[CLOUD_SUBMISSION_SCHEMA.md](CLOUD_SUBMISSION_SCHEMA.md)** - Technical specification (full vs telemetry-only)

**Current Status (v1.2.0):**
- ✅ Detection export (pixel coordinates, confidence scores)
- ✅ Observation export (3D trajectory points)
- ✅ Frame extraction (key frames as PNG)
- ✅ Calibration export (geometry, intrinsics, ROIs)
- ✅ Performance metrics in manifest

**Automation Roadmap:**
- 6 months: Ball detector model (eliminate HSV tuning)
- 9 months: Field segmentation (auto-detect ROIs)
- 12 months: Batter pose estimation (auto-calculate strike zone)
- 18 months: Self-calibration (reduce setup to <2 min)

**Enable ML Data Collection:**
```yaml
# configs/default.yaml
recording:
  save_detections: true       # Export detection JSON
  save_observations: true     # Export 3D observations
  save_training_frames: true  # Save key frames
  frame_save_interval: 5      # Frame sampling rate
```

**Validate Export:**
```powershell
python test_ml_data_export.py "recordings\session-2026-01-16_001"
```

**Export for Cloud Submission:**
```powershell
# Full package (videos + telemetry) - 4-5 GB, enables all 5 models
python export_ml_submission.py --session-dir "recordings\session-2026-01-16_001" --output "ml-submission-full.zip" --type full --pitcher-id "anonymous-123"

# Telemetry-only (no videos) - 50-100 MB, enables 2 of 5 models, privacy-preserving
python export_ml_submission.py --session-dir "recordings\session-2026-01-16_001" --output "ml-submission-telemetry.zip" --type telemetry_only --pitcher-id "anonymous-123" --reason privacy_preserving
```
