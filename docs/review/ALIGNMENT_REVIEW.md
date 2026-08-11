# Alignment Review

## North star

The system currently appears to exist to **help baseball and softball coaches capture, reconstruct, review, and export pitch evidence on a local Windows laptop by combining synchronized stereo video, configurable detection, a pitch lifecycle, trajectory fitting, and durable session artifacts**.

This is independently supported by the README and requirements, ADR-0001, the service/event architecture, durable contracts, UI applications, synthetic tests, open validation issues, and recent documentation-alignment history.

| Dimension | Rating | Evidence-led assessment |
|---|---:|---|
| Product | 3/5 | Intended coach workflow is clear; physical usefulness is unproven. |
| Architecture | 4/5 | Service/event ownership matches the product; legacy and metadata gaps remain. |
| Domain model | 4/5 | Units, observations, pitch lifecycle, summaries, and evidence contracts are explicit. |
| APIs/contracts | 3/5 | Broad typed contracts; required correlation and durable metadata are incomplete. |
| UI | 2/5 | Setup/review exist, but layouts exceed common screens and coaching construction fails. |
| Tests | 3/5 | Broad and green in HEAD CI; false skips and environment-coupled recording failures hide important paths. |
| Backlog | 4/5 | Hardware/installer/module issues are valid; UI/test/performance findings need addition. |
| Documentation | 3/5 | Strong evidence language, with stale counts and contradictory performance/completion claims. |
| Agent guidance | 3/5 | Strong ownership model; some requirements are aspirational or conflict with the codebase. |

## ALN-001 — Evidence is behind implementation breadth

- **Finding:** Most planned software capabilities exist, but the product's defining physical-output evidence does not.
- **Evidence:** Stereo/ray fitters, recording, setup, review, export, and 1,302 collected tests exist; issues #9 and #10 remain open for a qualified rig and physical speed/location validation.
- **Impact:** Feature completeness cannot be translated into coach-facing accuracy or field readiness.
- **Confidence:** High.
- **Recommendation:** Make physical validation the release gate and label all synthetic results accordingly.
- **Dependencies:** #9 qualified hardware, repeatable fixtures, reference radar/location system, privacy-safe data handling.
- **Effort:** Large; hardware-dependent.
- **Definition of Done:** A versioned validation report publishes representative denominators, error distributions, failure cases, rig/config identity, and pass thresholds for speed and plate location.

## ALN-002 — Optional capability is described too much like default behavior

- **Finding:** Global association and ray trajectory modes are implemented but are not the default production path.
- **Evidence:** `configs/default.yaml` selects `greedy_v1` and `stereo_3d`; `global_v2`, shadow comparison, `ray_reprojection`, and `ray_graph` are opt-in.
- **Impact:** Readers can overestimate the runtime path or assume comparison modes are field-approved.
- **Confidence:** High.
- **Recommendation:** State defaults wherever optional algorithms are introduced and preserve comparison-first language.
- **Dependencies:** None.
- **Effort:** Small.
- **Definition of Done:** README, architecture, config, and generated operator guidance name both the implemented options and actual defaults without implying field validation.

## Scope applicability

Authentication/authorization, a server database, mobile clients, and deep links are **not applicable to the proven default local desktop workflow**. Cloud upload and Bluetooth are **staged**, not N/A, because code/contracts and guarded tests exist. Updater behavior is applicable but clean-machine verification is outstanding.
