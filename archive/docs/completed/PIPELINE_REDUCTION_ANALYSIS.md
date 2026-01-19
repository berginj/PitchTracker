# Pipeline Service Further Reduction Analysis

## Current State

**File:** `app/pipeline_service.py`
**Lines:** 845 (48% reduction from original 1,625)
**Target:** <500 lines (<70% total reduction)

### Line Breakdown

| Section | Lines | Percentage |
|---------|-------|------------|
| Imports | 77 | 9% |
| Dataclasses (CalibrationProfile, PitchSummary, SessionSummary) | 38 | 4% |
| Abstract Interface (PipelineService) | 106 | 13% |
| Implementation (InProcessPipelineService) | 624 | 74% |
| **Total** | **845** | **100%** |

### Implementation Breakdown

| Component | Lines | Can Reduce? |
|-----------|-------|-------------|
| `__init__` composition | 43 | ❌ No - necessary setup |
| Callback coordination methods (5) | 150 | ⚠️  Possible - see below |
| Public interface delegators (18) | 320 | ❌ No - thin wrappers |
| Private helpers (3) | 111 | ⚠️  Possible - see below |

## Reduction Options

### Option 1: Extract Dataclasses ✅ Recommended
**Savings:** 38 lines
**Effort:** Low (15 minutes)
**Impact:** Minimal risk, cleaner organization

Create `app/pipeline/contracts.py`:
```python
from dataclasses import dataclass
from typing import List, Optional

@dataclass(frozen=True)
class CalibrationProfile:
    profile_id: str
    created_utc: str
    schema_version: str

@dataclass(frozen=True)
class PitchSummary:
    # ... fields ...

@dataclass(frozen=True)
class SessionSummary:
    # ... fields ...
```

Update `pipeline_service.py`:
```python
from app.pipeline.contracts import CalibrationProfile, PitchSummary, SessionSummary
```

**New Total:** 807 lines

### Option 2: Extract Abstract Interface ⚠️  Consider Carefully
**Savings:** 106 lines
**Effort:** Medium (30 minutes)
**Impact:** May hurt discoverability

Create `app/pipeline/interface.py`:
```python
from abc import ABC, abstractmethod

class PipelineService(ABC):
    # ... all abstract methods ...
```

**Concerns:**
- Abstract interface is valuable documentation for implementers
- Keeping it with implementation aids understanding
- Splitting may make codebase harder to navigate

**New Total (if done):** 701 lines

### Option 3: Extract Callback Coordinator ❌ Not Recommended
**Savings:** ~100 lines
**Effort:** High (2-3 hours)
**Impact:** High risk, unclear benefit

Create `app/pipeline/callback_coordinator.py` to handle:
- `_on_frame_captured()`
- `_on_detection_result()`
- `_on_stereo_pair()`
- `_on_pitch_start()`
- `_on_pitch_end()`

**Concerns:**
- These methods ARE the orchestration logic - they define the system flow
- Moving them obscures the main responsibility of InProcessPipelineService
- Would require passing many dependencies to coordinator
- Circular dependency risk
- Callbacks reference self._pitch_recorder, self._session_recorder, etc.
- **This is the core of what the orchestrator does**

**Verdict:** Do not extract - this is essential orchestration code

### Option 4: Simplify Recording Methods ⚠️  Possible
**Savings:** ~50 lines
**Effort:** Medium (1 hour)
**Impact:** Medium risk

Extract `_start_recording_io()` and `_stop_recording_io()` to a RecordingOrchestrator:
```python
class RecordingOrchestrator:
    def __init__(self, config, camera_mgr, stereo, gates, ...):
        # ... dependencies ...

    def start_session(self, session_name, pitch_id):
        # Create session recorder
        # Create pitch analyzer
        # Create session manager
        # Create pitch tracker
        # Export calibration
        return (session_recorder, pitch_analyzer, session_manager, pitch_tracker)

    def stop_session(self):
        # Close pitch recorder
        # Stop session recorder
```

**Concerns:**
- Adds another layer of indirection
- These methods are already quite clean
- Marginal readability improvement

**New Total (if done):** ~750 lines

## Recommendation

### Implement Option 1 Only ✅

Extract dataclasses to `app/pipeline/contracts.py`:
- **Low effort, low risk**
- **Cleaner separation of concerns**
- **New total: ~807 lines (50% reduction from original)**

### Do NOT Implement Options 2, 3, 4

The remaining code is essential orchestration logic:
- **Abstract interface:** Valuable documentation
- **Callback methods:** Core orchestration responsibility
- **Delegator methods:** Necessary interface implementation
- **Helper methods:** Already minimal

## Conclusion

**Current State (845 lines) is Excellent**

- ✅ 48% reduction from original (1,625 → 845)
- ✅ All complex logic extracted to focused modules
- ✅ Clear composition-based architecture
- ✅ Easy to understand and maintain
- ✅ No circular dependencies
- ✅ Thread-safe
- ✅ Well-tested

**With Option 1 (807 lines):**
- ✅ 50% reduction from original
- ✅ Even cleaner organization
- ✅ Still under 850 lines
- ✅ Minimal additional complexity

**Target of <500 lines is unrealistic without sacrificing:**
- Code clarity
- Maintainability
- Navigability
- Proper separation of concerns

The orchestrator SHOULD contain orchestration logic. The current implementation achieves the right balance.

## Implementation Steps (Option 1)

1. Create `app/pipeline/contracts.py`
2. Move CalibrationProfile, PitchSummary, SessionSummary
3. Update import in `pipeline_service.py`
4. Update imports in test files
5. Run tests to verify
6. Commit changes

**Time Estimate:** 15-20 minutes
**Risk Level:** Very Low
