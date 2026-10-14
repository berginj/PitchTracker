# Analytics instructions

Inherits [shared UI instructions](../AGENTS.md). Primary package: UX-07 in the
[workspace plan](../../docs/UX_WORKSPACE_PLAN.md).

- Reuse workspace session/player selection through public interfaces. Clearly
  label the selected session, comparison set, units and observation counts.
- Present existing service-produced summaries. New chart layouts do not justify
  adding trajectory algorithms, pitch classification or physical claims to UI code.
- Preserve denominators and unavailable/rejected outcomes. Do not turn missing
  measurements into zero, silently drop failed comparisons, or let comparison
  output replace the primary result.
- Distinguish research comparisons from coach-facing summaries. Estimated,
  validated and legacy unknown results must retain their actual provenance.
- Use shared chart colors and labels, readable axes and a text/table equivalent
  for key results. Include empty, partial-data and incompatible-comparison states.
- Test selection consistency, unavailable results and primary/comparison
  separation; use synthetic chart screenshots for visual review.
