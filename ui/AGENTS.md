# Shared user experience instructions

Applies throughout `ui/`. Read the [root specification](../AGENTS.md) and
[UX workspace plan](../docs/UX_WORKSPACE_PLAN.md). These are maintenance
instructions for UIAgent and MaintenanceAgent, not additional runtime agents.
[Roadmap](../docs/ROADMAP.md) owns status; target behavior is not shipped behavior.

## Shared experience contract

- Build toward one workspace with Live, Sessions, Players and Setup navigation.
  Settings, Help and advanced tools are secondary destinations. Dialogs are for
  bounded tasks, not the normal journey between core screens.
- Preserve the active session while navigating. Keep recording status visible
  outside Live. Page activation must not acquire cameras, record, edit the rig
  or start offline processing. Services enforce operation admission.
- Follow the plan's lifecycle vocabulary. Show one primary next action per
  context, with explicit progress and recovery for pending/failed operations.
  Do not infer successful commands from a click or duplicate domain state in widgets.
- Use the same session/pitch identifiers, measurement provenance, units and
  availability semantics in all views. Selected historical content must be
  distinguishable from the active recording context.
- Prioritize the coach's questions: are we recording, what happened on that
  pitch, and how is the session going? Keep research controls under advanced tools.

## Presentation and access

- Reuse theme tokens and shared components. Prefer fewer enclosing panels,
  readable numeric hierarchy and consistent spacing over screen-specific styles.
  Retain the light theme; dark mode is outside this work.
- Do not communicate readiness, recording, pitch outcome or quality through
  color alone. Operational error colors must not label every ball as a failure.
- Every visible action needs working behavior, a descriptive accessible name,
  keyboard access and visible focus. Explain disabled prerequisites. Icon-only
  controls also need an accessible description and tooltip.
- Use shared control-height tokens; avoid tiny local overrides such as the
  24-pixel pitcher Switch control. Keep units next to measurements and provenance
  accessible without relying only on hover.
- Make content shrinkable at 1366x768 and 1024x768; provide a deliberate reachable
  layout at 800x600. Essential recording controls must stay visible. Secondary
  content may scroll. Manual Windows scaling checks cover 125%, 150% and 200%.
- Design empty, loading, unavailable, rejected, partial-data and recoverable-error
  states alongside populated views. Unavailable is not zero or a normal ball verdict.

## Ownership and handoff

- Keep algorithms, persistence and operation admission in existing services.
  Use public typed context handoffs; do not create cross-window private access.
- Read active/pending pitcher context from RuntimeStatus.pitcher. A browsed
  recorded label is separate from this context. Dispatch explicit changes through
  change_pitcher; never relabel a pitch from the latest roster or UI selection.
- Read saved setup context through SetupPresentation and its change signal.
  Configuration saves, check invalidation and publication remain service commands.
- Distinguish hiding a page from closing the application. Preserve in-flight
  operation ownership, cancellation, finalization and cleanup when refactoring.
- Follow additional instructions in [coaching](coaching/AGENTS.md),
  [review](review/AGENTS.md), [setup](setup/AGENTS.md),
  [analytics](analytics/AGENTS.md), [team](team/AGENTS.md) and
  [themes](themes/AGENTS.md). Dialogs and shared widgets inherit this file.
- For a UX work package, include focused behavior tests and synthetic before/after
  screenshots with viewport/state labels. Note tests skipped by dependency guards.
  Geometry and focus-property tests do not prove visual or screen-reader quality.
- Record evidence in the package handoff, update roadmap status, and document
  remaining manual checks. Do not revive archived implementations or backlogs.
