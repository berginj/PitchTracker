# Security Policy

## Report vulnerabilities privately

Do not open a public issue for a suspected vulnerability. Use
[GitHub private vulnerability reporting](https://github.com/berginj/PitchTracker/security/advisories/new)
and include:

- affected commit, tag, or installer filename;
- reproduction steps and expected impact;
- relevant configuration with secrets removed;
- whether camera, recording, calibration, update, or export data is involved; and
- any safe mitigation already identified.

Do not attach athlete media, private facility data, raw serial numbers,
credentials, trust keys, or unreviewed logs. Describe sensitive evidence and wait
for a private transfer plan.

## Supported code

Security fixes target current `main`. The latest public release may lag `main`;
each advisory will identify affected and fixed versions explicitly. No installer
should be assumed current merely because it remains downloadable from an older
release.

## Response and disclosure

Maintainers will triage reports on a best-effort basis, preserve reporter credit
when requested, and coordinate disclosure after a fix or mitigation is available.
Do not publish exploit details before coordinated disclosure.

## Security boundaries

- Recordings, frames, manifests, calibration artifacts, logs, athlete data, and
  facility details are private by default.
- The updater contacts the public GitHub Releases API.
- Optional cloud/TAG behavior must remain disabled unless explicitly enabled,
  authenticated, and configured.
- Release installers require exact commit/tag provenance and SHA-256 verification.
- Missing validation evidence must fail closed; it must not be converted into an
  assumed pass.

Last reviewed: **2026-08-16**.
