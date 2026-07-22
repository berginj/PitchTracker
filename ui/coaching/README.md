# Coaching Application

> **Documentation note (2026-07-21):** this page originated as the dashboard
> prototype guide. The coaching UI is now pipeline-integrated; current delivery
> and open work are tracked in `docs/CURRENT_STATUS.md` and `docs/ROADMAP.md`.
> Prototype-era pending lists below are retained as design history, not backlog.

## Overview

Dashboard-style coaching application for fast, focused pitching session management.

**Status:** Integrated application; hardware and field validation pending

## Running the Prototype

```powershell
# From project root
python scripts/test_coaching_app.py
```

## Current Features

### ✅ Dashboard Layout
- Session info bar (session name, pitcher, pitch count)
- Dual camera views (left/right)
- Strike zone visualization (3x3 grid)
- Latest pitch metrics display
- Location heat map
- Recent pitches list

### ✅ Session Controls
- Start Session button (one-click start)
- Pause/Resume functionality
- End Session with confirmation
- Recording indicator
- Status bar with color-coded states

### ✅ UI Design
- Clean, focused dashboard layout
- Large buttons for quick access
- Real-time metric displays (placeholders)
- Color-coded feedback (green=recording, yellow=paused)

### 🚧 Pending Features

**Session Management:**
- Session start dialog (pitcher selection, session name)
- Load calibration from setup
- Auto-start capture on session start
- Save session data on end

**Live Tracking:**
- Real camera preview integration
- Pitch detection callbacks
- Real-time metric updates
- Trajectory trail visualization
- Heat map population

**Replay:**
- Last pitch replay button
- Frame-by-frame stepping
- Trajectory view dialog

**Summary:**
- Session summary dialog
- Statistics display
- Export for player review
- Upload to cloud

**Settings:**
- Quick batter height adjustment
- Ball type toggle
- Strike zone ratio sliders
- Camera selection (if needed)

## Architecture

```
ui/coaching/
├── coach_window.py           # Main dashboard
├── widgets/                  # Custom widgets
│   ├── pitch_monitor.py      # Live pitch tracking
│   ├── strike_zone_view.py   # Strike zone visual
│   ├── heat_map.py           # Location heat map
│   ├── metrics_panel.py      # Metrics display
│   └── pitch_history.py      # Recent pitches
├── dialogs/                  # Dialogs
│   ├── session_start.py      # Pitcher selection
│   ├── session_summary.py    # End of session
│   └── replay_viewer.py      # Pitch replay
└── export/                   # Export utilities
    └── player_package.py     # Player video package
```

## UI Layout

```
┌─────────────────────────────────────────────────────────────┐
│ Session: Practice-2026-01-16 | Pitcher: John Doe | Pitches: 23 | ● Recording │
├─────────────────────────────────────────────────────────────┤
│ ┌─────────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐│
│ │ Left Camera │  │  Strike  │  │   Latest   │  │  Right   ││
│ │             │  │   Zone   │  │   Metrics  │  │  Camera  ││
│ │   [Live]    │  │  3x3 Grid│  │ 87.3 mph   │  │  [Live]  ││
│ │             │  │          │  │ +2.1 H     │  │          ││
│ └─────────────┘  └──────────┘  │ -0.8 V     │  └──────────┘│
│                                │ STRIKE     │               │
│ ┌──────────────────────────┐  └────────────┘               │
│ │      Heat Map            │  ┌────────────────────────┐   │
│ │   Location by Zone       │  │   Recent Pitches       │   │
│ │  3  2  1                 │  │ 1. 87.3 mph STRIKE     │   │
│ │  2  5  3                 │  │ 2. 85.1 mph BALL       │   │
│ │  1  4  2                 │  │ 3. 88.9 mph STRIKE     │   │
│ └──────────────────────────┘  └────────────────────────┘   │
├─────────────────────────────────────────────────────────────┤
│ [Start Session]  [⏸ Pause]  [⏹ End Session]  [⚙][❓]     │
└─────────────────────────────────────────────────────────────┘
```

## Design Philosophy

### Focus on Speed
- One-click session start (<10 seconds)
- Auto-load calibration from setup
- Minimal dialogs, maximum dashboard
- Large, obvious buttons

### Real-time Feedback
- Metrics update immediately after pitch
- Heat map updates live
- Recent pitches list auto-scrolls
- Visual indicators (colors, icons)

### Minimal Distraction
- No technical configuration exposed
- Settings hidden in menu (password-protected)
- Clean, focused interface
- No clutter

### Safety
- Calibration loaded from setup (read-only)
- No risk of breaking calibration
- Session data auto-saved
- Confirmation before discarding data

## Testing Checklist

### Dashboard Tests
- [ ] Launch coaching app
- [ ] Verify all dashboard elements visible
- [ ] Check strike zone grid renders
- [ ] Verify session bar shows correct initial state

### Session Flow Tests
- [ ] Click "Start Session" - should show recording state
- [ ] Verify session info updates (name, pitcher, count)
- [ ] Verify recording indicator appears
- [ ] Click "Pause" - should show paused state
- [ ] Click "End Session" - should show confirmation
- [ ] Confirm end - should reset to initial state

### Button States
- [ ] Start button disabled when session active
- [ ] Pause/End buttons enabled only during session
- [ ] Settings/Help always available

## Next Steps

1. **Session Start Dialog** (1 hour)
   - Pitcher selection from saved list
   - Session name auto-generation
   - Quick settings (batter height, ball type)

2. **Pipeline Integration** (2 hours)
   - Load calibration from setup
   - Start capture automatically
   - Connect pitch tracking callbacks
   - Update metrics display

3. **Live Camera Preview** (2 hours)
   - Integrate camera feeds
   - Add strike zone overlay
   - Add detection indicators

4. **Replay Functionality** (2 hours)
   - Last pitch replay dialog
   - Frame-by-frame controls
   - Trajectory visualization

5. **Session Summary** (2 hours)
   - Statistics calculation
   - Heat map generation
   - Export for player review

6. **Polish** (1 hour)
   - Keyboard shortcuts
   - Color themes
   - Error handling

## Comparison: Setup vs Coaching

| Feature | Setup App | Coaching App |
|---------|-----------|--------------|
| **Purpose** | One-time configuration | Daily sessions |
| **User** | Technician/installer | Coach/pitcher |
| **Frequency** | Once (or rarely) | Every practice |
| **UI Pattern** | Wizard (guided) | Dashboard (quick access) |
| **Complexity** | High (many options) | Low (focused) |
| **Session Time** | 20-45 minutes | 10 sec start, 5-30 min session |
| **Focus** | Accuracy, validation | Speed, real-time feedback |
| **Safety** | Can change everything | Read-only calibration |

## Known Issues

1. Camera preview shows placeholder (integration pending)
2. Metrics show dummy data (pipeline integration pending)
3. Session start uses dummy pitcher name
4. Heat map not populated
5. Recent pitches list empty

## Future Enhancements

- Voice commands ("start recording", "show replay")
- Tablet mode (simplified for tablets)
- Parent/spectator view (read-only)
- Multi-pitcher quick switch
- Automatic session naming based on schedule
- Cloud sync for session data
