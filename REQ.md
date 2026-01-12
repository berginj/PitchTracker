# Portable Stereo Pitch Tracking (Option B) — Requirements (REQ.md)

## 0) Goal
Build a portable real-time stereo computer vision app that tracks baseball/softball pitches using two USB3 global-shutter cameras on a rigid mount and computes 3D trajectory + pitch metrics locally on a laptop with low latency.

### Quick install
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Hard Constraints
- Two cameras streaming simultaneously into ONE laptop via USB3
- Target mode: 1920x1080 @ 60 fps per camera
- End-to-end latency (capture → metrics): p95 ≤ 500 ms
- Manual lock: exposure, gain, white balance (or grayscale pipeline), focus (lens), FPS, resolution
- No seam-based spin estimation in v1

### Outputs per pitch
- 3D trajectory (time series)
- Velocity (mph)
- Horizontal break (in)
- Induced vertical break (in)
- Release point estimate (x,y,z)
- Approach angles (horizontal + vertical) near plate
- Confidence + diagnostics + latency metrics

### Implementation Status (current repo)
- PySide6 UI with in-process pipeline service and capture/replay.
- Lane + plate ROI calibration with strike-zone 3x3 overlay.
- Classical detector with ROI cropping and optional ONNX ML detector + validator.
- Per-pitch recording bundles with manifest, timestamps, and config snapshot.
- Plate plane calibration tool with persistent logging.

---

## 1) System Architecture (Modules + Interfaces)
Repository layout (required):
- /capture
- /calib
- /rectify
- /detect
- /stereo
- /track
- /metrics
- /telemetry
- /ui
- /record
- /tests
- /configs

### 1.2 App Architecture Commitment (UI + Service)
- UI must be PySide6 (Qt) for v1.
- The processing pipeline must run as a service layer with a stable API boundary.
- The UI must call the service via explicit interfaces; avoid Qt types in core pipeline code.
- Service must be usable in-process for v1 and swappable for IPC in future (D path).
- Core contracts (data types + config) must be serializable (JSON/YAML) to enable non-Python engines.

### 1.1 Camera Abstraction
Implement interface `CameraDevice` with:
- open(serial: str) -> None
- set_mode(width:int, height:int, fps:int, pixfmt:str) -> None
- set_controls(exposure_us:int, gain:float, wb_mode:str|None, wb:int|None) -> None
- read_frame(timeout_ms:int) -> Frame
- get_stats() -> CameraStats
- close() -> None

Backends (must support both):
- UVC backend (preferred default)
- Vendor SDK backend (optional, if required to reach performance)

### 1.2 Data Contracts (Required Types)
#### Frame
- camera_id: str (serial)
- frame_index: int
- t_capture_monotonic_ns: int  (monotonic timestamp at arrival to app)
- image: ndarray / cv::Mat
- width: int
- height: int
- pixfmt: str

#### Detection
- camera_id: str
- frame_index: int
- t_capture_monotonic_ns: int
- u: float
- v: float
- radius_px: float
- confidence: float

#### StereoObservation
- t_ns: int
- left: (u,v)
- right: (u,v)
- X,Y,Z: float (rig coordinates)
- quality: float
- covariance (optional): 3x3
- confidence: float

#### TrackSample
- t_ns: int
- X,Y,Z: float
- Vx,Vy,Vz: float
- Ax,Ay,Az: float (optional)
- quality_flags: bitset/int

#### PitchMetrics
- pitch_id: str
- t_start_ns: int
- t_end_ns: int
- velo_mph: float
- HB_in: float
- iVB_in: float
- release_xyz_ft: (float,float,float)
- approach_angles_deg: (float horizontal, float vertical)
- confidence: float
- diagnostics: dict
- latency: dict (p50,p95, max)

