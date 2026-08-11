# Drift Matrix

## Released HEAD versus current worktree

| Area | HEAD `e8a1009…` | Current worktree | Audit interpretation |
|---|---|---|---|
| UVC identity | Earlier selector/discovery mapping | Stable PnP identities mapped through one discovery snapshot to DirectShow indexes | Worktree-only implementation; physical correctness cannot verify |
| Camera qualification | Production qualification behavior | Unrecognized/rolling-shutter devices may enter diagnostic setup, while production remains blocked | Useful diagnostic intent; requires clear operator state |
| Setup capture timeout | 20 seconds | 45 seconds | Worktree-only tolerance change |
| Setup layout | No new outer scroll wrapper | Scroll wrapper added | Does not fix measured 1,998-pixel minimum width |
| Shared ROIs | Committed values | Lane/plate reset to `null` | Worktree configuration state; do not treat as release default |
| Setup/camera tests | HEAD versions | Tests expanded/revised with delta | Focused non-recording setup tests passed |
| Camera/update configs | Absent | Two untracked files | Private device identities redacted; update settings are development state |
| Coaching crash | Present | Present/unaffected | Current defect, not caused by worktree delta |
| pytest-qt false skip | Present | Present/unaffected | Current test defect |
| Codec/offscreen coupling | Present in tested source/environment interaction | Present/unaffected | Not attributable to camera delta |

## Frozen pre-existing delta hashes

These SHA-256 values were recorded before audit documentation edits and
rechecked afterward. Hashes do not disclose the redacted catalog contents.

| Path | SHA-256 |
|---|---|
| `app/services/capture/setup_worker_main.py` | `71F541914BA23AB69AF94729194E97D6F397E541988CC096A905E82067C8AB24` |
| `capture/uvc_backend.py` | `01E8262787FABB12E454B6244C24E004235C89C09E8674560851E92231873ECC` |
| `rois/shared_rois.json` | `066A51F86112B22C1A618D7667709A9C846F2C7500938889E37C4EE9C582CE97` |
| `tests/test_camera_select_view.py` | `FB50F3AE9EF333F1A49D0579141D824FC54CD8C156822C6E3FA447924883048A` |
| `tests/test_camera_setup.py` | `38C45CCC50CBCCDB11D1B832F81FB94E49EBEF821E4E579765E8C444CA08F711` |
| `tests/test_setup_capture_process.py` | `EB236EB1CC1F84CFCB00911F88F6505AA0614EDCB23354BB9415B6B5336CC1EE` |
| `tests/test_setup_providers.py` | `59F1414F75B8CE981D75BE215E86B109B7E14AE7EBE61653629AD1B49A28D239` |
| `tests/test_stereo_setup_window.py` | `39CD1349A12FBEA9309483920A536A0AB6422559A03940DE0AA0CBE28ED9F418` |
| `ui/setup/README.md` | `C46DAFFC96EBAFD70E3EE695E40E454B28A8A2F2973AB54CE92DAC36CE96A163` |
| `ui/setup/camera_select_view.py` | `6B74BBD6E1CC90C3C8E98D342E90AC300D92E1777721877D14054A6631361C50` |
| `ui/setup/providers.py` | `03EE772B6FC8DEECF70C15C59757B66FDD9E463075A978FED5AF3BC132F23FB0` |
| `ui/setup/steps/camera_select_step.py` | `BF4A1D625B0F4076077A96DADA15443C22DD13E718E2005EED2F8464619CD16A` |
| `ui/setup/stereo_setup_window.py` | `E175E5AB3E3B55DAFEF1E07BA911F2FD3E6446C8E3FA5F2436D2061F55B6F6A3` |
| `configs/camera_catalog.json` | `0280C33584355FFF44FDEDAC19E425C7A09F25D4DF1C84153C1FD435C3A5E5AC` |
| `configs/update_settings.json` | `38D7BFD74B66D3F495ACD302CD23A2C4668E96B99F9233A4770EDD602C07CA2F` |

## DRIFT-001 — In-progress camera delta is not release evidence

- **Finding:** The worktree materially changes camera discovery and setup behavior but has no commit/CI identity.
- **Evidence:** Frozen 13-modified/2-untracked set and changed-file hashes; HEAD/main/origin remain identical.
- **Impact:** Combining results would misstate released behavior and could expose private hardware data.
- **Confidence:** High.
- **Recommendation:** Review and validate this delta independently, redact hardware identifiers, then land through normal CI if accepted.
- **Dependencies:** Physical UVC mapping tests and qualified cameras.
- **Effort:** Medium.
- **Definition of Done:** A dedicated commit/PR identifies the device mapping model, includes simulator/unit evidence and manual hardware results, contains no private identifiers, and passes required CI.
