# Documentation maintenance

Status: current maintenance policy. Last reviewed: 2026-10-16.

## Sources of truth

| Question | Canonical source |
|---|---|
| What is PitchTracker and where do I start? | [README](../README.md), [documentation map](README.md) |
| How should coding agents work? | [AGENTS.md](../AGENTS.md), applicable scoped instructions |
| What is delivered and validated? | [Current Status](CURRENT_STATUS.md), linked CI/evidence |
| What remains and what constitutes acceptance? | [Roadmap](ROADMAP.md), linked issues |
| How do operators run and qualify a rig? | [Operator runbook](OPERATOR_RUNBOOK.md), [rig walkthrough](RIG_VALIDATION_WALKTHROUGH.md) |
| Who owns runtime behavior? | [Architecture](ARCHITECTURE_CURRENT_STATE.md), [agent contracts](architecture/agent-contracts.md) |
| Why was a direction chosen? | [Architecture decisions](decisions/) |
| What did a particular validation demonstrate? | Dated [review evidence](review/) |
| Where are superseded plans? | [Archive index](../archive/docs/ARCHIVE_INDEX.md) |

## Change the existing guide first

Find the canonical page through the documentation map. Edit it in the behavior
change; update Current Status or Roadmap only when delivery or acceptance changes.
Keep the root README short. Tool-specific instruction files point to AGENTS.md
and contain only guidance specific to that tool.

New or substantially revised guides state whether they are current reference,
planned work or historical evidence, their scope and last actual review date.
Give each topic one authoritative guide and link to related contracts or evidence.
A review date records a review; it is not a freshness guarantee or an instruction
to change dates without reading the document.

Create a new page only for a distinct maintained topic, accepted decision,
substantial scoped plan or material validation result. Do not add a new summary,
completion report or backlog after every maintenance session. Reuse the existing
roadmap and validation record when they already own the information.

## Separate instruction, plan and evidence

Root and scoped AGENTS.md files contain durable working rules. Runtime service
tables belong in agent contracts. A plan describes scope and acceptance; the
roadmap records its delivery. Dated evidence records source revision, commands,
results, skipped checks and manual limits without becoming a competing backlog.

Prefer links to the relevant CI run over copying test counts across guides.
Keep release/app/schema identities distinct and link their canonical source.
Keep historical measurements and failure counts unchanged; correct a factual
error with a dated annotation rather than silently rewriting the evidence.
Simulator, geometry and rendering success do not grant physical accuracy approval.

## Archive without breaking readers

Preserve superseded full text under archive/docs/ and add it to the archive
index. Add a historical banner and a current-guide link, update relative links
and inbound references, and leave a short compatibility pointer where existing
links need to keep working. docs/archive/ contains old-path pointers only.

Keep useful contracts/procedures in the current guide before retiring migration
notes. Physical validation protocols, replay/quality contracts, schemas and
dated validation evidence stay available while their acceptance gates matter.
Deferred partnership/cloud concepts belong in the archive; current availability
belongs in [optional integrations](OPTIONAL_INTEGRATIONS.md).

Historical agent notes use a reference filename, not AGENTS.md or
AGENTS.override.md. Local scratch assets belong in ignored archive/local/,
which is also excluded from source lint/type checks. Never put private recordings,
calibration, operator state or credentials in the published documentation archive.

## Validation

Run python scripts/check_public_docs.py. It discovers all maintained Markdown
from Git plus new unignored files, checks local file/directory links with exact
filename case, validates review dates and checks required entry points. It also
checks the issue templates and prevents historical agent notes from being
discovered as instructions. Fenced examples and inline code are excluded from
prose checks; historical archive/evidence bodies keep their original context.
The archive index remains checked. Anchor existence and external URL availability
still require review; a passing link check does not prove semantic correctness.

For checker changes, also run python -m pytest tests/test_documentation_checks.py
and the repository lint/type gates.
