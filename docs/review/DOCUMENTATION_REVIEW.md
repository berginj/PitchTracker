# Documentation Review

## Canonical hierarchy assessment

`README.md`, `REQ.md`, `docs/CURRENT_STATUS.md`, `docs/ROADMAP.md`, current architecture pages, and `docs/README.md` form a workable hierarchy. Historical/archive material is generally labelled. The main drift is not missing volume; it is evidence freshness and a tendency for software implementation breadth to become “complete” language.

Recent history explains the current shape: PR #8 aligned evidence boundaries and
tester recruitment; issue #12 and PR #13 restored Flake8/file-length gates while
grandfathering 34 oversized files; PR #20 migrated Actions to Node 24; PR #21
corrected camera/setup guidance and backend defaults; PR #22 aligned public
release, installer, security, and hardware claims. Those changes were valid, but
they do not supersede the newer worktree, UI, codec, or benchmark evidence.

## DOC-001 — Test evidence is historical, not current worktree truth

- **Finding:** Canonical pages present 1,267 passed / 32 skipped / 0 failed at commit `211d246` without consistently distinguishing that historical HEAD evidence from the current dirty worktree.
- **Evidence:** Current collection is 1,302; serial offscreen is 1,235 passed / 34 failed / 33 skipped. Latest Actions at current HEAD passed both supported Python versions.
- **Impact:** Readers may assume the in-progress worktree is fully green or treat a host-specific failure cluster as a released regression.
- **Confidence:** High.
- **Recommendation:** Preserve the exact historical CI statement and add the dated local audit result with environment/root-cause qualification.
- **Dependencies:** TEST-001/002.
- **Effort:** Small.
- **Definition of Done:** Every headline test count includes commit, date, environment, and whether it applies to HEAD or worktree.

## DOC-002 — Performance pages contradict their own evidence

- **Finding:** `docs/PERFORMANCE_BENCHMARKS.md` says baseline work is pending while marking targets passed; `docs/PERFORMANCE_OPTIMIZATIONS.md` states large I/O savings and zero quality loss without reproducible evidence.
- **Evidence:** Benchmark source counts submissions and fixed sleeps; corrected terminal-outcome measurements contradict a blanket 60 fps pass.
- **Impact:** Platform and field decisions can be based on invalid measurements.
- **Confidence:** High.
- **Recommendation:** Mark historical estimates clearly, remove pass marks, and make this audit baseline the current evidence boundary.
- **Dependencies:** PERF-001/002.
- **Effort:** Small documentation correction; medium benchmark repair.
- **Definition of Done:** No performance target is marked pass without raw samples, denominators, config, host, commit, and repeatable command.

## DOC-003 — Completion and step-count wording drifted

- **Finding:** Requirements/status language says automated implementation or hardening is complete, and one architecture page describes nine genuine setup widgets although ten are implemented.
- **Evidence:** Open issues, coach construction defect, metadata/test/performance gaps, and setup enum/window implementation.
- **Impact:** Release readiness and operator expectations are overstated.
- **Confidence:** High.
- **Recommendation:** Use “broadly implemented” and name remaining evidence gates; correct nine to ten.
- **Dependencies:** None.
- **Effort:** Small.
- **Definition of Done:** Canonical docs distinguish implementation, automated verification, physical validation, and release readiness, and all active setup descriptions say ten steps.

## Historical material

No archive was rewritten. Active performance optimization guidance receives a historical/unverified notice because it can be mistaken for current measured truth. Existing obsolete notices elsewhere remain intact.
