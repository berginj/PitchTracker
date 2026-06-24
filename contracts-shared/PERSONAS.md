# PitchTracker Contract Persona Context

Last updated: 2026-06-22

## Purpose

The canonical product personas now live in `../docs/USER_PERSONAS.md`. This
file keeps the schema-facing mapping so contract decisions stay tied to real
workflows without forcing persona-specific fields into every payload.

## Canonical Persona Set

Current pilot-phase personas:
- Setup Technician / Installer
- Coach / Session Operator
- Facility Owner / Program Director
- Pitcher / Athlete Review Recipient
- Support / Maintenance Operator

Read `../docs/USER_PERSONAS.md` before adding or changing durable schemas.

## Contract Mapping

### `session_summary.schema.json`

Primary workflow: coach completes or pauses a live session and needs a compact
summary for review, export, or upload.

Persona relevance:
- Primary producer: Coach / Session Operator
- Primary consumers: Coach / Session Operator, Pitcher / Athlete Review Recipient
- Secondary consumer: Facility Owner / Program Director when reviewing pilot
  adoption and value

### `session_upload.schema.json`

Primary workflow: a session leaves the local desktop product and is handed to a
remote analytics or reporting system.

Persona relevance:
- Primary producer: Coach / Session Operator or upload integration
- Primary consumers: Cloud analytics, dashboards, later reviewer experiences
- Privacy stakeholders: Facility Owner / Program Director, Pitcher / Athlete
  Review Recipient

### `training_report.schema.json`

Primary workflow: setup validation, troubleshooting, or diagnostics where a
technical operator needs evidence about capture quality and system health.

Persona relevance:
- Primary producer: Setup Technician / Installer
- Primary consumers: Setup Technician / Installer, Support / Maintenance
  Operator, engineering

### `marker_spec.schema.json`

Primary workflow: marked-ball experiments where detection or training tooling
needs a stable representation of the marking geometry.

Persona relevance:
- Primary producers: Vision engineer, advanced setup operator
- Primary consumers: Vision tooling and analysis pipelines

## Discovery Questions

Canonical discovery questions live in `../docs/USER_PERSONAS.md`. Contract
reviews should add schema-specific questions here only when they affect durable
payload shape, privacy, routing, or compatibility.

## Immediate Contract Implications

- Do not add persona fields just to label users; add them only when they change
  behavior, routing, privacy, or product outcomes.
- Add workflow context through README guidance, schema `description`, and
  `$comment` fields first.
- Add a new contract when a new durable artifact appears, especially for setup
  handoff, calibration validation, or player-facing review packages.
- Treat session context, calibration provenance, and export audience as likely
  future contract needs.
