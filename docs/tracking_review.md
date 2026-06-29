# Ball Detection And Tracking Review

## Verdict

The current detector is a reasonable prototype for controlled indoor tests. It is not robust enough by itself for outdoor baseball/softball tracking behind a catcher. The system needs a detection evidence model, temporal association, stereo-aware matching, and pitch-level rejection reasons before it can be trusted.

## Candidate Detection

Current approach:

- `detect/classical_detector.py` runs frame differencing/background differencing or edge/blob masks from `detect/modes.py`.
- `detect/filters.py` filters by area, circularity, optional velocity, and optional lane ROI.
- Detection confidence is derived mostly from blob circularity.
- ML detector hooks exist, but default config uses `classical`.

Strengths:

- Fast enough for real-time capture-side detection.
- Simple, testable, and works with simulator-style inputs.
- ROI cropping reduces compute and some false positives.

Weaknesses:

- Outdoor lighting, shadows, dirt, grass, uniforms, bat/glove motion, catcher movement, and fences can all trigger blob candidates.
- Circularity is a weak confidence signal for blurred fast balls and bright non-ball objects.
- The detector does not model expected ball radius as a function of depth, baseball vs softball size, exposure, or blur.
- Background adaptation can absorb slow or repeated motion and can be disturbed by lighting changes.
- There is no durable per-candidate explanation beyond center, radius, and confidence.

## Temporal Tracking

Current approach:

- `PitchStateMachineV2` owns lifecycle transitions and filters too-short or under-observed pitches.
- `TimestampedTrajectoryTracker` fits a small polynomial window for live observation updates.
- Final analysis fits a trajectory after pitch end.

Failure risks:

- A false stereo observation can drive pitch activity.
- Missed detections are not handled as a first-class state in detection association.
- There is no multi-hypothesis track model, no Kalman/smoother pass over candidates, and no robust frame-to-frame assignment.
- Velocity gating exists as a simple filter, but the final tracker does not use a full physical prior during candidate selection.

Required redesign:

- Treat detection output as candidates, not facts.
- Build per-camera tracks with motion priors, missed-detection handling, candidate costs, and rejection reasons.
- Carry multiple candidates into stereo matching when needed, but select a globally consistent pitch track offline.
- Prefer offline smoothing and robust fitting over real-time display needs.

## Stereo Correspondence

Current approach:

- `DetectionProcessor` pairs frames by timestamp or frame index.
- `build_stereo_matches()` tries each left/right detection pair.
- `SimpleStereoMatcher` uses horizontal row tolerance.
- `CalibratedStereoMatcher` uses symmetric epipolar error from `F`.

Weaknesses:

- Matching is local and pairwise. It does not solve for the globally best sequence across time.
- Time offset is configured but not estimated per session before matching.
- One-camera dropouts are only useful for ray comparison modes, not as a first-class stereo tracking path.
- Triangulated observations do not include covariance, pixel residuals, or ambiguity score.

Needed behavior:

- Frame pairing must produce measured sync diagnostics and reject bad sessions.
- Stereo matching should use epipolar distance, descriptor/detection confidence, expected ball radius, temporal velocity prior, and global path consistency.
- One-camera rays should remain available and contribute to offline path fitting when stereo point triangulation is sparse.

## Quality Scoring

Current quality signals:

- Per-detection confidence.
- Epipolar error per stereo match.
- Observation confidence set to zero if depth is out of range.
- Trajectory diagnostics with RMSE, inlier ratio, failure codes, and expected plate error.
- Pitch validity checks for observation count and duration.

Missing quality signals:

- Candidate rejection reason per frame.
- Per-camera track confidence.
- Stereo ambiguity score when multiple matches satisfy epipolar constraints.
- Triangulation uncertainty and reprojection residual per observation.
- Pitch-level reasons such as poor sync, sparse coverage, non-monotonic Z, implausible speed, no plate crossing, high residuals, and excessive one-camera dropout.

Minimum acceptance rules for reliable MVP:

- Reject pitches without a production-ready calibration and passing sync report.
- Reject paths with non-monotonic travel toward plate, implausible speed, no plate crossing, excessive p95 residual, or too little Z span.
- Require at least one durable diagnostic artifact explaining why each pitch was accepted or rejected.
