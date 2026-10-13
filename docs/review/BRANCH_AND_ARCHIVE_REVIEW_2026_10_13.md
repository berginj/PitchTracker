# Branch and archive review — 2026-10-13

The user requested a critical review of all pending branches, integration of
good improvements into main, and a discussion of archive candidates. Reviewed
all 17 local branch tips, the fetched origin refs, both open PRs, their checks
and comments, historical squash trees, and the current runtime entry points.
Initial main was `6b4bdd5`; the optional detector tip was `e843621`.
Pre-existing untracked `docs/reviews/` remains untouched and unpublished.

This is a targeted branch and ownership review, not physical qualification or
an exhaustive audit of every numerical algorithm. No code, branches, recordings,
calibrations, configurations or private assets are archived/deleted by this change.

## Branch decisions

| Local branch | Reviewed tip | Disposition |
|---|---|---|
| `main` | `6b4bdd5` | Integration baseline. |
| `agent/audit-camera-setup` | `2eeb443` | Ancestor of main; incorporated. |
| `codex/arm64-qualification-closeout` | `42be76e` | Reviewed PR #42; four CI jobs passed; merged with history preserved as `7b49313`. |
| `codex/baseballcv-comparison` | `e843621` | PR #43 contains meaningful optional research; correct the findings below, then merge its checked head after required CI. |
| `codex/audit-public-github-content` | `ccc4b95` | Patch-equivalent work already on main. |
| `codex/docs-testing-status` | `83f9ae6` | Tip tree equals main's historical squash `4040014`; incorporated. |
| `codex/fix-review-followups` | `40ea2eb` | Patch-equivalent work already on main. |
| `codex/link-roadmap-issues` | `9ce768b` | Patch-equivalent work already on main. |
| `codex/migrate-actions-node24` | `ac4218a` | Patch-equivalent work already on main. |
| `codex/pitchtracker-field-robustness` | `40158c1` | Ancestor of main; incorporated. |
| `codex/python313-mypy` | `7874642` | Tip tree equals main's historical squash `a8708ea`; incorporated. |
| `codex/restore-ci-gates` | `71a01cf` | Patch-equivalent work already on main. |
| `fix/finalization-ownership-followup` | `6d2eacf` | Ancestor of main; incorporated. |
| `fix/pending-work-remediation` | `b310d3b` | Ancestor of main; incorporated. |
| `fix/review-followups-and-installer-ci` | `e2f40e7` | Ancestor of main; incorporated. |
| `integration/valuable-branch-consolidation` | `a55b898` | Ancestor of main; incorporated. |
| `review/production-readiness` | `dbc6687` | Tip tree equals main's historical squash `09148ec`; incorporated. |

The only fetched work branches are #42 and #43. Previously retired remote tips
remain under `archive/2026-10-06/*`, with decisions in
[the October 6 review](BRANCH_CONSOLIDATION_2026_10_06.md). Their rejected
Python 3.9 patches and superseded worker implementations remain rejected.
Squash histories explain apparently unmerged commits; merging those branches
wholesale would restore obsolete code rather than recover missing improvements.

## Critical findings and fixes before PR #43 integration

1. **High — held-out leakage.** Different study IDs could reference the same
   captured session in development and evaluation. Reject repeated session
   roots and video hashes reused across those splits, including renamed/copied
   recordings. Input hashing stays inside the supervised worker; the parent
   can reject repeated roots without hashing multi-gigabyte videos.
2. **High — incorrect stereo truth.** Two correct 2D centers with absent pitch
   IDs, or different surveyed targets within one pitch window, could count as a
   correct match. Prefer explicit target identity; otherwise require a shared,
   nonempty pitch identity. Unassigned centers are unverified. Group the
   positive denominator by that identity, so separate pitches/targets in the
   two cameras do not create fictitious stereo opportunities.
3. **High — false-positive promotion.** Quality admission compared recall and
   false stereo matches but ignored increased false candidates and extra pitch
   attempts. Those increases now reject operational qualification even when a
   localization tail improves.
4. **High — duplicate-camera timing.** A two-entry timing summary could repeat
   one camera. Require stable distinct recorded camera identities, both summary
   entries, and journal coverage of exactly those cameras.
5. **Checked, already correct — trial tracking.** The committed shadow pipeline
   builds candidates from its selected stereo configuration. Add a regression
   proving a global_v3 trial uses predictive tracking while primary remains
   greedy. No production fix was needed for this concern.

