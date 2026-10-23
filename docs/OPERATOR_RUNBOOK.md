# Operator Daily-Session Runbook

**Last reviewed:** 2026-10-14
**Applies to:** v2.0.0 and current `main`

This runbook covers the repeatable steps for each coaching session. It assumes
the rig has already been set up and the setup snapshot is current and eligible.
For first-time setup, start with [Guided Setup](GUIDED_SETUP.md) and its
five-stage workflow. The workspace opens without acquiring cameras.

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
2. Choose **Setup**, then **Open Guided Setup**. Review the saved rig revision,
   complete the five stages and resolve the named blockers before publication.
3. Use explicit setup camera actions to check the pair, frame rate and timing.
   Stop setup acquisition before preparing runtime preview.
4. Confirm saved setup readiness for estimated research recording. Readiness
   does not grant physical accuracy approval. Pending rig edits and stale checks
   must be resolved through Setup; changing pages does not resolve them.

> If the snapshot is ineligible or the rig was moved, rerun the relevant setup
> steps and persist a fresh snapshot before recording.

---

## Recording a session

1. Go to **Live** and choose **Prepare Session**. Enter a session name, select
   a roster label and confirm the session settings. Preparation requests preview.
2. Review the preview, frame rate and named prerequisites. **Ready** means
   recording can be requested; it does not mean recording has started.
3. Choose **Start Recording** and wait for confirmed **Recording** status.
   Remain at the computer to monitor tracking and errors.
4. Use **Pause** and **Resume Recording** as needed. Page navigation keeps
   recording active, and the workspace status remains visible on every page.
5. Choose **End Session** after the final pitch. Wait through **Finalizing**
   until **Completed**, then choose **Review Session**. If finalization fails,
   follow the supported recovery action; a failure does not confirm closure.
6. Do not disconnect cameras until recording and capture have closed. Use
   **Stop Preview** explicitly before rig edits. Do not infer shutdown from navigation.

**Players** browsing never changes runtime attribution. **Use as active pitcher**
is an explicit command; a pending change takes effect at a safe pitch boundary.
Previously recorded pitch labels are retained after roster edits.

---

## Between pitches

- Watch the detection health overlay; report persistent miss warnings in the
  session log.
- Do not move the rig or cameras mid-session. Any repositioning invalidates
  the current snapshot and requires a new setup pass.
- Record environmental changes (lighting shift or rig movement) in your local
  operator notes without uploading private session data.

---

## Post-session review

1. Choose **Review Session** after confirmed completion, or browse **Sessions**
   and open a completed recording. Historical selection is separate from runtime recording.
2. Step through each pitch and confirm the evidence indicators (track length,
   confidence, stereo quality, correction flags) are within expected ranges.
3. Use the available local export action for the selected session if needed.
4. Retain unavailable and rejected pitches in your review denominator. Source,
   reference and recorded status qualify speed values; unavailable is not zero
   or a normal ball call. Movement remains unavailable without validation.

---

## Shutdown

1. End the session and stop preview explicitly, then close the application.
   Closing while recording offers **End Session and Exit** or **Cancel**.
   Cancel keeps the session running; requested exit waits for worker cleanup.
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
