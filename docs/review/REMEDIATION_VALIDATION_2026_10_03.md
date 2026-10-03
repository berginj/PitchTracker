# October remediation implementation and validation

Baseline: `a55b898`. Initial findings are preserved in the
[pending-work review](PENDING_WORK_2026_10_03.md). The user authorized continued
implementation, cleanup, commits, and pushing validated `main` with parallel
agents. Existing untracked `docs/reviews/2026-09-09-assets/` is excluded from
local lint/type scans and remains untouched and unstaged.

## Implemented changes

- `fe0fb19`: shared compatible CSV exports preserve speed provenance, fit-quality
  basis, uncertainty availability, and strike eligibility. Boundary sensitivity
  uses available positional covariance and acquisition-time evidence. Missing
  physical uncertainty remains explicit; spin/RPM stays unavailable. The
  expanded 28-case synthetic ODE sweep includes plate bias, geometry, coverage,
  timing, noise seeds and model sensitivity; it does not establish physical
  accuracy (`physical_claim_eligible=false`).
- `301bc77`: capture/detection retain live workers through bounded stop failures,
  reconnect completion is fenced, and callback locks are released before joins.
  Recording fences inputs, ends the tracker before draining accepted analysis,
  retains terminal subscriptions, and preserves journal metadata and failed
  manifest results for retry. Coaching defers close until shutdown succeeds.
  Manual updater workers are cancelled and retained until native completion.
- `301bc77`: frozen applications initialize writable per-user state before
  logging imports. Bundled defaults are immutable and copied only when absent;
  migration copies known legacy files without overwrites or link traversal.
  Installer uninstall retains operator data and configuration bundling uses an
  explicit allowlist. Installer hashes bind to the exact fresh compiler output.
- `b310d3b`: the frozen GUI includes Matplotlib plus its required `unittest` and
  `difflib` dependencies. Source tests alone did not expose these missing imports;
  real frozen GUI smoke found them and the corrected artifact passes.
- Verified unused setup helper/write-only widget storage was removed. Public
  compatibility surfaces and runtime service ownership boundaries are retained.

## Committed CI evidence

