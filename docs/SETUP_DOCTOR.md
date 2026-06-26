# Setup Doctor Manual Validation

Use this checklist for real fixed-rig validation before a coaching session.

Setup Doctor runs the stages below in order. Each stage produces `PASS`, `WARN`,
or `CRITICAL`; coaching startup blocks only on `CRITICAL`. Saving the report
writes `setup_report.json` next to the active rig profile.

1. Camera assignment
   - Confirm left and right serials match the active rig profile.
   - Confirm the selected backend matches the active rig profile.

2. Focus and exposure stability
   - Lock manual focus where the camera supports it.
   - Confirm focus scores remain stable after warm-up.
   - Confirm exposure does not hunt under field lighting.

3. Physical alignment
   - Use software correction for stable image roll and small vertical offset.
   - Physically adjust cameras for focus mismatch, major toe-in, poor overlap, or unstable mounts.
   - Re-run alignment after tightening mounts.

4. ChArUco metadata
   - Verify board pattern, square size, and marker dictionary before capture.
   - Keep the board flat and fully visible in both cameras.

5. Full calibration capture
   - Capture at least 10 valid stereo poses; 15 or more is preferred.
   - Cover the full tracking volume with varied board positions and angles.
   - Reject pose pairs where either camera fails corner detection.

6. Full stereo calibration
   - Use full matrix calibration for production readiness.
   - Treat quick calibration as diagnostic or fallback-only.
   - Review RMS error, per-image errors, rejected pairs, and quality rating.

7. ROI coverage
   - Save lane and plate ROIs to the active rig profile ROI file.
   - Confirm both left and right lane ROIs cover the full expected pitch path.
   - Confirm plate ROI covers the front edge and strike-zone crossing area.

8. Runtime dry-run
   - Start production capture from the active rig profile.
   - Confirm transforms are visible in preview.
   - Confirm calibrated stereo matcher loads from the profile calibration file.
   - Confirm ROI reload updates lane and plate gated detections.
   - Do not start coaching if Setup Doctor reports `CRITICAL`.
