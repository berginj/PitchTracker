# Review/Training Mode - Design Document

**Date:** 2026-01-18
**Status:** Design Phase
**Priority:** Enhancement

---

## Executive Summary

Review/Training Mode allows users to:
1. Load previously recorded sessions
2. Replay videos through the detection pipeline
3. Adjust detection parameters in real-time
4. Compare original vs. improved detections
5. Annotate and score pitches
6. Export improved configurations and annotations

**Goal:** Enable iterative improvement of detection accuracy without re-recording.

---

## User Workflows

### Primary Use Cases

**1. Parameter Tuning**
- Coach records a session with default settings
- Some pitches were missed or incorrectly detected
- Load session in Review Mode
- Adjust HSV thresholds, filters, etc. while watching replay
- See detection improve in real-time
- Export optimized configuration

**2. Training Data Annotation**
- Load session with raw detection data
- Review each pitch frame-by-frame
- Manually annotate correct ball locations where detection failed
- Score pitch quality (good/bad detection)
- Export annotated data for ML training

**3. Detection Algorithm Comparison**
- Load same session multiple times
- Try different detection modes (MODE_A vs MODE_B)
- Compare results side-by-side
- Identify which algorithm performs best for this environment

---

## Architecture Overview

### High-Level Components

```
┌─────────────────────────────────────────────────────────────┐
│                     Review Window (UI)                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐      │
│  │   Video      │  │  Detection   │  │  Parameter   │      │
│  │   Player     │  │  Comparison  │  │   Tuning     │      │
│  └──────────────┘  └──────────────┘  └──────────────┘      │
└─────────────────────────────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────┐
│                    Review Service                            │
│  • Session Loading                                           │
│  • Video Playback Control                                    │
│  • Detection Re-processing                                   │
│  • Annotation Management                                     │
└─────────────────────────────────────────────────────────────┘
                            │
            ┌───────────────┼───────────────┐
            ▼               ▼               ▼
    ┌──────────────┐  ┌──────────┐  ┌──────────────┐
    │   Session    │  │ Video    │  │  Detection   │
    │   Loader     │  │ Reader   │  │  Pipeline    │
    └──────────────┘  └──────────┘  └──────────────┘
```

---

## Component Design

### 1. Session Loader

**Purpose:** Load and parse recorded session data

**File:** `app/pipeline/session_loader.py`

```python
@dataclass
class LoadedSession:
    """Represents a loaded recording session."""
    session_dir: Path
    session_manifest: dict
    pitches: list[LoadedPitch]
    left_video_path: Path
    right_video_path: Path
    calibration: dict
    original_config: AppConfig

@dataclass
class LoadedPitch:
    """Represents a single pitch in the session."""
    pitch_id: str
    manifest: dict
    left_video_path: Path  # pitch-specific video
    right_video_path: Path
    original_detections: dict  # left/right detection JSON
    original_observations: list  # 3D trajectory points
    frames: list  # PNG frame files if available

class SessionLoader:
    """Loads recorded sessions for review."""

    @staticmethod
    def load_session(session_dir: Path) -> LoadedSession:
        """Load session directory with all metadata and video files."""
        pass

    @staticmethod
    def get_available_sessions(recordings_dir: Path) -> list[Path]:
        """Scan recordings directory for available sessions."""
        pass

    @staticmethod
    def validate_session(session_dir: Path) -> tuple[bool, str]:
        """Check if session directory is valid and complete."""
        pass
```

**Features:**
- Validates session directory structure
- Loads session and pitch manifests
- Locates video files (session-level and pitch-level)
- Loads original detection/observation data if available
- Loads calibration metadata
- Reconstructs original configuration

---

### 2. Video Reader Service

**Purpose:** Read video files frame-by-frame with playback control

**File:** `app/review/video_reader.py`

```python
class VideoReader:
    """Reads video files with playback control."""

    def __init__(self, left_video_path: Path, right_video_path: Path):
        self._left_cap = cv2.VideoCapture(str(left_video_path))
        self._right_cap = cv2.VideoCapture(str(right_video_path))
        self._frame_count = min(
            self._left_cap.get(cv2.CAP_PROP_FRAME_COUNT),
            self._right_cap.get(cv2.CAP_PROP_FRAME_COUNT)
        )
        self._current_frame = 0
        self._fps = self._left_cap.get(cv2.CAP_PROP_FPS)

    def read_frame(self, frame_index: Optional[int] = None) -> tuple[np.ndarray, np.ndarray]:
        """Read specific frame or next frame from both videos."""
        pass

    def seek(self, frame_index: int) -> None:
        """Seek to specific frame."""
        pass

    def get_frame_count(self) -> int:
        """Get total frame count."""
        pass

    def get_fps(self) -> float:
        """Get video FPS."""
        pass

    def close(self) -> None:
        """Close video files."""
        pass
```

