# Keyboard Shortcuts

This document lists all keyboard shortcuts available in the PitchTracker application.

## Capture

| Shortcut | Action | Description |
|----------|--------|-------------|
| **F5** | Start Capture | Begin capturing video from cameras |
| **F6** | Stop Capture | Stop capturing video |
| **Ctrl+Shift+R** | Restart Capture | Restart the capture pipeline |
| **Ctrl+R** | Start Recording | Begin recording session data |
| **Ctrl+Shift+S** | Stop Recording | Stop recording session data |
| **Ctrl+T** | Training Capture | Start training data capture mode |

## Calibration

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+G** | Calibration Guide | Open the calibration guide documentation |
| **Ctrl+W** | Setup Doctor | Launch rig readiness checks |
| **Ctrl+Q** | Quick Calibrate | Open quick calibration dialog |
| **Ctrl+Shift+P** | Plate Plane Calibrate | Calibrate the plate plane position |

## ROI (Region of Interest)

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+1** | Edit Lane ROI | Enter lane ROI editing mode |
| **Ctrl+2** | Edit Right Lane ROI | Enter right lane ROI editing mode |
| **Ctrl+3** | Edit Plate ROI | Enter plate ROI editing mode |
| **Ctrl+S** | Save ROIs | Save current ROI configuration |
| **Ctrl+O** | Load ROIs | Load ROI configuration from file |

## Settings

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+,** | Recording Settings | Open recording settings dialog |
| **Ctrl+Z** | Strike Zone Settings | Configure strike zone parameters |
| **Ctrl+D** | Detector Settings | Configure ball detector settings |

## Tools

| Shortcut | Action | Description |
|----------|--------|-------------|
| **F5** | Refresh Devices | Scan for connected cameras |
| **Ctrl+L** | Checklist | Open pre-session checklist |
| **Ctrl+Shift+L** | Low Perf Mode | Toggle low performance mode |
| **Ctrl+Shift+G** | Reset Game | Reset tic-tac-toe game state |
| **Ctrl+Shift+T** | Target Mode | Toggle calibration target detection mode |

## Review

| Shortcut | Action | Description |
|----------|--------|-------------|
| **Ctrl+P** | Replay | Start replay of recorded session |
| **Space** | Pause/Resume Replay | Toggle replay pause |
| **Right Arrow** | Step Replay | Step forward one frame in replay |

## View

| Shortcut | Action | Description |
|----------|--------|-------------|
| **F2** | Show Health Panel | Toggle health monitoring panel |
| **F3** | Show Right Camera | Toggle right camera view |
| **F11** | Production Mode | Toggle production mode (clean UI) |

## Help

| Shortcut | Action | Description |
|----------|--------|-------------|
| **F1** | Keyboard Shortcuts | Open this keyboard shortcuts guide |
| (none) | About | Show application version and info |

## Tips

### Common Workflows

**Quick Start Session:**
1. `F1` - Review calibration guide if needed
2. `F5` - Start capture
3. `Ctrl+R` - Start recording
4. Throw pitches
5. `Ctrl+Shift+S` - Stop recording

**Calibration Workflow:**
1. `Ctrl+Q` - Open quick calibrate
2. Capture 5-10 images
3. Review results
4. `Ctrl+S` - Save ROIs if needed

**Review Session:**
1. `Ctrl+P` - Start replay
2. `Space` - Pause at interesting frame
3. `Right Arrow` - Step through frames
4. `Space` - Resume playback

### Function Key Summary

- **F1** - Help (Keyboard Shortcuts)
- **F2** - Toggle Health Panel
- **F3** - Toggle Right Camera
- **F5** - Start Capture / Refresh Devices
- **F6** - Stop Capture
- **F11** - Production Mode

### Modifier Key Patterns

- **Ctrl+Letter** - Primary actions (R=Record, Q=Quick Cal, L=Checklist)
- **Ctrl+Shift+Letter** - Secondary/Stop actions (S=Stop Record, R=Restart)
- **Ctrl+Number** - ROI selection (1=Lane, 2=Right Lane, 3=Plate)

## Notes

- Some shortcuts may be context-sensitive (e.g., Space for pause only works during replay)
- F5 has dual function: Start Capture in main view, Refresh Devices in Tools menu
- All shortcuts are case-insensitive
- Shortcuts work when the main window has focus

---

**Last Updated**: 2026-02-13
**File Location**: `ui/main_window.py` (lines 1616-1721)
