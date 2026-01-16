# PitchTracker Installation

Thank you for installing PitchTracker!

## System Requirements

- **Operating System:** Windows 10 or 11 (64-bit)
- **RAM:** 8 GB minimum, 16 GB recommended
- **Disk Space:** 2 GB free space
- **Cameras:** Dual USB cameras (UVC compatible)
- **Processor:** Intel Core i5 or equivalent (for real-time processing)

## What's Being Installed

PitchTracker consists of:

1. **Launcher** - Main entry point with role selector
2. **Setup Wizard** - Guided calibration and configuration
3. **Coaching App** - Real-time session management
4. **Pipeline Service** - Detection and tracking engine

## After Installation

### First-Time Setup

1. **Connect Cameras**
   - Plug in both USB cameras
   - Ensure they're detected by Windows

2. **Launch PitchTracker**
   - Find it in Start Menu → PitchTracker
   - Or use the desktop shortcut (if created)

3. **Run Setup Wizard**
   - Click "Setup & Calibration"
   - Complete all 6 steps:
     - Camera selection
     - Stereo calibration
     - ROI configuration
     - Detector tuning
     - System validation
     - Export configuration

4. **Start Coaching**
   - Return to launcher
   - Click "Coaching Sessions"
   - Begin tracking pitches!

## Updates

PitchTracker checks for updates automatically on startup. When an update is available:

- You'll see a notification dialog
- Click "Download and Install" to update
- Restart the application to apply changes

## Data Storage

Your data is stored in:

```
C:\Program Files\PitchTracker\
├── data\sessions\      # Recorded sessions
├── calibration\        # Calibration files
├── rois\              # Region of interest configs
├── configs\           # Application settings
└── logs\              # Application logs
```

## Troubleshooting

### Cameras Not Detected

- Check USB connections
- Try different USB ports (USB 3.0 recommended)
- Check Device Manager → Imaging devices

### Calibration Failed

- Ensure checkerboard pattern is visible in both cameras
- Improve lighting conditions
- Hold pattern steady during capture
- Try different angles and distances

### Application Won't Start

- Right-click PitchTracker.exe → Run as Administrator
- Check logs folder for error messages
- Reinstall the application

## Support

For help and support:

- **Documentation:** README_LAUNCHER.md
- **Issues:** https://github.com/berginj/PitchTracker/issues
- **Email:** [Your support email]

## License

This software is provided under the terms specified in the LICENSE file.

---

**Version:** 1.0.0
**Installation Date:** [Automatically populated during install]