---

### 3. Review Service

**Purpose:** Orchestrate playback, detection, and annotation

**File:** `app/review_service.py`

```python
class ReviewService:
    """Service for reviewing and re-processing recorded sessions."""

    def __init__(self):
        self._loaded_session: Optional[LoadedSession] = None
        self._video_reader: Optional[VideoReader] = None
        self._detector: Optional[ClassicalDetector] = None
        self._config: Optional[AppConfig] = None
        self._playback_state = PlaybackState.STOPPED
        self._current_frame_index = 0
        self._annotations: dict[int, Annotation] = {}

    def load_session(self, session_dir: Path) -> LoadedSession:
        """Load session for review."""
        pass

    def start_playback(self, speed: float = 1.0) -> None:
        """Start video playback at specified speed."""
        pass

    def pause_playback(self) -> None:
        """Pause playback."""
        pass

    def seek_to_frame(self, frame_index: int) -> None:
        """Seek to specific frame."""
        pass

    def seek_to_pitch(self, pitch_index: int) -> None:
        """Seek to start of specific pitch."""
        pass

    def get_current_frame(self) -> tuple[Frame, Frame]:
        """Get current left/right frames."""
        pass

    def run_detection(self) -> tuple[list[Detection], list[Detection]]:
        """Run detection on current frame with current config."""
        pass

    def update_detector_config(self, config: DetectorConfig) -> None:
        """Update detection parameters (HSV, thresholds, etc.)."""
        pass

    def add_annotation(self, frame_index: int, annotation: Annotation) -> None:
        """Add manual annotation at frame."""
        pass

    def export_config(self, output_path: Path) -> None:
        """Export tuned configuration to YAML."""
        pass

    def export_annotations(self, output_path: Path) -> None:
        """Export annotations to JSON."""
        pass
```

---

### 4. Review Window UI

**Purpose:** User interface for review/training mode

**File:** `ui/review/review_window.py`

**Layout:**

```
┌────────────────────────────────────────────────────────────────┐
│  Review Mode - session-2026-01-18_001                     [X]  │
├────────────────────────────────────────────────────────────────┤
│  File   Playback   Detection   Tools   Export                  │
├────────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────┐  ┌──────────────────────────────┐│
│ │   Left Camera View       │  │   Right Camera View          ││
│ │  (with detections)       │  │  (with detections)           ││
│ │                          │  │                              ││
│ │                          │  │                              ││
│ └──────────────────────────┘  └──────────────────────────────┘│
│ ┌──────────────────────────────────────────────────────────────┤
│ │  Original Detections: 5    New Detections: 7                ││
│ │  [Show Original] [Show New] [Show Both] [Show Diff]         ││
│ └──────────────────────────────────────────────────────────────┤
│ ┌──────────────────────────────────────────────────────────────┤
│ │  Timeline:  [========|==================] Frame 125/480      ││
│ │  [<<] [<] [Play] [>] [>>]  Speed: 1.0x  [Pitch Markers]     ││
│ └──────────────────────────────────────────────────────────────┤
│ ┌───────────────────────────┐  ┌──────────────────────────────┤
│ │  Detection Parameters     │  │  Pitch List                  ││
│ │                           │  │  1. Pitch 001 ✓ Good         ││
│ │  Mode: MODE_A       [▼]   │  │  2. Pitch 002 ✗ Missed       ││
│ │  Frame Diff:  18.0  [▲▼]  │  │  3. Pitch 003 ✓ Good         ││
│ │  BG Diff:     12.0  [▲▼]  │  │  4. Pitch 004 ⚠ Partial     ││
│ │  Min Area:    12    [▲▼]  │  │  5. Pitch 005 ✓ Good         ││
│ │  Min Circ:    0.1   [▲▼]  │  │  [Go to Pitch]              ││
│ │                           │  │                              ││
│ │  [Reset to Original]      │  │  Stats:                      ││
│ │  [Apply Changes]          │  │  Good: 3 (60%)              ││
│ │  [Export Config]          │  │  Missed: 1 (20%)            ││
│ └───────────────────────────┘  │  Partial: 1 (20%)           ││
│                                 └──────────────────────────────┘│
└────────────────────────────────────────────────────────────────┘
```

**Key Features:**

1. **Dual Video Display**
   - Side-by-side left/right camera views
   - Overlay detections (circles on detected balls)
   - Show original vs new detections with different colors

2. **Playback Controls**
   - Timeline scrubber for seeking
   - Play/pause/step forward/step back
   - Variable speed (0.1x to 2.0x)
   - Pitch markers on timeline

3. **Parameter Tuning Panel**
   - All detection parameters adjustable with sliders
   - Real-time preview of detection changes
   - Reset to original config
   - Export tuned config

