# Remediation Plan

Priorities are dependency ordered. “Regardless” applies independent of platform choice.

## Work-item disposition

| Item | Classification | Priority / scope | Dependencies | Measurable closure |
|---|---|---|---|---|
| #9 qualify global-shutter hardware | Valid, Blocked by hardware | P1 / regardless | Procurement/test rig | Named models pass mode, exposure, sync, drop, and session-duration protocol |
| #10 physical speed/location validation | Valid, Blocked by #9 | P1 / regardless | #9, references, privacy plan | Versioned error distributions meet stated thresholds on representative sample |
| #11 clean installer smoke test | Valid, Blocked by clean machines | P1 / infrastructure | Release artifact, x64/ARM64 machines | Install/launch/update/uninstall and codec checklist recorded |
| #14 extract rig-profile responsibilities | Valid | P2 / architecture | Characterization tests | Narrow persistence/model/service modules; baseline entry removed |
| #15 split setup providers | Valid; worktree now 1,172 lines | P2 / architecture | Stable setup delta | Provider boundaries and tests; baseline entry removed |
| #16 replace best-effort UVC discovery | Valid | P1 / infrastructure | Vendor/OS capability evidence | Capability report is deterministic or explicitly unknown, never guessed |
| #12 restore CI gates | Already complete | Closed | PR #13 | Flake8/schema/file gate and matrix are green |
| Coach construction defect | Valid | P0 / regardless | Style API decision | UI-001 DoD |
| False pytest-qt skips | Valid | P0 / infrastructure | Qt lane | TEST-001 DoD |
| Offscreen/codec coupling | Valid | P0 / infrastructure | Codec policy, #11 | TEST-002 DoD |
| Event metadata gap | Valid | P1 / architecture | Schema migration | AGT-001 DoD |
| Benchmark semantics | Valid | P1 / regardless | Metadata/counters | PERF-001 DoD |
| Responsive setup/review/launcher | Valid | P1 / regardless | Minimum-resolution decision | UI-002/003 DoD |
| Accessible names/keyboard path | Valid | P1 / regardless | Manual AT test access | UI-004 DoD |
| 34 grandfathered files | Needs revision as one item | P2–P3 / architecture | Owners/issues | Every entry triaged; count falls without new debt |
| TAG cloud/Bluetooth | Blocked/staged | P3 / architecture | Product authorization, credentials, privacy | Disabled until dedicated integration/security acceptance passes |
| Full Rust/Go/.NET/C++ rewrite | Obsolete as current proposal | Not scheduled | PLAT-001 rewrite gate | Reconsider only if >50% non-isolatable Python-bound dominance is proven |

## P0 — Restore truthful core gates

1. Fix coaching construction and execute unguarded simulator smoke tests.
2. Correct the pytest-qt import guard.
3. Split offscreen UI and non-offscreen recording/codec test lanes; fail CI when either lane lacks evidence.

## P1 — Establish product evidence

4. Repair benchmarks with terminal conservation and representative host profiles.
5. Complete #9, then #10; do not publish accuracy before both close.
6. Complete #11 and #16 for deployment/camera truth.
7. Version required event metadata through capture → detection → pitch → analysis → recording/replay.
8. Make setup, review, and launcher responsive and complete accessible naming/manual AT checks.

## P2–P3 — Reduce structural and optional risk

9. Execute #14/#15, then triage remaining grandfathered modules by ownership/change rate.
10. Consolidate or retire legacy compatibility paths only after parity tests identify all consumers.
11. Keep cloud/Bluetooth/ray comparison features disabled or comparison-first until their explicit validation gates pass.

## Platform boundary

Must-fix regardless: all P0 items, physical accuracy, benchmark truth, layout/accessibility, event evidence. Python-specific: false module import, typing debt, possible profiled hot-path optimization. Architecture-specific: metadata, legacy paths, oversized ownership. Infrastructure-specific: CI lanes, codecs, installer, cameras. No remediation depends on a rewrite.
