# Final branch consolidation review — 2026-10-06

Reviewed after fetching origin and checking a clean worktree. Integration base:
`e1df60d`. The user requested completion of branch reviews, consolidation of
meaningful work into main, and retirement of redundant branches. This record
preserves each reviewed tip and the reason for its disposition.

## Branch decisions

| Branch | Reviewed tip | Decision | Preserved reference |
|---|---|---|---|
| `feature/development-plan` | `1f83691f87900c73c94fcf3299bd8a0e9b783b3d` | Already an ancestor of main (zero branch-only commits). Its proposals are superseded by the controlled-pilot plan. Retire the branch. | `archive/2026-10-06/development-plan` |
| `review/production-readiness` | `803e43e6a5bf47c6f1079bdbd8f4ae7b5ec4658c` | PR #23's squash contains the core work. Later valuable discovery/launcher changes were adapted in October. Remaining older patches would regress modern contracts and worker dispatch. Retire the branch. | `archive/2026-10-06/production-readiness` |
| `feature/controlled-pilot-items-1-5` | `f1ac3e4c10bc6e27e542c8fc16638392f1ee0265` | The pilot implementation is already on main. Four unique commits are unsupported Python 3.9 compatibility churn with defects; reject those patches and retire the branch. | `archive/2026-10-06/controlled-pilot-items-1-5` |
| `docs/reality-alignment-2026-10-06` | `c6166e1` plus this decision record | Meaningful remaining work: current documentation, simulator startup without camera validation, backend regressions, and expanded documentation checks. Merge through PR #41 after final CI, then retire the source branch. | Main merge history and PR #41 |

Archive tags preserve the exact old tips before remote branches are removed.
They are recovery/history references, not software releases or accuracy approvals.
Do not merge the archived branches wholesale merely to make their commits
ancestors of main.

## Production-readiness reconciliation

The original squash is main commit `09148ec` (PR #23). The old remote adds
`9d39d83`, `ab9bc82`, and `803e43e` after the incorporated review work. The
[October 2 review](BRANCH_CONSOLIDATION_2026_10_02.md) and
[implementation record](CONSOLIDATION_VALIDATION_2026_10_02.md) explain the
adaptation/rejection decisions; current source was rechecked for this review.

- CR-001: recording lifecycle controls bypass bounded frame capacity while
  preserving FIFO order in `app/services/recording/worker.py`.
- CR-002: launcher validation uses cancellable tooling and retains workers until
  terminal signals. October follow-ups also retain recording/capture ownership
  after failed shutdown.
- CR-003: discovery cancellation reaches PnP/OpenCV child processes, avoids
  cancelled cache writes, suppresses stale results, and retains setup-owned work.
- CR-004: review configuration authorization uses resolved-path containment.
- Source launcher preparation is inside `main()`, not import-time execution.
  Current packaged work uses dedicated worker entry points, with explicit GUI
  dependency inclusion and `strip=False`.

The old standalone OpenCV probe helper and unconditional multiprocessing hooks
are not replacements for current source/frozen worker dispatch. Older removed
metadata/terminal-flow assertions and stale roadmap content are not imported.

## Pilot compatibility rejection

Reviewing the unique diff while ignoring line endings shows annotation changes,
UTC fallbacks, imports, and whitespace rather than new pilot algorithms.
Fallbacks such as `from datetime import timezone as UTC` provide a class where
`datetime.now()` requires a timezone instance. `Optional` and `Union` annotations
also appear without required imports (for example setup contracts and cleanup
management). These changes neither establish Python 3.9 compatibility nor improve
the supported Python 3.13/3.14 behavior. The archive retains them for inspection.

## PR #41 review and validation

The source change routes simulator startup to the existing tooling worker with
`check_cameras=false`. UVC/OpenCV retain default camera validation and cancellation
behavior. No camera/detection/trajectory logic moves into the UI. Regression
coverage checks all three backend choices. The documentation separates historical
tag/test evidence from current status and records the eight outstanding software
review findings and operator gates.

At reviewed source `c6166e1`, [CI run 37427133281](https://github.com/berginj/PitchTracker/actions/runs/37427133281)
passed all four jobs: Python 3.13 and 3.14 each passed 1,838 tests with 33 skips;
mypy checked 759 source files cleanly; native UVC ran 10 passing tests. Required
static gates and the advisory security job passed. PR #41 had no inline review
requests or submitted reviews at this audit. Final merge must use the checked
head and passing required checks after adding this documentation record.

## Work remaining after consolidation

Branch consolidation does not close the eight software review findings in
[the request/work audit](REQUEST_AND_WORK_AUDIT_2026_10_05.md), issue acceptance
reconciliation for #34–#40, physical camera/accuracy qualification, signing, or
clean-machine installer testing. Those remain in [the roadmap](../ROADMAP.md).
No recordings, calibration files, configs, private assets, or external worktrees
are removed by retiring the reviewed Git branches.