4. **Pitch List Sidebar**
   - Navigate between pitches
   - Score each pitch (Good/Missed/Partial)
   - Statistics summary

5. **Comparison Tools**
   - Show original detections only
   - Show new detections only
   - Show both (different colors)
   - Show diff (where they disagree)

---

## User Interface Mockups

### Main Menu Integration

**Option 1: Add to Main Window**
```
┌────────────────────────────────────────────┐
│  PitchTracker                              │
├────────────────────────────────────────────┤
│  [ Start New Session ]                     │
│  [ Review Prior Session ]  ← NEW           │
│  [ Settings ]                              │
│  [ Calibration ]                           │
│  [ Exit ]                                  │
└────────────────────────────────────────────┘
```

**Option 2: Add to Coach Window**
```
Coach Window toolbar:
[ Capture ]  [ Review Session ]  [ Settings ]
     ↑              ↑                ↑
  Current       NEW option       Existing
```

**Recommendation:** Option 2 (add to Coach Window) - keeps all coaching workflows in one place.

---

## Implementation Plan

### Phase 1: Core Infrastructure (Week 1)
**Goal:** Basic session loading and playback

1. **Day 1-2:** Session Loader
   - Implement `SessionLoader` class
   - Parse session/pitch manifests
   - Validate directory structure
   - Load video file paths

2. **Day 3-4:** Video Reader
   - Implement `VideoReader` class
   - Frame-by-frame reading
   - Seek functionality
   - Synchronization between left/right

3. **Day 5:** Review Service (Basic)
   - Implement `ReviewService` class
   - Load session
   - Basic playback control
   - Frame retrieval

**Deliverable:** Can load session and read frames programmatically

---

### Phase 2: UI Foundation (Week 2)
**Goal:** Basic review window with video playback

1. **Day 1-2:** Review Window Shell
   - Create `ReviewWindow` class
   - Layout with video displays
   - Playback controls (play/pause/seek)

2. **Day 3-4:** Video Display
   - Dual video player widgets
   - Frame rendering
   - Overlay detections

3. **Day 5:** Timeline Integration
   - Scrubber widget
   - Pitch markers
   - Frame navigation

**Deliverable:** Can open session and watch videos with basic controls

---

### Phase 3: Detection Integration (Week 3)
**Goal:** Re-run detection on loaded videos

1. **Day 1-2:** Detection Pipeline Connection
   - Integrate classical detector
   - Run detection on current frame
   - Compare with original detections

2. **Day 3-4:** Parameter Tuning Panel
   - Adjustable sliders for all parameters
   - Real-time detection updates
   - Reset/apply functionality

3. **Day 5:** Visual Comparison
   - Original vs new detection overlay
   - Color-coded markers
   - Diff view

**Deliverable:** Can tune parameters and see detection improve

---

### Phase 4: Annotation & Export (Week 4)
**Goal:** Scoring, annotation, and export

1. **Day 1-2:** Pitch Scoring
   - Pitch list sidebar
   - Score pitches (good/missed/partial)
   - Statistics summary

2. **Day 3:** Manual Annotation
   - Click to add manual ball markers
   - Frame-by-frame annotation
   - Annotation storage

3. **Day 4:** Export Functionality
   - Export tuned configuration
   - Export annotations to JSON
   - Export comparison report

4. **Day 5:** Polish & Testing
   - Bug fixes
   - UX improvements
   - Documentation

**Deliverable:** Fully functional review/training mode

---

## Data Structures

### Annotation Format

```json
{
  "session_id": "session-2026-01-18_001",
  "annotations": [
    {
      "frame_index": 125,
      "timestamp_ns": 4166666666,
      "left_annotations": [
        {
          "x": 640.5,
          "y": 360.2,
          "type": "manual",
          "confidence": 1.0,
          "note": "Ball missed by detector"
        }
      ],
      "right_annotations": [...],
      "pitch_score": "good"
    }
  ],
  "detector_config": {
    "mode": "MODE_A",
    "frame_diff_threshold": 18.0,
    ...
  }
}
```

---

## Technical Considerations

### Performance

**Challenge:** Re-running detection on every frame during playback

**Solutions:**
1. **Cache Results:** Cache detection results for each frame
2. **Background Processing:** Run detection in background thread
3. **Lazy Evaluation:** Only run detection when parameters change
4. **Frame Skipping:** Allow lower-quality preview mode (every Nth frame)

### Memory

**Challenge:** Loading large video files into memory

