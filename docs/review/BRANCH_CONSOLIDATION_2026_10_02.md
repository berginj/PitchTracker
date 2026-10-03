# Branch consolidation review and commit plan

Reviewed 2026-10-02 after `git fetch origin --prune`.
Baseline: `main`, `origin/main`, and the checked-out
`fix/review-followups-and-installer-ci` all point to `e2f40e7`.
No source changes, merges, commits, or pushes were performed for this review.
The pre-existing untracked `docs/reviews/2026-09-09-assets/` is user work;
leave it untouched and do not include it through blanket staging.

This records the initial review. Subsequent user-authorized implementation,
cleanup, commits, and validation are tracked in
[the consolidation execution record](CONSOLIDATION_VALIDATION_2026_10_02.md).

## Scope and conclusion

Reviewed every local branch and fetched origin branch, ancestry, patch
equivalence, historical squash trees, remaining unique changes, current
camera/launcher lifecycle code, runtime policy, and CI gates. This is a
branch-consolidation review with targeted code inspection, not an exhaustive
line-by-line audit or physical hardware qualification.

Use current main as the integration base. Preserve the valuable remaining
camera lifecycle work through focused adaptations. Do not merge every stale
branch merely to make its commits reachable: most work is already present,
and the Python 3.9 compatibility branch introduces defects outside the
supported Python 3.13/3.14 runtime policy.

## Every branch and disposition

| Branch | Tip | Decision and evidence |
|---|---|---|
| `main`, `origin/main` | `e2f40e7` | Integration baseline. |
| `fix/review-followups-and-installer-ci` | `e2f40e7` | Identical to main; no pending branch changes. |
| `agent/audit-camera-setup` | `2eeb443` | Ancestor of main; incorporated. |
| `codex/pitchtracker-field-robustness` | `40158c1` | Ancestor of main; incorporated. |
| `codex/restore-ci-gates` | `71a01cf` | Patch-equivalent commit already on main (`4bf8dfc`). |
| `codex/docs-testing-status` | `83f9ae6` | Entire tip tree identical to main commit `4040014`; incorporated by squash. |
| `codex/link-roadmap-issues` | `9ce768b` | Patch-equivalent commit already on main (`50335be`). |
| `codex/migrate-actions-node24` | `ac4218a` | Patch-equivalent commit already on main (`a2f85aa`). |
| `codex/fix-review-followups` | `40ea2eb` | Patch-equivalent commit already on main (`211d246`). |
| `codex/audit-public-github-content` | `ccc4b95` | Patch-equivalent commit already on main (`e8a1009`). |
| `review/production-readiness` | `dbc6687` | Entire tip tree identical to main commit `09148ec`; all local review fixes incorporated. |
| `codex/python313-mypy` | `7874642` | Entire tip tree identical to main commit `a8708ea`; later main commits further improve typing and camera probes. |
| `origin/feature/development-plan` | `1f83691` | Ancestor of main; main subsequently replaces speculative proposals with the controlled-pilot plan. |
| `origin/review/production-readiness` | `803e43e` | Shares old review history; inspect/adapt `ab9bc82` camera lifecycle changes and reconcile `803e43e` follow-up documentation. Do not merge wholesale. |
| `origin/feature/controlled-pilot-items-1-5` | `f1ac3e4` | Four commits ahead of main (`30335c7`, `f67051f`, `9a1b6b4`, `f1ac3e4`), all Python 3.9 compatibility changes. Reject current patches; pilot implementation itself is already on main. |

Origin HEAD points to main; it is an alias rather than another work branch.
Several local codex branches track deleted remote branches. Their work remains
locally inspectable; missing upstream branches do not imply missing changes.
`git cherry` alone overstates unmerged work for the squash histories above;
the whole-tree equality checks establish incorporation.

## Findings affecting consolidation

1. **High: launcher shutdown can accept close while validation is running.**
   `launcher.py:378` waits only 3000 ms, ignores the wait result, and then
   accepts close. `StartupValidationThread` has no cancellation mechanism.
   This permits unsafe QThread teardown. Remote review item CR-002 is still
   relevant; that remote branch documents it but does not implement the fix.

2. **Medium: useful discovery cancellation was left out of main.**
   `ab9bc82` adds cancellation through PnP discovery, UI discovery, and camera
   step ownership. Current `ui/setup/steps/camera_discovery_worker.py` has no
   cancel/wait API; `CameraStep.on_exit()` only closes previews/cameras.
   The current isolated OpenCV probe is better than the old multiprocessing
   implementation and must be retained. Adapt cancellation around the current
   dedicated worker process instead of replacing it with the old probe.

