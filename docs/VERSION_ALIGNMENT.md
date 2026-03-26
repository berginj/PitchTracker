# Version Alignment and Pilot Build Lock

**Date:** March 26, 2026
**Status:** ✅ In Progress
**Owner:** Product/Engineering

---

## Executive Decision: Canonical Pilot Version

**OFFICIAL PILOT BUILD VERSION: v1.5.0**

This version is locked as the canonical pilot build effective immediately.

### Rationale

- CHANGELOG.md already documents v1.5.0 (Jan 2026) with pattern detection system
- contracts/versioning.py has APP_VERSION = "1.5.0"
- Most comprehensive feature set completed
- Best represents current product state

---

## Version Inconsistencies Identified (Pre-Alignment)

| Location | Version Found | Status |
|----------|--------------|--------|
| CHANGELOG.md | 1.5.0 | ✅ CANONICAL |
| contracts/versioning.py | 1.5.0 | ✅ CANONICAL |
| updater.py | 1.0.0 | ❌ MISALIGNED |
| docs/CURRENT_STATUS.md | 1.2.1+calibration-ux | ❌ MISALIGNED |
| README.md (installer ref) | 1.0.0 | ❌ MISALIGNED |
| docs/PRODUCT_STRATEGY.md | March 2026 (no version) | ⚠️ NEEDS VERSION TAG |

---

## Alignment Actions Required

### Immediate (Today)

1. **Update updater.py**
   - Change CURRENT_VERSION from "1.0.0" to "1.5.0"
   - Ensures auto-update mechanism reports correct version

2. **Update README.md**
   - Change installer references from v1.0.0 to v1.5.0
   - Update all version examples to v1.5.0

3. **Update docs/CURRENT_STATUS.md**
   - Change version from "1.2.1+calibration-ux" to "1.5.0-pilot"
   - Add pilot lock notice

4. **Tag Git Commit**
   - Create git tag: `v1.5.0-pilot`
   - Push tag to origin

5. **Update docs/PRODUCT_STRATEGY.md**
   - Add version reference: "Applies to: v1.5.0-pilot"

### Short-Term (Next 7 Days)

6. **Build Canonical Installer**
   - Build installer with v1.5.0 version string
   - Output: `PitchTracker-Setup-v1.5.0-pilot.exe`
   - Test installer on clean Windows machine

7. **Create Pilot Release Package**
   - Installer executable
   - Hardware compatibility list
   - Setup guide (updated for v1.5.0)
   - Known limitations doc

8. **Version Freeze Policy**
   - No new features to main branch without capability contract approval
   - Bug fixes allowed with patch version bump (v1.5.1, v1.5.2)
   - Pilot feedback features go to feature branches

---

## Version Governance Going Forward

### Version Numbering Scheme

**Format:** `MAJOR.MINOR.PATCH[-TAG]`

- **MAJOR**: Breaking changes to contracts or workflows (rare)
- **MINOR**: New capabilities that pass capability contract
- **PATCH**: Bug fixes, performance improvements, documentation
- **TAG**: -pilot, -beta, -rc1, etc.

**Examples:**
- `v1.5.0-pilot` - Current canonical pilot build
- `v1.5.1-pilot` - Bug fix to pilot build
- `v1.6.0-beta` - Next feature release (post-pilot)
- `v2.0.0` - Major breaking change (e.g., new contract schema)

### Single Source of Truth

**Authoritative Version Location:** `contracts/versioning.py`

All other locations must derive from this:
- updater.py imports from contracts.versioning
- Build scripts read from contracts.versioning
- Documentation references contracts.versioning
- Release tags match contracts.versioning.APP_VERSION

### Version Update Process

1. Update `contracts/versioning.py` (APP_VERSION and SCHEMA_VERSION if needed)
2. Update `CHANGELOG.md` with dated entry
3. Run version sync script (to be created) to propagate
4. Create git tag matching version
5. Build installer with version in filename
6. Update documentation references

---

## Pilot Build Characteristics (v1.5.0-pilot)

### What's Included
✅ Stereo camera capture with real-time 3D tracking
✅ Coaching mode (3 visualization modes)
✅ Review mode with trajectory overlay
✅ Pattern detection with pitch classification
✅ Pitcher profiles and baseline comparison
✅ Session recording with metadata
✅ ChArUco calibration system
✅ 389+ automated tests

### What's Excluded (Deferred Post-Pilot)
❌ Cloud analytics
❌ Mobile app integration
❌ Social sharing features
❌ ML-based detector (pilot uses classical)
❌ Consumer-oriented features

### Known Limitations (v1.5.0-pilot)
⚠️ Setup requires 30-60 minutes (ChArUco board, ROI calibration)
⚠️ Accuracy not yet validated against reference equipment
⚠️ Requires technical operator (not self-service)
⚠️ Best for fixed installations, not portable setups
⚠️ Windows 10/11 only

---

## Version Lock Commitment

**This build (v1.5.0-pilot) will remain stable for pilot program duration (90 days minimum).**

### What This Means

**Allowed:**
- Bug fixes (v1.5.1, v1.5.2)
- Documentation improvements
- Performance optimizations that don't change behavior
- Error messaging improvements

**Not Allowed:**
- New features without capability contract approval
- UI changes that alter workflows
- Contract/schema changes
- Breaking changes to export formats

**Exception Process:**
- Critical pilot blocker → emergency patch (v1.5.x)
- High-value pilot request → capability contract review → v1.6.0-beta branch
- Low-value requests → defer to post-pilot roadmap

---

## Verification Checklist

Before declaring alignment complete:

- [ ] updater.py shows CURRENT_VERSION = "1.5.0"
- [ ] README.md references v1.5.0 throughout
- [ ] docs/CURRENT_STATUS.md shows v1.5.0-pilot
- [ ] Git tag `v1.5.0-pilot` created and pushed
- [ ] contracts/versioning.py verified as source of truth
- [ ] CHANGELOG.md has entry for v1.5.0-pilot lock
- [ ] Installer builds with v1.5.0 in filename
- [ ] All documentation references checked

---

## Communication Plan

### Internal
- Engineering team notified of version freeze
- Capability contract checklist required for all new features
- Pilot feedback triage process defined

### External (Pilot Partners)
- "You are running v1.5.0-pilot, the canonical pilot build"
- Version number displayed in UI (About dialog, title bar)
- Release notes provided with known limitations

### Public (GitHub, README)
- README.md states: "Current version: v1.5.0-pilot (locked for pilot program)"
- CHANGELOG.md entry for v1.5.0-pilot with lock notice
- GitHub Releases page shows v1.5.0-pilot with pilot package

---

## Next Steps After Alignment

1. Execute Priority #2: Design velocity validation protocol
2. Execute Priority #3: Recruit 2-3 pilot partners
3. Build v1.5.0-pilot installer package
4. Create pilot onboarding materials
5. Begin pilot deployments

---

**Status:** Version alignment in progress (alignment actions being executed)
**Target Completion:** March 27, 2026
**Owner:** Engineering Lead + Product Manager
