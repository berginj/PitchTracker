# Assumption Register

Unknowns are not treated as facts. `Cannot verify` means the evidence needed was unavailable in this audit.

| ID | Assumption | Status | Evidence / test | Consequence |
|---|---|---|---|---|
| ASM-001 | HEAD is the released-source reference. | Verified | `main`, `origin/main`, and HEAD all resolved to `e8a1009…`. | Released/worktree conclusions can be separated. |
| ASM-002 | The dirty files are one in-progress camera/setup delta. | Verified | 13 modified and 2 untracked files share camera discovery/setup scope; hashes frozen. | Do not attribute the delta to released HEAD. |
| ASM-003 | The ten-step setup is implemented. | Verified | Step enum/window/providers/tests expose ten steps. | Documentation saying nine is incorrect. |
| ASM-004 | Global assignment is the default. | Rejected | Default config is `greedy_v1`; global/shadow modes are optional. | Performance/accuracy claims must name the algorithm. |
| ASM-005 | Ray fitting is the default primary trajectory. | Rejected | Default is `stereo_3d`; ray modes are comparison-first. | Ray results cannot define current field behavior. |
| ASM-006 | The installed pytest-qt plugin enables workflow tests. | Rejected | Plugin/fixture exists as `pytestqt`; test guard imports nonexistent `pytest_qt`. | Ten tests skip falsely. |
| ASM-007 | Local video codecs are unavailable. | Rejected in isolation; unresolved in suite | All five writer choices opened outside offscreen mode; all failed with Qt offscreen enabled. | Separate UI and codec lanes and test clean packaged systems. |
| ASM-008 | A green HEAD CI run exists for supported Python versions. | Verified | Actions run `29923290687`: Python 3.11, Python 3.12, and security jobs succeeded. | HEAD has cross-version automated evidence. |
| ASM-009 | Physical speed and location meet requirements. | Cannot verify | No selected physical rig/reference test; issues #9/#10 remain open. | No accuracy or production-readiness claim. |
| ASM-010 | Current camera hardware supports required exposure/synchronization. | Cannot verify | Private catalog inspected only for shape; no physical operation was authorized/available. | Hardware throughput and rolling-shutter behavior remain unknown. |
| ASM-011 | Installer/updater works on a clean Windows system. | Cannot verify | Issue #11 is open; no hands-on Windows runtime available. | Do not promise deployment reliability. |
| ASM-012 | Five-minute memory behavior is stable. | Inconclusive | RSS was non-monotonic, 126.6–191.3 MiB, ending 45.3 MiB above cold start. | Run longer after warm-up with allocation/native-memory attribution. |
| ASM-013 | Python is the dominant performance limiter. | Rejected by available evidence | OpenCV/NumPy/SciPy are native-heavy; no Python-exclusive profile share ≥30% was demonstrated. | No native-language POC yet. |
| ASM-014 | Offscreen screenshots represent installed typography and DPI. | Cannot verify | Qt reported missing font directory and rendered square glyphs in the audit environment. | Geometry/accessibility data are usable; visual typography and real DPI are not. |
| ASM-015 | Cloud/Bluetooth paths are production capabilities. | Rejected | Disabled defaults and opt-in skip guards. | Treat as staged integrations. |
