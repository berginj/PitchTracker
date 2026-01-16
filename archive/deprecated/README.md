# Deprecated Code Archive

This directory contains deprecated code that has been replaced but preserved for reference.

---

## pitch_tracking_v1.py

**Original location:** `app/pipeline/pitch_tracking.py`

**Deprecated on:** 2026-01-16

**Replaced by:** `app/pipeline/pitch_tracking_v2.py`

### Why Deprecated?

The V1 implementation had 12 critical issues that caused data loss and timing errors:

1. **Pre-roll buffer always empty** - Buffered AFTER pitch starts
2. **Lost ~5 observations during ramp-up** - No RAMP_UP phase
3. **Timing errors of ±330ms** - Used trigger frame instead of first/last detection
4. **No thread safety** - Race conditions possible
5. **No data validation** - Saved empty/junk pitches
6. **No false trigger filtering** - No minimum duration check
7. **Callback errors corrupt state** - No error recovery
8. Plus 5 additional medium-severity issues

**Total data loss:** ~16 frames per pitch (~533ms @ 30fps)

### V2 Improvements

All issues fixed:
- ✅ Zero data loss (pre-roll and ramp-up captured correctly)
- ✅ Thread-safe with RLock
- ✅ Accurate timing (<33ms error instead of ±330ms)
- ✅ Data validation (min observations + duration)
- ✅ False trigger filtering
- ✅ Error recovery with state rollback
- ✅ Explicit state pattern (INACTIVE → RAMP_UP → ACTIVE → FINALIZED)

### Documentation

See comprehensive V2 documentation:
- `PITCH_TRACKING_V2_GUIDE.md` - Integration guide
- `PITCH_TRACKING_V2_SUMMARY.md` - Quick comparison
- `PITCH_TRACKING_V2_INTEGRATION.md` - Changes made
- `PITCH_TRACKING_ANALYSIS.md` - V1 issues detailed
- `V2_TEST_RESULTS.md` - Test results (8/8 passing)

### Should I Use This Code?

**NO.** This code is preserved only for reference. Use `pitch_tracking_v2.py` instead.

The V2 implementation is production-ready, fully tested, and addresses all critical bugs in V1.