PR #42's process-tree cleanup and lazy service imports remain narrowly owned.
The new adapter/research workers preserve CPU defaults, comparison isolation,
local model assets, explicit failure outcomes and recording ownership. Classical
MODE_A, greedy_v1 and stereo_3d defaults remain unchanged. Real models,
representative field data and independent physical confirmation remain gates.

## Validation

- Before review fixes: 127 focused tests passed on Python 3.13, covering both
  PRs' imports, geometry, provenance, adapter, comparison and admission.
- Review fixes: 37 focused tests passed on Python 3.13; the Python 3.14 domain
  subset passed 34 tests with one optional skip and two GUI tests deselected.
  The final unknown-identity correction passed all 12 review regressions on 3.13.
- Focused mypy and Flake8 passed; schema mirror, public-documentation,
  file-length and typing-policy gates passed.
- PR #43's original head had all four CI jobs green. Its revised head must pass
  the full Python 3.13/3.14 and other required CI checks before merge. Consult
  [PR #43](https://github.com/berginj/PitchTracker/pull/43) for that exact head.

The previously documented frozen binary predates these review fixes; its smoke
results are historical packaging evidence, not a new release qualification.
No hardware, private data upload, signed release or real-model trial was run.

## Main archive candidates for discussion

These are recommendations, not approved removal instructions. Counts indicate
maintenance scope, not a promised bundle-size or performance saving.

| Priority | Candidate | Evidence and prerequisite |
|---|---|---|
| 1 | Superseded ML integration notes and TAG partnership/specification documents | Root `ML_TRAINING_IMPLEMENTATION_GUIDE.md` and `PITCH_TRACKING_V2_INTEGRATION.md` describe older runtime wiring. TAG specifications describe conditional future work. Move historical proposals to one indexed archive and update all inbound links; preserve current training/operator guides. |
| 1 | Retired local branch labels | Fifteen local branch tips have no remaining independent work after #42/#43 integration, excluding main and the current feature branch. Preserve history/tags, then retire redundant branch labels in a separately agreed cleanup. |
| 2 | Dormant TAG integration | `app/services/tag_sports_integration.py`, `tag_sports_adapters.py`, and `tag_sports_flags.py` total about 600 lines. Consumers outside this island are tests and concept docs; there is no current coaching/orchestrator wiring. If partnership work is deferred, archive the implementation, mocks, tests and proposals together, retaining an activation note. |
| 2 | Superseded private candidate-enrichment implementation | `DetectionFrameHandler._enrich_detections` and its helper have no callers after CandidateProcessor became the shared live/replay owner. Remove this duplicate in a focused cleanup; archival Git history is sufficient. |
| 3 | Seven-stage SetupWindow and ten-stage stereo registry | Launcher now injects the five-stage guided factory. Older defaults, scripts and compatibility tests still exercise the other flows. Retire the old entry points after deciding the compatibility policy; keep shared BaseStep, discovery, capture, calibration and field helpers. Do not move the entire setup/steps or providers directories. |
| 3 | InProcessPipelineService and its implementation-only mixins | Canonical QtPipelineService uses PipelineOrchestrator. About 1,000 lines span the older implementation and neighboring service modules, but shared service contracts remain active. Two analysis modules still import PitchSummary through this older module for typing. Move those imports to app.contracts and agree API retirement before archiving implementation-only files. |
| 3 | Old direct pipeline CLI and prototype launch scripts | `app/pipeline.py` collides with the app.pipeline package; CLI tests deliberately load it by filename. `scripts/test_setup_wizard.py` opens the older setup. Confirm external usage and replace supported commands with canonical service/launcher routes before retiring them. |

Recommended sequence: historical document/index cleanup, then dormant TAG and
verified private duplicates, then an explicit compatibility retirement for the
old setup/pipeline paths. The last group offers the most architectural
simplification and requires the most care.

Keep numerical/trajectory alternatives, independent physical-validation tools,
decision journals, replay mappings, model qualification checks and schema
mirrors. Visualization still serves Review; benchmarks support platform and
measurement qualification. Hardware design files support rig work. These are
not dead merely because no default UI imports every entry point.

Keep dated `docs/review/` records as evidence, with current truth in
CURRENT_STATUS/ROADMAP. Consolidating the two existing archive roots may improve
navigation, but should be an indexed move with link checks, not deletion.
Private recordings, calibration, ROI/config state, logs and generated local
builds require a separate retention decision and are outside this review.
