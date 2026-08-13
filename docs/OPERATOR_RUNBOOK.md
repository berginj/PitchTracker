# Operator Daily-Session Runbook

**Last reviewed:** 2026-08-11
**Applies to:** v2.0.0 and current `main`

This runbook covers the repeatable steps for each coaching session. It assumes
the rig has already been set up and the setup snapshot is current and eligible.
For first-time setup, start with [QUICK_START.md](QUICK_START.md) and the
ten-step wizard.

---

## Before arriving at the facility

- [ ] Confirm the cameras, cables, USB hubs (if any), and ChArUco target are
      packed.
- [ ] Verify the laptop has sufficient disk space for session recordings
      (estimate ~4–5 GB per 20-pitch full session).
- [ ] Check that the last saved rig profile matches today's planned camera pair
      and mounting position.

---

## Hardware setup

1. Mount both cameras to the rig. Tighten all fasteners; confirm the rig does
   not shift after handling.
2. Connect cameras directly to USB 3.x ports. Avoid hubs unless previously
   qualified.
3. Position the rig so both cameras have overlapping coverage of the intended
   pitch volume and the strike zone is within frame.
4. Record the baseline measurement if the rig has been moved since last use.

---

## Launch and preflight

1. Open a PowerShell terminal and activate the virtual environment:
   ```powershell
   .\.venv\Scripts\Activate.ps1
   python launcher.py
   ```
2. Choose **Setup & Calibration** and run the setup quality report. Review the
   ten-step checklist summary; resolve any blockers before proceeding.
3. Confirm both camera previews are live, achieve the target FPS, and show
   healthy synchronization.
4. Verify that the current setup snapshot is eligible (no expired approval,
   no missing artifact hash). The UI displays eligibility status on the
   dashboard.

> If the snapshot is ineligible or the rig was moved, rerun the relevant setup
> steps and persist a fresh snapshot before recording.

---

## Recording a session

1. Return to the launcher, choose **Coaching Sessions**, and enter a session
   name (use a consistent convention, e.g., `YYYYMMDD_location_pitcher-id`).
2. Confirm both previews, achieved FPS, and health indicators are green.
3. Resolve any blocking warnings before starting a named session.
4. Click **Start Session** and record pitches. Remain at the computer to
   monitor the health dashboard.
5. After the last pitch, click **Stop Recording** and wait for the recording
   service to close cleanly (the status indicator returns to idle).
6. Do not disconnect cameras until recording closes.

---

## Between pitches

- Watch the detection health overlay; report persistent miss warnings in the
  session log.
- Do not move the rig or cameras mid-session. Any repositioning invalidates
  the current snapshot and requires a new setup pass.
- Note any environmental changes (lighting shift, crowd movement) in the
  session notes field.

---

## Post-session review

1. From the launcher choose **Review**, open today's session.
2. Step through each pitch and confirm the evidence indicators (track length,
   confidence, stereo quality, correction flags) are within expected ranges.
3. Export the session summary if needed (`File → Export Session Summary`).
4. Note any pitches flagged as `DEGRADED` or `REJECTED` and record the reason.

---

## Shutdown

1. Stop capture and close the application cleanly.
2. Back up the `recordings/` output directory and the current rig profile
   (`calibration/rigs/`) to secure storage before powering down.
3. Do not commit raw recordings, calibration artifacts, athlete names, or
   facility details to the public repository.

---

## Quick-reference troubleshooting

| Symptom | First action |
|---|---|
| Camera not detected | Check USB port, try a different USB 3.x port, see [CAMERA_RECONNECTION.md](CAMERA_RECONNECTION.md) |
| FPS below 58 sustained | Check USB bandwidth, close background apps, see [TROUBLESHOOTING.md](user/TROUBLESHOOTING.md) |
| Setup snapshot ineligible | Re-run affected setup steps, persist a new snapshot |
| Persistent miss warnings | Check lane ROI alignment, lighting, and detection config |
| Recording did not close | Check disk space; see logs in `logs/` for errors |

For full diagnostics, see [TROUBLESHOOTING.md](user/TROUBLESHOOTING.md) and
[CALIBRATION_TROUBLESHOOTING.md](CALIBRATION_TROUBLESHOOTING.md).