### 1.3 Service API (Pipeline)
Provide a service interface that the UI uses (in-process for v1) with:
- start_capture(config, left_serial, right_serial) -> None
- stop_capture() -> None
- get_preview_frames() -> (left Frame, right Frame)
- start_recording(pitch_id: str | None) -> None
- stop_recording() -> RecordingBundle
- run_calibration(profile_id: str) -> CalibrationProfile
- get_stats() -> dict (fps, jitter, drop rate, latency)

### 1.4 Contract Versioning (Cross-Language Safe)
- All serialized payloads must include a `schema_version` string (semver).
- Contract changes that break compatibility must bump the MAJOR version.
- Backward-compatible additions must bump MINOR; PATCH for bugfixes only.
- UI must declare the supported schema range; service must reject unsupported versions.
- Each persisted artifact (recordings, calibration profiles, metrics) must embed:
  - `schema_version`
  - `app_version`
  - `rig_id` (if known)
  - `created_utc` timestamp (ISO 8601)

Example (recording manifest):
```json
{
  "schema_version": "1.0.0",
  "app_version": "0.2.0",
  "rig_id": "rig-01",
  "created_utc": "2026-01-11T17:05:00Z",
  "pitch_id": "pitch-2026-01-11-001",
  "left_video": "left.avi",
  "right_video": "right.avi",
  "left_timestamps": "left_timestamps.csv",
  "right_timestamps": "right_timestamps.csv",
  "config_path": "configs/default.yaml",
  "calibration_profile_id": "profile-2026-01-11-01"
}
```

### 1.5 Extensibility Requirements (Path to D)
- Pipeline logic must live in non-UI modules; UI must not import cv2 directly.
- All inputs/outputs that cross the UI boundary must be versioned and serializable.
- Capture, detection, stereo, tracking, and metrics modules must be replaceable without UI changes.
- Prefer pure functions for math-heavy code to ease porting to C++/Rust.

---

## 2) Capture Layer Requirements
### 2.1 Modes
- Default mode: 1920x1080 @ 60 fps
- Pixel formats allowed: GRAY8 (best), YUY2, MJPG (fallback)
- Must select cameras by serial number

### 2.2 Controls (must be lockable)
- Exposure: manual, set by exposure_us
- Gain: manual
- White balance: fixed OR grayscale-only pipeline
- Focus: fixed (lens); app must treat focus as constant after calibration

### 2.3 Threading / Queues
- One capture thread per camera
- Lock-free or minimal-lock queues to processing
- Each camera queue depth configurable; default = 6 frames
- Detect and log dropped frames

### 2.4 Capture Diagnostics (live)
- fps (avg + instant)
- jitter (timestamp delta p95)
- dropped frames count/rate
- queue depth
- per-camera capture-to-process latency

#### FAIL CONDITIONS (run-time)
- avg fps < 58 sustained for 2 seconds -> WARN "capture unstable"
- drop rate > 2% -> WARN "drops"
- queue depth > 6 sustained -> WARN "pipeline behind"

---

## 3) Calibration / Geometry Requirements
### 3.1 Intrinsics Calibration
- Prefer Charuco board, fallback checkerboard
- Store: K, distortion coeffs, reprojection error per camera
- Quality gate: intrinsics reprojection error < 0.6 px

### 3.2 Stereo Calibration
- Store: R, T, essential/fundamental matrices
- Produce rectification maps for runtime
- Quality gate: stereo reprojection error < 0.8 px

### 3.3 Profiles
- Calibration profile key MUST include:
  - left_serial, right_serial
  - lens_id_left, lens_id_right (strings)
  - measured_baseline_ft (float)
  - rig_id (string)
- Must refuse "metrics mode" if serials mismatch profile unless user override flag is set

### 3.4 Baseline Consistency Gate
- Estimated baseline from calibration must be within ±2% of measured baseline

---

## 4) Rectification Requirements
- Precompute rectification maps from profile
- Runtime rectification per frame
- Time budget: ≤ 2 ms per camera per frame (CPU)

