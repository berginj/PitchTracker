# Code Review: Next Five Improvement Items (2026-04-03)

## Scope
Review focused on maintainability, reliability, and roadmap alignment based on:
- Design constraints in `DESIGN_PRINCIPLES.md`
- High-churn core modules (`ui/`, `app/`, `calib/`)
- Existing TODO markers and roadmap docs

## 1) Break up oversized modules that violate the 500-line hard limit (P1)

The design policy sets a **hard maximum of 500 lines per file**, but several core modules are far beyond that threshold. Most critical hotspots include:
- `ui/setup/steps/calibration_step.py` (~4101 lines)
- `ui/main_window.py` (~1580 lines)
- `app/pipeline_service.py` (~995 lines)

This creates high review friction and change risk in the app’s most important runtime paths.

## 2) Replace broad exception catches in calibration/setup path with typed exceptions (P1)

The design policy says to avoid generic exception handling and use custom exception types. In setup calibration worker code, broad catches (`except Exception`) currently swallow error categories that should be differentiated (calibration failure, tooling invocation issues, I/O issues).

## 3) Complete incomplete coaching-session control logic (pause/resume) (P1)

Coaching flow has a stubbed pause implementation. This is a user-facing gap in session control and should be completed with service orchestration + UI state synchronization.

## 4) Finish strike-zone normalization using configured bounds instead of hardcoded assumptions (P2)

Broadcast/coaching visualization currently uses a fixed normalization model with a TODO to use real strike-zone config. This can generate misleading UI placement for players of different heights/profiles and should be sourced from active config/metrics definitions.

## 5) Prioritize TAG integration scaffolding into real deliverables behind feature flags (P2)

TAG integrations have clear placeholders for cloud auth/session sync and BLE integration. Instead of leaving these as passive stubs, convert them into staged deliverables:
- interfaces + mock adapters
- feature-flagged runtime wiring
- contract tests for upload/download payloads

This keeps partnership code from drifting while core product stabilizes.

## Why these five first

These items give the highest leverage on:
1. Lowering regression risk in core runtime code.
2. Improving operator trust (session control + accurate visualization).
3. Converting roadmap placeholders into testable increments.