**Solutions:**
1. **Streaming:** Read frames on-demand (don't load entire video)
2. **Frame Cache:** Keep small LRU cache of recent frames
3. **Thumbnail Preview:** Generate thumbnail strip for timeline

### Video Format Compatibility

**Challenge:** Recorded videos may be grayscale or color

**Solutions:**
1. **Auto-detect:** Check video format on load
2. **Convert:** Convert grayscale to RGB for display if needed
3. **Pass-through:** Support both formats in detection pipeline

---

## Configuration Options

Add to `configs/default.yaml`:

```yaml
review_mode:
  cache_size: 100  # Number of frames to cache
  preview_quality: high  # high, medium, low (affects frame skip)
  auto_save_annotations: true
  comparison_colors:
    original: [255, 0, 0]  # Red
    new: [0, 255, 0]  # Green
    both: [255, 255, 0]  # Yellow
```

---

## API Design

### Review Service Public API

```python
# Load session
service = ReviewService()
session = service.load_session(Path("recordings/session-001"))

# Playback control
service.start_playback(speed=1.0)
service.pause_playback()
service.seek_to_pitch(pitch_index=2)

# Detection
service.update_detector_config(new_config)
detections_left, detections_right = service.run_detection()

# Annotation
annotation = Annotation(x=640, y=360, type="manual")
service.add_annotation(frame_index=125, annotation=annotation)

# Export
service.export_config(Path("tuned_config.yaml"))
service.export_annotations(Path("annotations.json"))
```

---

## Testing Strategy

### Unit Tests

1. **SessionLoader:** Test with mock session directories
2. **VideoReader:** Test seek, read, frame count
3. **ReviewService:** Test state management, playback control

### Integration Tests

1. **End-to-End:** Load real session, playback, run detection
2. **Parameter Tuning:** Verify parameter changes affect detection
3. **Export:** Verify exported configs are valid

### Manual Testing

1. **Usability:** Coaches test with real sessions
2. **Performance:** Benchmark with various video sizes
3. **Edge Cases:** Corrupted videos, missing files, etc.

---

## Future Enhancements

### Phase 5+: Advanced Features

1. **Batch Processing**
   - Process multiple sessions at once
   - Export aggregate statistics
   - Find optimal parameters across sessions

2. **ML Model Training**
   - Export annotations in COCO format
   - Train custom ball detector
   - A/B test classical vs ML detection

3. **Comparison Mode**
   - Load same session with different configs
   - Side-by-side comparison
   - Statistical analysis

4. **Collaborative Annotation**
   - Multiple users annotate same session
   - Consensus scoring
   - Inter-rater reliability metrics

---

## File Structure

```
ui/review/
├── __init__.py
├── review_window.py          # Main review window
├── video_player_widget.py    # Video display widget
├── timeline_widget.py         # Timeline scrubber
├── parameter_panel.py         # Detection parameter tuning
├── pitch_list_widget.py       # Pitch list sidebar
└── comparison_widget.py       # Original vs new comparison

app/review/
├── __init__.py
├── video_reader.py            # Video file reading
├── playback_controller.py     # Playback state management
└── annotation_manager.py      # Annotation storage/retrieval

app/pipeline/
├── session_loader.py          # Load recorded sessions

docs/
├── REVIEW_MODE_USER_GUIDE.md  # End-user documentation
└── REVIEW_MODE_DESIGN.md      # This document
```

---

## Success Metrics

**Feature is successful if:**

1. **Usability:** Coaches can load and review sessions in < 30 seconds
2. **Performance:** Playback is smooth at 1x speed (30-60 fps)
3. **Accuracy:** Parameter tuning improves detection by measurable amount
4. **Adoption:** 50%+ of users try review mode within first month

---

## Open Questions

1. **Should we support real-time vs post-processing?**
   - Real-time: Run detection during playback (may be slow)
   - Post-processing: Pre-compute all frames first (faster playback)

2. **How to handle manual annotations?**
   - Click to place markers?
   - Draw bounding boxes?
   - Import from external tool?

3. **Export format for annotations?**
   - Custom JSON?
   - COCO format for ML training?
   - CSV for spreadsheet analysis?

4. **Integration with main workflow?**
   - Separate window?
   - Mode within coach window?
   - Standalone application?

**Recommendation:** Start with real-time processing, click-to-annotate, custom JSON, and integration into coach window.

---

## Conclusion

Review/Training Mode is a powerful feature that enables iterative improvement of detection accuracy. The phased implementation plan allows for incremental delivery and user feedback.

**Estimated Effort:** 3-4 weeks for full implementation
**Priority:** Medium (nice-to-have enhancement)
**Complexity:** High (new UI paradigm, video processing, state management)

**Next Steps:**
1. Review and approve design
2. Create detailed task breakdown
3. Implement Phase 1 (Session Loader + Video Reader)
4. User testing with prototype

---

**Document Version:** 1.0
**Last Updated:** 2026-01-18
**Author:** PitchTracker Development Team
**Status:** Design - Awaiting Approval