---

## 5) Ball Detection Requirements (v1 Classical CV)
### 5.1 Detector Outputs
- Produce 0..N candidates per frame with (u,v,radius,confidence)

### 5.2 Required Operating Modes
- MODE_A: frame differencing / background subtraction + blob filtering
- MODE_B: edge/blob hybrid (for busy backgrounds)

### 5.3 Filtering Constraints
- Must reject obvious non-ball blobs using:
  - area range
  - circularity/compactness
  - velocity consistency (temporal)
- Must run in ≤ 4 ms per camera per frame (CPU)

### 5.4 Detector Health Checks
- Idle false positives: ≤ configurable threshold (default 1 per second)
- If no detections for >0.5s during an active pitch window -> WARN "miss"

---

## 6) Stereo Association + 3D Triangulation Requirements
### 6.1 Frame Pairing (no hardware sync)
- Pair frames by closest timestamp
- Max pairing tolerance: default 8 ms (configurable)

### 6.2 Matching (rectified space)
- Epipolar constraint: |yL - yR| < epsilon (default 3 px)
- Choose match minimizing:
  - epipolar residual + motion consistency penalty

### 6.3 Triangulation
- Use projection matrices or Q matrix
- Output 3D point (rig coordinates) + quality/confidence

### 6.4 Outlier Rejection Gates
Reject observation if any:
- Z outside [3 ft, 80 ft] (configurable)
- disparity outside plausible range
- 3D jump > 12 inches vs predicted in one frame (unless first samples)

---

## 7) Tracking + Smoothing Requirements
### 7.1 Tracker
- Kalman filter constant-acceleration preferred
- State includes position and velocity (acceleration optional)
- Must handle missing observations up to 100 ms

### 7.2 Gating
- Observation accepted if within predicted gating region (3D distance threshold)

### 7.3 Track Quality Gates
- Minimum track length: 20 frames (configurable)
- If innovation residual high for >N frames -> WARN "bad association or calibration"

---

## 8) Metrics Requirements
### 8.1 Coordinate System (must define and enforce)
- Rig coordinates:
  - X: catcher left-right (ft)
  - Y: vertical (ft)
  - Z: toward pitcher (ft) OR toward plate (ft)
- Must be consistent across modules and saved in outputs

### 8.2 Planes
- Plate plane: Z = 0 (configurable)
- Release plane: default Z = 50 ft from plate (configurable)

### 8.3 Metrics Computation
- Velo: speed near release segment (configurable window)
- HB: lateral deviation vs gravity-only model
- iVB: vertical deviation vs gravity-only model
- Release point: extrapolate trajectory to release plane
- Approach angles: compute at last N feet before plate (default N=5 ft)

### 8.4 Sanity Bounds
Flag as low-confidence if out of bounds:
- velo: 30..110 mph
- HB: -30..+30 inches
- iVB: -30..+30 inches
- release height: 1..8 ft

---

## 9) Telemetry + Latency Requirements
### 9.1 Latency Measurement
- Each PitchMetrics bundle includes:
  - capture timestamps used
  - compute start/end timestamps
  - derived end-to-end latency

### 9.2 Rolling Stats
- p50/p95 latency
- fps per camera
- drop rate
- track success rate

### 9.3 Real-time Gate
- If p95 latency > 500 ms for >10 pitches -> WARN "not real-time"

---

## 10) Recording + Replay Requirements (mandatory for debugging)
### 10.1 Pitch Capture Bundle
- Save raw frames from both cams for window around pitch event
- Save timestamps + calibration profile ID + config snapshot
- Save derived detections and metrics as JSON

### 10.2 Deterministic Replay
- Must replay from saved frames producing identical metrics within tolerance:
  - velo std dev ≤ 0.2 mph over 10 replays
  - break std dev ≤ 0.3 inches over 10 replays

---