3. **Medium: setup close cleanup is valuable remaining remote work.**
   `ab9bc82` invokes step cleanup when setup windows close. Current legacy
   `SetupWindow.closeEvent()` only resets styling. Port cleanup through current
   ownership boundaries; preserve the stereo window's busy/capture cancellation
   flow and ensure cleanup runs once terminal state is reached.

4. **Medium: pilot branch's UTC fallback is invalid.**
   In `analysis/pattern_detection/detector.py` and `pitcher_profile.py`,
   `from datetime import timezone as UTC` binds a class, not a timezone
   instance. `datetime.now(UTC)` fails when this fallback executes. The correct
   older-runtime value would be `timezone.utc`; the supported runtime already
   has `datetime.UTC`, so no fallback is needed here.

5. **Medium: pilot branch replaces annotations with missing imports.**
   Examples include `Optional` in `contracts/setup.py`,
   `contracts/durable_registry.py`, `contracts/setup_capture.py`,
   `app/services/setup_snapshot.py`, and `app/services/rig_profile_approval.py`;
   `Union` is also missing in `app/lifecycle/cleanup_manager.py`. Postponed
   annotation evaluation masks some runtime failures but static checks and
   evaluated type hints will fail. Compatibility scope also remains incomplete
   (for example evaluated union casts in setup contracts). Avoid importing this
   branch's annotation churn and line-ending changes.

6. **Remote review documentation requires reconciliation.**
   `803e43e` documents CR-001 recording command admission and CR-004 config
   containment, already addressed on main, alongside outstanding CR-002.
   CR-003 cancellation/cache poisoning must be tested when cancellation is
   reintroduced. Do not overwrite current roadmap/status with the old file.

## Ordered merge and commit plan

Create a separate integration worktree from `origin/main` so existing untracked
assets and the user's checkout remain undisturbed. Suggested branch:
`integration/valuable-branch-consolidation`.

1. **`fix: cancel camera discovery and clean up setup ownership`**
   Adapt selected changes from `ab9bc82`, recording that source hash in the
   commit body. Wire cancellation/completion through current discovery modules,
   prevent stale results after backend switches/window close, cancel/reap child
   probes, and run setup step cleanup. Preserve modern worker entry points,
   camera metadata, native capability discovery, and typed contracts. Add tests
   for blocked PnP/probe cancellation, backend switches, setup close, and no
   cache writes on cancelled results. Use current module paths in old tests.

2. **`fix: wait for terminal launcher validation before close`**
   Implement CR-002 through the tooling service and startup worker's supported
   cancellation/timeout path. Request cancellation on close; defer acceptance
   until completion and reap the subprocess. Do not forcibly terminate Qt
   threads. Test blocked validation, repeated close, and successful completion.

3. **Conditional: `fix: make source launcher imports side-effect free`**
   Adapt `ab9bc82`'s `launch_app.py` main guard if current launcher import tests
   demonstrate the need. Current import changes cwd and clears caches at module
   scope. Keep preparation inside `main()` and test import does not change cwd
   or remove caches. Retain current source/frozen worker dispatch; avoid blindly
   adding redundant multiprocessing hooks. `inspect` exclusion removal and
   `strip=False` are already present and need no extra packaging commit.

4. **`docs: reconcile branch review and current validation status`**
   Incorporate this decision record; update roadmap follow-ups to distinguish
   fixed admission/containment from remaining lifecycle work. Replace validation
   claims only with actual results for the final integration commit. Leave
   physical accuracy approval and clean-machine qualification explicitly pending.

Each implementation commit should include its boundary tests, pass focused
checks, and explain source/adaptation decisions. Review the final diff against
main, then merge the integration branch through the required CI gates. Do not
merge the stale source branches into it. Commit only explicit selected paths.
Archive/delete redundant branches only as a separately requested cleanup after
the integration is accepted; do not delete recordings, configs, or assets.

## Validation and exit criteria

Baseline checks executed on Python 3.13.14:

- 88 tests passed across event metadata, recording worker, orchestrator
  lifecycle, discovery, camera step teardown, worker execution, runtime
  requirements, and review session loading. Fourteen third-party Matplotlib /
  pyparsing deprecation warnings; no failures.
- Schema mirror, public documentation, file-length, and typing-policy checks
  passed.

The baseline checks do not prove absent cancellation features or validate the
unmerged branch; new failure-path tests are necessary. Full suites, Flake8,
mypy, Python 3.14, installer build, and hardware qualification were not run in
this review.

Before merge, run the focused new tests, then repository-wide `python -m
pytest` on Windows Python 3.13 and 3.14 using CI's supported execution strategy;
run schema/docs/length/Flake8/typing-policy/direct-mypy gates. Build and smoke
test frozen workers and the installer because lifecycle/entrypoint changes
cross the packaging boundary. Document an operator-run camera disconnect,
backend-switch, and setup/launcher-close check on the real rig. Software merge
does not establish physical measurement accuracy or authorize a release.
