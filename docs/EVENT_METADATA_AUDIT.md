# Event Metadata Audit

**Last Updated:** 2026-06-23
**Scope:** Runtime events in `app/events/event_types.py`
**Reference:** `agents.md` Interaction Protocols

---

## Summary

Runtime service events are typed dataclasses and carry the core domain payloads
needed by the current in-process event bus. They are not yet a complete
implementation of the durable/enveloped message schema in `agents.md`.

This is acceptable for the current local runtime because the event bus does not
persist these events directly. Durable artifacts already carry schema and app
metadata through manifests and summaries. If these events are persisted,
exported, queued, or consumed cross-process, add an envelope before that change.

---

## Current Event Coverage

| Event | Current Required Metadata | Gap Against `agents.md` | Pilot Impact |
| --- | --- | --- | --- |
| `FrameCapturedEvent` | `camera_id`, `timestamp_ns`, `frame` with frame metadata | No explicit `message_type`, `correlation_id`, `session_id`, or diagnostics field | Low for in-process runtime; required before persisted frame-event replay |
| `ObservationDetectedEvent` | `timestamp_ns`, `confidence`, typed stereo observation | No explicit `message_type`, `correlation_id`, `session_id`, `pitch_id`, or diagnostics field | Medium; pitch/session linkage is inferred by orchestrator state |
| `RayObservationDetectedEvent` | `timestamp_ns`, `confidence`, typed ray observation | Same as stereo observation event | Medium; ray diagnostics should become structured before field validation claims |
| `PitchStartEvent` | `pitch_id`, `pitch_index`, `timestamp_ns` | No explicit `message_type`, `correlation_id`, `session_id`, or diagnostics field | Low; already pitch-scoped |
| `PitchEndEvent` | `pitch_id`, observations, `timestamp_ns`, `duration_ns`, ray observations | No explicit `message_type`, `correlation_id`, `session_id`, or diagnostics field | Medium; session linkage should be explicit if replay or async analysis is added |
| `PitchAnalyzedEvent` | `pitch_id`, pitch summary, session summary | No event timestamp, `message_type`, `correlation_id`, `session_id`, or diagnostics field | Medium; summary payload includes durable fields, but event envelope is thin |
| `ConfigUpdateEvent` | config key/value and `timestamp_ns` | No `message_type`, `correlation_id`, session scope, actor, or validation diagnostics | Low; currently reserved/unused |
| `ErrorEvent` | service name, error type, message, details, `timestamp_ns` | No explicit `correlation_id`, `session_id`, `pitch_id`, `camera_id`, or structured diagnostics map | Medium; current details string is less consumable than structured diagnostics |

---

## Required Follow-Up Before Async Or Durable Events

1. Add a backward-compatible event envelope or metadata mixin with
   `message_type`, `correlation_id`, optional `session_id`, optional `pitch_id`,
   optional `camera_id`, and `diagnostics`.
2. Keep dataclass constructor compatibility by adding optional metadata at the
   end of event definitions or by wrapping events at bus/persistence boundaries.
3. Add event-bus tests that prove metadata survives publish/subscribe paths.
4. Add manifest/replay tests before using runtime events as durable replay
   records.

---

## Recommendation

Do not add mandatory metadata fields directly to every event before the pilot.
That would touch many call sites without changing current runtime behavior.
For the current runtime, keep typed in-process events as-is and treat this audit as
the acceptance record. Make the next change additive through an envelope when
events become durable or cross-process.
