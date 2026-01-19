# Documentation Archive Index

**Date:** 2026-01-18
**Action:** Documentation Cleanup and Archival
**Total Files Archived:** 25 files

---

## Purpose

This archive contains documentation that is no longer actively maintained but preserved for historical reference. Files were archived to:

1. **Reduce documentation clutter** in root and docs/ directories
2. **Keep historical record** of completed work and decisions
3. **Preserve reference material** for future questions
4. **Maintain clean project structure** with only current documentation

---

## Archive Structure

```
archive/docs/
├── completed/      - Completed work and superseded documentation (11 files)
└── reference/      - Historical reference and analysis documents (14 files)
```

---

## Completed Work (11 files)

Documentation for work that has been completed and superseded by newer docs.

### Root Level (8 files)

| File | Reason for Archival | Superseded By |
|------|---------------------|---------------|
| **V2_CLEANUP_TASKS.md** | All cleanup tasks completed | SESSION_SUMMARY_2026-01-18.md |
| **REFACTORING_PROGRESS.md** | Refactoring work 100% complete | Current codebase structure |
| **PIPELINE_REDUCTION_ANALYSIS.md** | Pipeline refactoring completed | Current pipeline implementation |
| **NEXT_STEPS.md** | Old roadmap | NEXT_STEPS_PRIORITIZED.md |
| **DEPLOYMENT_IMPROVEMENTS.md** | Early deployment planning | PRODUCTION_READINESS_STATUS.md |
| **UI_REDESIGN_ROADMAP.md** | UI redesign completed | Current UI structure |
| **UI_ROLE_BASED_REDESIGN.md** | UI redesign completed | Current UI implementation |
| **PRE_DEPLOYMENT_CHECKLIST.md** | Pre-deployment tasks complete | PRODUCTION_READINESS_STATUS.md |

### Docs Folder (3 files)

| File | Reason for Archival | Superseded By |
|------|---------------------|---------------|
| **INTEGRATION_COMPLETE.md** | Integration work completed | INTEGRATION_TESTS.md |
| **HARDENING_COMPLETE.md** | Hardening work completed | BLOCKERS_RESOLVED.md |
| **DEPLOYMENT_CHECKLIST.md** | Old deployment checklist | PRODUCTION_READINESS_STATUS.md |

---

## Reference Material (14 files)

Historical documentation preserved for reference purposes.

### Root Level (10 files)

| File | Type | Description |
|------|------|-------------|
| **PITCH_TRACKING_ANALYSIS.md** | Analysis | V1 issues analysis (12 critical bugs); historical context for V2 |
| **V2_TEST_RESULTS.md** | Test Results | V2 validation results (8/8 passing); historical testing record |
| **PITCHER_ANALYTICS_README.md** | Reference | Analytics features documentation |
| **PITCHER_ANALYTICS_INTEGRATION.md** | Reference | Analytics integration guide |
| **AGENTS.md** | Reference | Agent documentation and training material |
| **TRAJECTORY_PROMPT.md** | Reference | ML trajectory prompt documentation |
| **TRAINING.md** | Reference | Training and onboarding documentation |
| **SCREENSHOT_GUIDE.md** | Reference | UI screenshots and demo guide |
| **UI_PROTOTYPES_SUMMARY.md** | Reference | UI prototyping work from design phase |
| **CODE_SIGNING_GUIDE.md** | Optional | Code signing documentation (optional feature) |
| **DEMO_GUIDE.md** | Reference | Demo and presentation guide |
| **IMPROVEMENTS_SUMMARY.md** | Reference | Historical improvements summary |
| **CLEANUP_CHECKLIST.md** | Reference | Old cleanup tasks (completed) |
| **release_notes_v1.0.0.md** | Historical | v1.0.0 release notes |

### Docs Folder (8 files)

| File | Type | Description |
|------|------|-------------|
| **INTEGRATION_GUIDE.md** | Reference | Integration guidance documentation |
| **PROJECT_SUMMARY.md** | Reference | Historical project overview |
| **CAMERA_VALIDATION_GUIDE.md** | Reference | Camera validation procedures |
| **PRE_FIELD_TEST_CHECKLIST.md** | Reference | Pre-test checklist |
| **PITCH_RECORDING_GUIDE.md** | Reference | Recording procedures guide |
| **SYSTEM_BRITTLENESS_ANALYSIS.md** | Analysis | System brittleness investigation |
| **TIMESTAMP_AND_CALIBRATION_IMPROVEMENTS.md** | Reference | Historical calibration improvements |
| **camera_capture_validator.md** | Reference | Camera validation tool documentation |

---

## Active Documentation (Kept)

### Root Level (18 files)

**Core Documentation:**
- README.md
- CHANGELOG.md
- BUILD_INSTRUCTIONS.md
- README_INSTALL.md
- README_LAUNCHER.md

**Schema & Technical:**
- MANIFEST_SCHEMA.md
- CLOUD_SUBMISSION_SCHEMA.md
- DESIGN_PRINCIPLES.md
- REQ.md

**ML & Data Export:**
- ML_QUICK_REFERENCE.md
- ML_TRAINING_DATA_STRATEGY.md
- ML_TRAINING_IMPLEMENTATION_GUIDE.md
- CLOUD_SUBMISSION_GUIDE.md

**Pitch Tracking V2:**
- PITCH_TRACKING_V2_GUIDE.md
- PITCH_TRACKING_V2_SUMMARY.md
- PITCH_TRACKING_V2_INTEGRATION.md

**Deployment:**
- GITHUB_RELEASE_INSTRUCTIONS.md
- QUICK_START_IMPROVEMENTS.md

### Docs Folder (9 files)

**Production & Status:**
- PRODUCTION_READINESS_STATUS.md

**Testing & Quality:**
- INTEGRATION_TESTS.md
- PERFORMANCE_BENCHMARKS.md
- MEMORY_LEAK_TESTING.md

**Features:**
- STATE_CORRUPTION_RECOVERY.md
- CAMERA_RECONNECTION.md
- BLOCKERS_RESOLVED.md

**Planning:**
- NEXT_STEPS_PRIORITIZED.md
- SESSION_SUMMARY_2026-01-18.md

### User Documentation (3 files)

- docs/user/FAQ.md
- docs/user/TROUBLESHOOTING.md
- docs/user/CALIBRATION_TIPS.md

---

## Statistics

### Before Cleanup

| Location | Total Files | Lines |
|----------|-------------|-------|
| Root | 39 | ~7,000 |
| Docs | 20 | ~5,000 |
| **Total** | **59** | **~12,000** |

### After Cleanup

| Location | Active Files | Archived Files | Active Lines |
|----------|--------------|----------------|--------------|
| Root | 18 | 18 | ~3,500 |
| Docs | 9 | 11 | ~3,500 |
| User | 3 | 0 | 1,540 |
| **Total** | **30** | **29** | **~8,540** |

**Impact:** Reduced active documentation by 49% while preserving historical record

---

## Accessing Archived Documentation

**Location:** `archive/docs/completed/` and `archive/docs/reference/`

**Note:** Archived files are preserved in git history and remain searchable. They are not actively maintained but can be referenced if needed.

---

## Document Maintenance

**Last Cleanup:** 2026-01-18
**Next Review:** After major feature releases or quarterly
**Maintained By:** Development team

**Criteria for Future Archival:**
- Work completed and documented elsewhere
- Superseded by newer documentation
- Historical reference only (not actively used)
- Outdated technical information

---

**Archive Version:** 1.0
**Created:** 2026-01-18
