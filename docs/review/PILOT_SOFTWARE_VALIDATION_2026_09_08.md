# Controlled-pilot software validation — 2026-09-08

## Provenance and scope

Base commit: `1f83691f87900c73c94fcf3299bd8a0e9b783b3d`, plus the uncommitted
controlled-pilot implementation. No release, commit, push, or physical accuracy
approval was created. Tests used Windows 11, Python 3.13.14, NumPy 2.2.2,
SciPy 1.17.0, OpenCV 4.10, and PyInstaller 6.18.0.

No physical camera capture was performed. Frozen setup testing explicitly used
the simulator. No private recordings or calibration artifacts were uploaded.

## Automated results

| Gate | Result |
|---|---|
| Full Windows suite, native UVC probe disabled, two loadscope workers | 1,722 passed; 32 skipped; 37 warnings; exit 0; 374.37 s |
| Final frozen-worker smoke tests | 4 passed; 17.80 s |
| Repository-wide mypy, no incremental cache | Clean; 735 source files |
| Flake8 | Zero findings |
| Schema mirror | In sync |
| Public documentation | Passed, 13 checked files |
| Typing suppression policy | Passed |
| 500-line gate | Passed; zero grandfathered files; 18 new Python files also checked |
| Windows-aware whitespace check | Passed using `core.whitespace=cr-at-eol` for the repository's mixed line endings |

Local XML results are in `validation_output/pilot-tests.xml` and
`validation_output/pilot-packaged-tests.xml` (ignored build/test evidence).
The four opt-in packaged tests normally skip without `PITCHTRACKER_PACKAGED_DIR`;
they were explicitly run against the final artifact. Other skips retain their
existing environment/display/dependency guards. Existing warnings include
Matplotlib deprecations and a ChArUco test returning a value; the full count is
not a claim that every hardware/calibration path was exercised.

Regressions cover distorted-pixel geometry, continuous strike intersection,
independent numerical truth, covariance/identifiability, failure eligibility,
timing and speed provenance, actual child timeout/reaping/recovery, reply
correlation, queue telemetry, and timestamp persistence. An initial full run
exposed outdated provenance/UI fixtures and unnecessary fitting of stationary
tracks. These were corrected before the passing full rerun.

## Local bundle

Final output: `dist/pilot-quality-final/PitchTracker/`. The earlier
`dist/pilot-quality/` output was preserved. The bundle contains the GUI and its
dedicated console worker; no signed Inno installer was produced in this run.

- `PitchTracker.exe` SHA-256:
  `C1BEE79119D186241E2D7C9E72F43A3F1D89D8FD9E68A98D50D1E86B436C7736`
- `PitchTrackerWorker.exe` SHA-256:
  `F2ABF7AB953800254FC7033C761ABDDEBD9FD62529030F2E73D2E27DB7B80B09`

Smoke coverage: health/probe-help dispatch without cameras, synthetic fit
matching source, simulator setup capture, and tooling environment validation.
The probe help test found and drove a dispatcher argument-routing fix.
PyInstaller reported unresolved Windows system-DLL/optional-import warnings;
local worker success does not replace testing on a clean Windows installation.

## Numerical envelope, not physical approval

The independent fixed-seed 12-case sweep uses 30/60/90 mph, 0.1/0.3 s windows,
0.005 ft synthetic noise, and zero/30 ft/s² transverse acceleration. All six
zero-transverse-force cases passed the fit gate (maximum absolute speed error
0.133 mph in these inputs). Added transverse force was rejected in all three
0.3 s cases but not the three 0.1 s cases. Short-arc fit success therefore does
not establish model adequacy. See [model limits](../TRAJECTORY_PHYSICS.md).

The stereo process deadline is 15 seconds, including startup, after a cold
import-plus-fit measurement of about 14.3 seconds under development load.
Ray limits remain 10 seconds per fit. These are containment bounds, not latency
promises. Queue capacity/window defaults were preserved pending telemetry.

## Outstanding release gates

- Python 3.14 CI validation for this change set.
- Operator-led real-rig timing, lifecycle, recording, and USB qualification.
- Predeclared independent physical confirmation and reviewed signatures.
- Clean-machine GUI/install/update/uninstall/reinstall and signed artifact
  provenance. No accuracy or arbitrary-camera support claim is authorized.

Execute [the controlled pilot checklist](../CONTROLLED_PILOT_CHECKLIST.md).
