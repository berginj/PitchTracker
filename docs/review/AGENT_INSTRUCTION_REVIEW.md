# Agent Instruction Review

Reviewed active guidance: `agents.md`, `.github/copilot-instructions.md`, README contribution/build links, release automation guidance, and nested setup documentation. No agent-instruction file was changed.

## AGT-001 — Ownership guidance is useful but partly aspirational

- **Finding:** `agents.md` accurately describes desired service ownership, but its required message metadata is not consistently present in runtime event dataclasses.
- **Evidence:** Frame and pitch events commonly omit `message_type`, `schema_version`, `correlation_id`, or `session_id`; the architecture's event-metadata audit records the same gap. `ConfigUpdateEvent` is explicitly reserved/unused.
- **Impact:** Debugging and replay across asynchronous/durable boundaries cannot always correlate frame, pitch, session, and artifact decisions.
- **Confidence:** High.
- **Recommendation:** Keep the specification authoritative but label unimplemented requirements and close them through a versioned contract migration.
- **Dependencies:** ARCH-001, schema compatibility, recording/replay consumers.
- **Effort:** Large.
- **Definition of Done:** Every asynchronous/durable message carries applicable required fields; schemas and compatibility readers are versioned; conservation/replay tests prove correlation end to end.

## AGT-002 — Copilot exception rule conflicts with established behavior

- **Finding:** `.github/copilot-instructions.md` broadly forbids `RuntimeError` and bare `Exception`, while the implementation uses typed runtime failures and broad boundary catches in established service/tooling/UI patterns.
- **Evidence:** Repository search finds many `RuntimeError` raises/catches and broad `Exception` boundaries; some are deliberate expected failures or last-resort isolation. Flake8 still passes.
- **Impact:** An agent following the wording literally may make unnecessary exception rewrites or hide legitimate boundary behavior.
- **Confidence:** High.
- **Recommendation:** Propose narrower guidance: domain failures use typed codes/exceptions; boundary catches must log and return a valid degraded state; broad catches need a documented isolation reason.
- **Dependencies:** Human approval because this changes automated-agent behavior.
- **Effort:** Small documentation decision; potentially large code cleanup separately.
- **Definition of Done:** Guidance distinguishes forbidden silent swallowing from allowed boundary isolation and matches enforced lint/tests.

## AGT-003 — File-size guidance hides the scale of inherited debt

- **Finding:** The 500-line rule is enforced only for new growth; 34 files are grandfathered and the active roadmap names only two extraction issues.
- **Evidence:** Gate output and its baseline; issues #14 and #15 cover `rig_profile.py` and setup providers.
- **Impact:** Agents can report the gate as clean without understanding concentration risk.
- **Confidence:** High.
- **Recommendation:** Require the gate output and grandfathered count in structural reviews, with no opportunistic refactor unless in scope.
- **Dependencies:** RM-001.
- **Effort:** Small guidance proposal.
- **Definition of Done:** Agent guidance names the grandfather mechanism, ownership rule, and issue requirement for each planned extraction.

## Readiness verdict

The guidance is strong enough for bounded maintenance work when paired with source inspection and worktree preservation. It is not a reliable statement that all runtime agents already satisfy every metadata rule. Proposed edits remain here because changing agent guidance was expressly excluded.
