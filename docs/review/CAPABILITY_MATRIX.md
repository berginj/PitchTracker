# Capability Matrix

| Capability | HEAD implementation | Worktree delta | Automated evidence | Physical/manual evidence | Confidence |
|---|---|---|---|---|---:|
| Ten-step stereo setup | Present | Camera mapping, diagnostic fallback, deadline, scrolling changes | Focused setup tests passed | Cannot verify cameras/usability | Medium |
| Rig-profile persistence | Present | Related catalog/settings files added | Unit/service coverage | Cannot verify field reuse | Medium-high |
| Sim/OpenCV/UVC capture | Present | UVC mapping revised | Simulator/backend tests | UVC hardware cannot verify | Medium |
| Classical detection | Default | None | Unit tests and synthetic timings | Real ball/lighting cannot verify | Medium |
| ML detection/export | Optional/local | None | Contract/export tests | Model quality cannot verify | Low-medium |
| Stereo pairing/triangulation | Present | None | Synthetic geometry/evidence tests | Accuracy cannot verify | Medium |
| Global association | Optional (`global_v2`) | None | Tests present | Field benefit cannot verify | Medium |
| Pitch lifecycle | Present | None | State/concurrency tests | Real sequence cannot verify | Medium-high |
| Stereo trajectory | Default | None | Synthetic fits pass | Physical accuracy cannot verify | Medium |
| Ray trajectory modes | Comparison-first | None | Synthetic fits pass | Field calibration cannot verify | Medium-low |
| Session/pitch recording | Present | None | HEAD CI green; local offscreen failures | Packaged codec cannot verify | Medium-low |
| Analysis/summaries | Present | None | Unit/integration coverage | Coach usefulness cannot verify | Medium |
| Coaching UI | Present but construction defect | None | Guarded tests miss defect | Cannot verify manually | Low |
| Review/replay/annotation | Present | None | Import/controller tests | Layout exceeds common screens | Medium-low |
| Selected export | Present/local | None | Export tests | Privacy workflow cannot verify manually | Medium |
| Calibration subprocess tooling | Present | Setup worker changed | Tooling tests | Physical calibration cannot verify | Medium |
| Installer/updater | Scripts/contracts present | Update settings untracked | Build/unit evidence | Clean install cannot verify | Low |
| TAG cloud | Staged/disabled | None | Four opt-in skips | Cannot verify | Low |
| Bluetooth | Staged/disabled | None | Four opt-in skips | Cannot verify | Low |
| Radar | Stub/manual boundary | None | Limited tests | Physical device cannot verify | Low |

## CAP-001 — Capability truth must include evidence level

- **Finding:** Source presence is often stronger than operational or physical evidence.
- **Evidence:** Core flows and contracts are present, while #9–#11, guarded integrations, offscreen UI defects, and codec behavior remain unresolved.
- **Impact:** A binary complete/incomplete label exaggerates readiness.
- **Confidence:** High.
- **Recommendation:** Maintain this five-column distinction in release decisions.
- **Dependencies:** Versioned CI, physical validation reports, clean-machine smoke records.
- **Effort:** Medium and ongoing.
- **Definition of Done:** Every release capability has an implementation state, default/optional state, automated evidence link, manual/physical evidence link, and named owner.
