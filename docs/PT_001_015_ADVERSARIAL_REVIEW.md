# PT-001–PT-015 adversarial review

Date: 2026-07-21

Three independent review lanes challenged the completed field-robustness work:

1. Physical camera, setup, calibration, field alignment, and rig persistence.
2. Pairing, tracking, coordinate frames, evidence, validation, and trajectory claims.
3. Coaching UI, worker generations, recording lifecycle, shutdown, and downstream claims.

The reviews were read-only first. Findings were then assigned as non-overlapping
fix slices and verified with focused regression suites before repository-wide
validation.

## Repaired findings

| Area | Adversarial failure | Enforced result |
|---|---|---|
| Live setup | Successful profile persistence referenced an undefined selection | Live fake-hardware persistence now completes and activates a profile |
| Physical cameras | Startup/reconnect trusted requested settings | UVC mode and control readback are verified before threads start and after reconnect; mismatch closes the device and blocks measurement |
| Global shutter | Unknown/rolling-shutter pairs could pass production selection | Physical selection requires catalog-recognized global-shutter capability |
| White balance | `wb=null` could be called verified or make setup unusable | Setup samples the physical auto-WB value, locks it, verifies it, records provenance, and persists the resolved value; unsupported sampling fails closed |
| Calibration | Matrix-only legacy artifacts could inherit FULL/production-ready status | Physical profiles require explicit FULL/readiness, finite RMS, dimensions, and positive sample evidence |
| Field alignment | “Recalculate” could silently reuse a stale transform | Fixture SHA-256 and point count are persisted; changes or explicit force trigger recomputation |
| Rig durability | IDs could collide and activation writes were non-atomic | IDs include microsecond time and UUID entropy; profile and active marker use atomic replacement |
| Pitch recording | `PitchEndEvent` never armed post-roll, blocking the next pitch | End events arm post-roll; both-camera completion auto-closes and consecutive pitches are tested |
| Evidence writes | Concurrent rewrites could expose partial/inconsistent files | Evidence v2 serializes writers and atomically publishes content-addressed generations with the manifest last |
| Pair timing | Configured camera offset was applied after pairing decisions | Adjusted timing now drives pairing, skew gates, drift, and lifecycle while raw and adjusted timestamps remain distinct |
| Coordinates | Field XYZ retained camera covariance; ray models used camera world axes | Covariance rotates as `RΣRᵀ`; ray extrinsics are re-expressed in a residual-gated field frame or fail closed |
| Validation | Blank/duplicated cases could satisfy sample thresholds | Dataset/case IDs must be nonblank and case IDs unique |
| Trajectory promotion | Ray primary was not connected to ground-truth approval | Physical ray primary requires an exact mode/rig/revision/software/dataset/report approval; comparison-only use remains allowed |
| Runtime metrics | Missing/NaN metrics and lower-severity sync warnings could look healthy | Missing opportunity is unavailable, invalid values reject, and severity cannot downgrade an existing rejection |
| Detector health | Detector exceptions became ordinary “no candidates” | Exceptions reach cumulative failure accounting; attempts, failures, and queue drops expose explicit denominators |
| Analysis failures | Empty, dropped, or failed analysis could leave no verdict while failure rate stayed zero | Exactly one `UNAVAILABLE` terminal summary is published with reason codes; exceptions also increment worker failures and recording writes the verdict |
| Worker restart | A timed-out generation could accept work for a dead/stopping thread | Workers gate acceptance by live generation, reject stale submissions, use one stop deadline, and block unsafe restart |
| Shutdown | Recording resources closed even when a writer could still be active | Drain timeout keeps resources open/faulted for explicit retry |
| Coaching polling | Bursts were dropped, updates stalled after ten, and games replayed the same pitch | Full session history plus unseen pitch IDs drives exact-once UI updates and mode scoring |
| Measurement claims | Rejected pitches became balls/zero-speed trends; raw movement and fit confidence could drive athlete claims | Central usability gating suppresses rejected results; missing speed remains absent; fatigue requires consistent usable speed provenance and excludes fit-confidence decay |
| Startup rollback | Recording initialization failure left analysis/detection subscribed | Startup rolls back newly started services in reverse order |

## Follow-up adversarial review status

The AR-001 through AR-015 follow-up closed the software architecture gaps while
preserving the hardware and validation boundaries:

1. Setup burst capture now runs in a supervised, disposable camera-owner process.
   Qt remains responsive, operator cancellation terminates the child, a parent
   deadline force-kills a stalled native read, and stale assignment/config results
   are rejected before setup evidence changes. Process termination still cannot
   prove that a defective kernel driver releases the physical device; cancel/reopen,
   unplug/reconnect, and repeated-cycle recovery remain mandatory hardware tests.
2. Every pairing-admitted frame now terminates as paired or unmatched, including
   timestamp/index rejection, buffer eviction, queue loss, failure, and stop flush.
   The session decision journal preserves the per-frame denominator.
3. Candidate-level decision replay now preserves detector-returned candidates,
   tracklet decisions, association edges/costs/gates, triangulation outcomes, and
   ramp-up history. This is not pixel-to-detector bitwise replay; that additionally
   requires source pixels and a reproducible detector runtime.
4. Deterministic global maximum-cardinality/minimum-cost association is available
   as `global_v2`, with `shadow_v2` comparison. `greedy_v1` remains the default
   until a physical confirmation dataset approves promotion.
5. Offline legacy pattern/trend tools still need a complete audit before raw
   `run_in`/`rise_in` can be guaranteed absent from every non-coaching classifier.
6. Physical-validation v2 now requires independent reference uncertainty,
   protocol/dataset/report hashes, predeclared tail policy, artifact fingerprints,
   lifecycle state, and distinct trusted attestations. V1 remains diagnostic-only.
7. No synthetic or automated test validates the physical global-shutter rig's
   accuracy. Hardware mode/control readback, timing tails, calibration, field
   alignment, and a named ground-truth dataset remain mandatory onsite acceptance.

## Verification boundary

Automated tests establish software behavior and failure handling only. They do
not justify a `VALIDATED` physical measurement. The active rig must still pass
the operational acceptance checklist in `PT_001_015_TRACEABILITY.md`.

Final integrated verification on 2026-07-21 after AR-001 through AR-015:

- Cross-workstream integration suite: 167 passed.
- Full repository suite: 1,257 passed, 32 skipped, 23 warnings.
- `compileall`: passed.
- `git diff --check`: passed.