[CI for `b310d3b`](https://github.com/berginj/PitchTracker/actions/runs/37143037101)
completed successfully on both supported runtimes.

| Gate | Result |
|---|---|
| Windows Python 3.13, two loadscope workers | 1,821 passed; 33 skipped; 213.14 s |
| Windows Python 3.14, serial | 1,821 passed; 33 skipped; 341.75 s |
| Repository mypy on Python 3.13 | Clean, 757 source files |
| Schema, public docs, file length, Flake8, typing policy | Passed |
| Native DirectShow provider import and fake UVC tests | Passed |

Earlier local sweeps encountered a worker idle timeout and an OpenCV fallback
timeout after a prolonged interrupted run. Each affected case passed separately;
the later clean CI matrix provides the complete committed-suite result.
The advisory dependency scan exited successfully but warned about ignored
Pillow matches from an unpinned requirement; it is not a security certification.

## Artifact evidence at `b310d3b`

Fresh isolated bundle: `dist/remediation-2026-10-03c/PitchTracker/`.
Source/frozen GUI and four worker smoke tests passed together: six tests,
21.28 seconds. GUI construction/render/close uses simulator and offscreen inputs.
Earlier packaging attempts and all consolidation artifacts remain preserved.

- GUI SHA-256: `4E3AB58123C5B6F23B8818875DEC2A096E435AD3D216A8FBBD33F55C76EB2C75`.
- Worker SHA-256: `D686B5DD31CA71FCEC9A3E189B5E035B018530196429756BEA5F2837A8DAC93D`.
- Fresh unsigned installer compilation completed in 185.907 seconds using an
  ignored copy of current `installer.iss` with explicit workspace SourceDir and
  isolated bundle/output paths. Output:
  `installer_output/remediation-2026-10-03/PitchTracker-Setup-v2.0.0-stereo.exe`.
  SHA-256: `8FDCC87D643293200302AC1AA0ECEB43B835894D97FE97D2315376B6FEF86B27`.

The initial tooling artifact smoke called normal environment validation, whose
camera check could probe index 0. Follow-up smoke uses explicit
`check_cameras=false` and isolated temporary state; it does not import legacy
operator state. Normal startup validation preserves camera checking by default.

## Follow-up and external gates

Follow-up review identified that terminal-analysis success could release a
recorder whose close/export failed, and repeated pause did not retry that close.
The follow-up separates close ownership from manifest ownership, serializes
artifact finalization, and makes frame submission atomic with the pause fence.
Focused disk-failure and concurrent-admission tests cover these orderings.
Partial detection resume/rollback also has explicit lifecycle regressions.
`b101740` implements independent close ownership, serialized artifact writes,
frame admission fencing, resume/rollback regressions, and camera-free tooling
smoke. `597c267` additionally retries exports after accepted post-roll frames
drain, before session state is cleared.

The complete local suites collected `b101740`: Python 3.13 with two loadscope
workers passed 1,833 tests, with 34 skips and 37 warnings, in 234.95 seconds.
Python 3.14 ran serially in an isolated clean worktree at that same commit:
1,833 passed, 34 skipped and 11 warnings in 439.20 seconds.
After the follow-up source and validation record were pushed as `6d2eacf`, the
repository CI matrix passed 1,835 tests with 33 skips on both Python 3.13 and
3.14. The CI run also passed mypy across 759 files, schema/docs/length/Flake8
gates, native UVC tests and the advisory security job.
The final `597c267` change passed 30 focused recording, manifest, terminal-flow,
orchestrator, environment-validation and tooling tests on both runtimes
(3.21 seconds on 3.13; 3.71 seconds on 3.14). Full-suite counts therefore do not
include the additional post-drain regression collected after `b101740`.
Final source static gates passed: mypy clean across 759 files; Flake8, file
length, schema mirror, typing policy and public docs passed. Local lint/type
checks explicitly excluded the unrelated untracked review assets.
Fresh bundle at application source `597c267`:
`dist/final-remediation-2026-10-03/PitchTracker/`. PyInstaller 6.18.0 completed
in 274.723 seconds. All six source/frozen GUI and worker smoke tests passed in
21.56 seconds using explicit camera-free environment validation and temporary
state. The build also includes the updated launcher guide documented here.

- GUI SHA-256: `B22C02351C0B0AACD65E3EBB4194AAC6FF88045784595823345F6AEC9C07C530`.
- Worker SHA-256: `3E5D70CCB8A4DE3D043EEF1067B4417EEDFA7D590A56AC6ED6F67209D9DF888F`.
- Included launcher guide SHA-256: `2FFD7A2988E77575638C18E22E4162BD7DAADA07D00815CF001865A18E4587F3`.

The current installer definition was copied into the isolated build directory
with explicit workspace SourceDir and the final bundle path. Inno Setup
completed in 176.656 seconds. The freshness helper verified the exact compiler
output against its start time:
`installer_output/final-remediation-2026-10-03/PitchTracker-Setup-v2.0.0-stereo.exe`.
SHA-256: `3DDC735BB6F804DECC727B7D415E481F50D54912D842BCC017E892A152CB2547`;
the adjacent `.sha256` file records this exact unsigned artifact.

No installer was installed, signed, published, or attached to a release. No
physical rig qualification or independent accuracy confirmation was performed.
Issues [#9](https://github.com/berginj/PitchTracker/issues/9),
[#10](https://github.com/berginj/PitchTracker/issues/10), and
[#11](https://github.com/berginj/PitchTracker/issues/11) remain operator gates:
camera/USB/exposure timing qualification, a disjoint independent confirmation
dataset, and signed standard-user clean-machine install/update/uninstall/
reinstall tests with sentinel data preservation and exact artifact provenance.
