# Player workflow instructions

Inherits [shared UI instructions](../AGENTS.md). Primary package: UX-06 in the
[workspace plan](../../docs/UX_WORKSPACE_PLAN.md).

- Use Players for the workspace destination and Pitcher for the active pitching
  role. Reuse existing roster persistence and selection APIs.
- Keep the browsed historical player separate from the active session pitcher.
  Browsing, renaming or removing a roster entry must not rewrite recorded history.
- Route active-pitcher changes through explicit session commands. Apply a change
  only at a safe pitch boundary confirmed by the owning service; preserve the
  current pitch's attribution. Do not infer stable identity from a changed label.
- Handle empty rosters, duplicate/blank names, cancelled selection and unknown
  historical players clearly under existing validation rules. Do not introduce
  a player-ID migration as an incidental layout change.
- Keep player names and records local under existing privacy rules. Roster
  removal must not delete recordings. Use synthetic names in screenshots.
- Test roster selection, history filtering, cancellation and pitcher changes
  during a session, including attribution across the transition.
- Use the shared configs.pitchers validation and atomic persistence for roster
  edits and preparation dialogs. Report malformed data without overwriting it.
  Confirm activation from RuntimeStatus.pitcher; show queued changes explicitly.