## 11) UI Requirements (minimum viable)
- Live rectified side-by-side view
- Overlay detections and matched pairs
- Simple 3D trajectory visualization (can be basic)
- Toggle UI refresh rate (e.g., 15 Hz) independent of processing rate
- One-click "record pitch" and "replay last pitch"
- Must be implemented in PySide6 and communicate with the pipeline service via interfaces.

---

## 12) Automated Test Plan (must implement in /tests)
### 12.1 Capture Stability Test (2 minutes)
PASS if:
- avg fps ≥ 59
- drop rate ≤ 1%
- timestamp jitter p95 ≤ 5 ms

### 12.2 Calibration Quality Test
PASS if:
- intrinsics reprojection < 0.6 px
- stereo reprojection < 0.8 px
- baseline estimate within ±2% of measured

### 12.3 Synthetic Motion Test
Use a ball-on-string or controlled motion sequence.
PASS if:
- detections continuous ≥ 95%
- triangulated Z monotonic as expected
- no 3D jumps > 6 inches frame-to-frame (after filter)

### 12.4 Latency Test
PASS if:
- p95 end-to-end ≤ 500 ms with UI ON
- p95 end-to-end ≤ 250 ms with UI OFF (target)

### 12.5 Repeatability Test (Replay)
PASS if:
- velo std dev ≤ 0.2 mph over 10 replays
- break std dev ≤ 0.3 inches over 10 replays

---

## 13) Configuration (required)
All tunables must live in versioned config files:
- camera mode, pixfmt, exposure_us, gain
- pairing tolerance, epipolar epsilon
- gating thresholds, sanity bounds
- planes, coordinate definition
- record window sizes
- UI refresh rate

## 14) Definition of Done (v1)
- Runs with two Option B cameras at 1080p60
- Produces stable 3D tracks on real pitches with track success ≥ 95% in controlled environment
- p95 latency ≤ 500 ms
- Recording + deterministic replay works
- Automated tests exist and pass on a target laptop

## 15) Training Guide
See `TRAINING.md` for dataset capture, labeling, and configuration guidance.

## 16) SWA Export + API Contract (Azure Static Web Apps)
Goal: A separate SWA repo ingests session summaries for dashboards (heatmap, strikes/balls, pitcher summaries).

Shared contract source of truth:
- Submodule: `contracts-shared/`
- Schema file: `contracts-shared/schema/session_summary.schema.json`

### 16.1 Export Artifact (from this app)
The app must write a JSON summary file per session:
- Path: `<recordings>/<session_id>/session_summary.json`
- JSON schema:
```json
{
  "schema_version": "1.0.0",
  "app_version": "0.2.0",
  "session_id": "session-2026-01-11-001",
  "pitch_count": 12,
  "strikes": 7,
  "balls": 5,
  "heatmap": [[1,2,0],[0,3,1],[0,1,4]],
  "pitches": [
    {
      "pitch_id": "session-2026-01-11-001-pitch-001",
      "t_start_ns": 0,
      "t_end_ns": 0,
      "is_strike": true,
      "zone_row": 2,
      "zone_col": 1,
      "run_in": 3.2,
      "rise_in": -1.1,
      "speed_mph": 62.5,
      "rotation_rpm": null,
      "sample_count": 18
    }
  ]
}
```

### 16.2 SWA Functions API (new repo)
The SWA Functions API ingests the JSON summary and exposes it for the UI.

#### POST `/api/sessions`
Body: session_summary.json payload (as above).  
Response: `{ "session_id": "..." }`

#### GET `/api/sessions`
Response: list of session metadata (id, date, pitch_count, strikes, balls).

#### GET `/api/sessions/{session_id}`
Response: full session summary JSON.

### 16.3 Authentication
SWA Functions must require either:
- a shared API key header (e.g., `x-api-key`), or
- SWA built-in auth if enabled.

### 16.4 Backwards Compatibility
SWA must accept compatible schema versions; reject unknown major versions.
