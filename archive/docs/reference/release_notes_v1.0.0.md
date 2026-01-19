# PitchTracker v1.0.0 - Initial Release

🎉 **First official release of PitchTracker!**

## Overview

PitchTracker is a dual-camera stereo vision system for baseball pitch tracking and analysis. This release provides a complete, professional application with installer, auto-updates, and comprehensive documentation.

## 🚀 Installation

**Quick Start:**
1. Download `PitchTracker-Setup-v1.0.0.exe` below
2. Run the installer (requires Windows 10+ 64-bit)
3. Launch from Start Menu
4. Connect dual USB cameras
5. Complete the 6-step Setup Wizard
6. Start tracking!

**System Requirements:**
- Windows 10 or 11 (64-bit)
- 8 GB RAM (16 GB recommended)
- Dual USB 3.0 cameras
- 2 GB free disk space

## ✨ Features

### Pitch Tracking
- Real-time pitch detection and tracking
- 3D trajectory reconstruction from stereo vision
- Strike zone analysis with 3x3 grid overlay
- Velocity, spin, and movement metrics
- Session recording with per-pitch video clips

### Calibration & Setup
- Guided stereo calibration wizard
- Checkerboard pattern detection
- AprilTag fiducial support
- ROI (Region of Interest) configuration
- Camera parameter tuning

### ML Support
- ONNX model integration
- Custom ball detector training
- ML data export for training
- Classical detector fallback

### User Interface
- Dual-role design: Setup Wizard + Coaching App
- Real-time visualization
- Session management
- Metrics dashboard
- Heat maps and trajectory plots

### Deployment
- Professional Windows installer
- Auto-update mechanism (GitHub Releases)
- Startup validation with helpful errors
- Complete documentation

## 📊 Technical Details

**Codebase:**
- 22,000+ lines of Python code
- 161 Python files
- Modular architecture
- Comprehensive test suite (pytest)

**Dependencies:**
- PySide6 (Qt) for UI
- OpenCV for computer vision
- NumPy/SciPy for numerical processing
- PyYAML for configuration
- Loguru for logging

**Architecture:**
- Pipeline service with detection threading
- Queue-based frame processing
- Pluggable camera backends (UVC, OpenCV, Simulated)
- Thread-safe pitch tracking (V2)
- Zero data loss design

## 📚 Documentation

**User Guides:**
- `README_INSTALL.md` - Installation and first-time setup
- `README_LAUNCHER.md` - Launcher and role selection
- `ML_QUICK_REFERENCE.md` - ML features quick start

**Developer Guides:**
- `BUILD_INSTRUCTIONS.md` - Building the installer
- `DEPLOYMENT_IMPROVEMENTS.md` - Deployment infrastructure
- `DESIGN_PRINCIPLES.md` - System architecture
- `PITCH_TRACKING_V2_GUIDE.md` - Pitch tracking V2 system

**Technical Documentation:**
- `MANIFEST_SCHEMA.md` - Session data format (v1.2.0)
- `CLOUD_SUBMISSION_GUIDE.md` - ML data export
- `ML_TRAINING_DATA_STRATEGY.md` - 18-month automation roadmap

## 🔄 Auto-Updates

This installer includes automatic update checking. When a new version is released:
1. You'll be notified on app launch
2. Click "Download and Install"
3. Installer downloads and launches automatically
4. App closes and updates

You can also:
- "Remind Me Later" - Check again next launch
- "Skip This Version" - Never notify about this version

## 📝 Changelog

Initial release - all features are new!

Key milestones:
- ✅ Dual-camera stereo calibration
- ✅ Real-time pitch detection
- ✅ 3D trajectory reconstruction
- ✅ Session recording and management
- ✅ Professional installer with auto-updates
- ✅ Comprehensive documentation

## 🙏 Credits

Built with Python, OpenCV, Qt, and lots of coffee.

**Co-Authored-By: Claude Sonnet 4.5**

---

**Full Changelog**: https://github.com/berginj/PitchTracker/commits/v1.0.0
