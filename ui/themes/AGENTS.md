# Shared presentation instructions

Inherits [shared UI instructions](../AGENTS.md). Primary packages: UX-01 and
UX-07 in the [workspace plan](../../docs/UX_WORKSPACE_PLAN.md).

- Extend the existing tokens, StyleManager and shared components. Do not add a
  second theme system or interpret legacy Glass names as a requirement for blur.
- Define reusable numeric hierarchy, spacing, control heights, surface and focus
  styles. Screens should select semantic variants rather than hard-code colors,
  fonts, tiny controls or repeated local stylesheets.
- Retain the light palette. Use operational status colors consistently and a
  separate outcome treatment for strike/ball. Always pair color with text or shape.
- Ensure normal text contrast of at least 4.5:1 and large text of at least 3:1;
  check focus/control boundaries at 3:1 where needed for identification. Token
  calculations do not replace checks of rendered previews, charts and overlays.
- Preserve readable disabled, hover, focus and selected states. Do not let a
  setup-specific style change unexpectedly restyle another workspace page.
- Test shared variants and inspect representative live/setup/review/dialog
  screenshots at the documented sizes and Windows scaling levels. Avoid tests
  that merely duplicate every token constant.
