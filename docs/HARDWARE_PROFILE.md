# PitchTracker Candidate Known-Good Hardware Profile

**Document Type:** Hardware Specification & Setup Guide
**Date:** March 26, 2026
**Version:** 1.0 (for v1.5.0-pilot)
**Status:** In validation testing; field evidence required before public known-good claims
**Owner:** Engineering + Operations

---

## Executive Summary

This document defines the **candidate hardware configuration** for PitchTracker v1.5.0-pilot. Treat these specifications as the pilot baseline until field deployments and reference validation confirm the final known-good profile.

**Purpose:**
- Provide pilot partners with clear hardware requirements
- Reduce setup variables and troubleshooting
- Establish baseline for accuracy validation
- Enable repeatable deployments

**Target Audience:** Pilot partners, facility operators, technical installers

---

## Hardware Requirements Overview

### Required Components
1. **Dual USB Cameras** (2× identical models)
2. **Windows Computer/Laptop** (Windows 10/11)
3. **ChArUco Calibration Board** (printed and mounted)
4. **Camera Mounting System** (tripods or custom mounts)
5. **USB Cables** (15+ feet for placement flexibility)

### Optional but Recommended
6. **Reference Radar Gun** (Pocket Radar, Stalker) for validation
7. **Lux Meter** (lighting verification)
8. **Tape Measure** (distance verification)
9. **Dedicated Monitor** (for operator visibility)

---

## 1. Camera Specifications

### Candidate Camera Models

#### Tier 1: Recommended Baseline
**Logitech C920 HD Pro Webcam**
- **Resolution:** 1920×1080 @ 30 FPS or 1280×720 @ 60 FPS
- **Field of View:** 78° diagonal
- **Focus:** Autofocus with manual override
- **Connection:** USB 2.0/3.0
- **Cost:** $60-80 per camera
- **Pros:** Widely available, reliable drivers, good low-light performance
- **Cons:** Plastic construction, limited mounting options
- **Pilot Status:** Baseline candidate; confirm field validation before public claims

**Logitech BRIO 4K**
- **Resolution:** 1920×1080 @ 60 FPS or 3840×2160 @ 30 FPS
- **Field of View:** 90° diagonal (adjustable to 78° or 65°)
- **Focus:** Autofocus with manual override
- **Connection:** USB 3.0 (requires USB 3.0 for 60 FPS)
- **Cost:** $150-200 per camera
- **Pros:** Higher frame rate option, better optics, 4K capability
- **Cons:** More expensive, requires USB 3.0
- **Pilot Status:** Testing candidate; do not claim validated until field evidence exists

#### Tier 2: Compatible (Not Yet Validated)
**Microsoft LifeCam HD-3000**
- **Resolution:** 1280×720 @ 30 FPS
- **Cost:** $25-40 per camera
- **Status:** Should work but not pilot-tested
- **Note:** Lower cost option for budget-constrained pilots

**ELP USB Camera (Various Models)**
- **Resolution:** Varies (720p-1080p)
- **Cost:** $30-60 per camera
- **Status:** Some users report success, needs validation
- **Note:** Wide variety of models, quality inconsistent

### Minimum Camera Requirements

**MUST HAVE:**
- ✅ USB Video Class (UVC) compatible OR OpenCV-readable
- ✅ Minimum resolution: 640×480 (preferably 1280×720 or higher)
- ✅ Minimum frame rate: 30 FPS (60 FPS preferred for high-velocity)
- ✅ Manual focus OR good autofocus (critical for consistent detection)
- ✅ USB 2.0 or higher (USB 3.0 preferred for bandwidth)

**SHOULD HAVE:**
- ⭐ Fixed focal length or lockable focus (prevents drift during session)
- ⭐ Mounting threads (1/4"-20 standard tripod mount)
- ⭐ Long USB cable included (or extension cable)
- ⭐ Good low-light performance (facilities often have variable lighting)

**AVOID:**
- ❌ Cameras with aggressive auto-exposure (causes detection issues)
- ❌ Cameras with slow autofocus hunting (creates frame-to-frame inconsistency)
- ❌ Cameras with proprietary drivers (UVC standard ensures compatibility)
- ❌ Extremely wide-angle lenses (>100° FOV introduces distortion)

### Camera Purchase Recommendations

**For Pilot Partners:**
- **Best Value:** 2× Logitech C920 ($120-160 total) - proven, reliable
- **Best Performance:** 2× Logitech BRIO ($300-400 total) - higher frame rate
- **Budget Option:** 2× Microsoft LifeCam HD-3000 ($50-80 total) - untested but should work

**Important:** Buy **identical camera models** (same brand, same model number). Mixed cameras complicate calibration.

---

## 2. Computer/Laptop Specifications

### Minimum Requirements (Will Work, May Struggle)
- **OS:** Windows 10 (64-bit) or Windows 11
- **Processor:** Intel Core i5-8th gen or AMD Ryzen 5 3000 series
- **RAM:** 8 GB
- **Storage:** 50 GB free space (for recordings)
- **USB Ports:** 2× USB 2.0 or higher (USB 3.0 preferred)
- **Display:** 1280×720 minimum resolution
- **Graphics:** Integrated graphics (Intel UHD, AMD Radeon)

**Expected Performance:**
- 30-40 FPS detection rate per camera at 720p
- May drop frames during high-intensity sessions
- 2-3 hour continuous recording before disk space concerns

### Recommended Requirements (Smooth Experience)
- **OS:** Windows 11 (64-bit)
- **Processor:** Intel Core i7-10th gen or AMD Ryzen 7 5000 series
- **RAM:** 16 GB
- **Storage:** 200 GB free space (SSD preferred)
- **USB Ports:** 2× USB 3.0 (separate controllers preferred)
- **Display:** 1920×1080 or higher
- **Graphics:** Dedicated GPU (optional, helps with UI rendering)

**Expected Performance:**
- 60-90 FPS detection rate per camera at 720p
- Stable frame retention >99%
- 8+ hour continuous recording capacity

### Optimal Requirements (Best Performance)
- **OS:** Windows 11 (64-bit)
- **Processor:** Intel Core i9 or AMD Ryzen 9
- **RAM:** 32 GB
- **Storage:** 500 GB SSD
- **USB Ports:** 4× USB 3.0 (dedicated USB 3.0 PCIe card)
- **Display:** 2560×1440 or 4K
- **Graphics:** Dedicated GPU (NVIDIA GTX 1650 or better)

**Expected Performance:**
- 60-90 FPS sustained with headroom
- Future-ready for 1080p @ 60 FPS or ML-based detection
- All-day recording sessions

### Operating System Notes

**Windows 10/11 (Primary Platform):**
- ✅ Fully supported and tested
- ✅ Installer package available
- ✅ Auto-update mechanism functional

**macOS (Limited Support):**
- ⚠️ Should work via Python launcher
- ⚠️ No installer package (manual setup required)
- ⚠️ Camera driver compatibility varies

**Linux (Experimental):**
- ⚠️ Should work via Python launcher
- ⚠️ UVC camera support generally good
- ⚠️ No official testing or support

**For Pilot Program:** Windows 10/11 ONLY to reduce variables.

---

## 3. Calibration Board Specifications

### ChArUco Board (Required)

**Default Configuration:**
- **Grid Size:** 5 columns × 6 rows
- **Square Size:** 30mm × 30mm
- **Marker Size:** ~20mm (embedded ArUco markers)
- **Paper Size:** US Letter (8.5" × 11") or A4 (210mm × 297mm)
- **Color:** Black and white (color printing not required)

### Printing Requirements

**CRITICAL - Print at 100% Scale:**
- ✅ NO "Fit to Page" or "Shrink to Fit"
- ✅ 100% scaling ONLY
- ✅ Verify actual square size with ruler: 30mm ± 0.5mm

**Print Quality:**
- ✅ High quality / Best quality setting
- ✅ Matte finish preferred (reduces glare)
- ✅ Thick paper or cardstock (for rigidity)
- ✅ Black ink density: dark, solid black squares

**Mounting:**
- ✅ Rigid backing: foam board, cardboard, or 1/4" plywood
- ✅ Perfectly FLAT (no warping, curling, or bending)
- ✅ Optional: laminate for durability and easy cleaning
- ✅ Handle with care (creases or damage ruin calibration)

### Board Dimensions

**Printed Board Size (6×6 grid, 30mm squares):**
- **Width:** ~150mm (5 columns × 30mm)
- **Height:** ~180mm (6 rows × 30mm)
- **Fits on:** US Letter or A4 paper

**Custom Sizes (Advanced):**
```bash
# Generate larger board for bigger facilities
python generate_charuco.py --cols 7 --rows 8 --size 40

# Generate smaller board for close-range calibration
python generate_charuco.py --cols 4 --rows 5 --size 25
```

**Verification After Printing:**
1. Measure actual square size with ruler
2. If the measured size is not 30mm, note the actual size for Setup Doctor board metadata
3. Ensure all ArUco markers are clearly visible and undamaged

---

## 4. Camera Mounting System

### Mounting Requirements

**Key Principles:**
- **Rigid mounting** (no wobble, shake, or drift)
- **Adjustable positioning** (height, angle, separation)
- **Behind home plate** (standard setup)
- **8-12 feet apart** (camera separation for stereo vision)
- **Eye-level to strike zone** (typically 3-5 feet off ground)

### Option 1: Tripods (Recommended for Pilots)

**Baseline Setup To Validate:**
- **2× Photo/Video Tripods** with 1/4"-20 screw mount
- **Height:** Adjustable 2-6 feet
- **Stability:** Weighted base or sandbag on tripod feet
- **Cost:** $30-50 per tripod

**Recommended Models:**
- Amazon Basics 60" Tripod (~$25 each)
- JOBY GorillaPod (flexible, $40-80 each)
- Manfrotto Compact Action ($50-70 each, very stable)

**Pros:**
- ✅ Adjustable height and angle
- ✅ Portable (can move between setups)
- ✅ Quick setup (5-10 minutes)

**Cons:**
- ❌ Can be bumped or knocked over
- ❌ Requires floor space behind plate
- ❌ May need sandbag weights for stability

### Option 2: Wall/Ceiling Mounts (Permanent Installations)

**Fixed Mounting:**
- **2× Camera Mounts** (1/4"-20 threaded)
- **Mounted to:** Wall studs or ceiling joists
- **Height:** 3-5 feet from ground (wall) or dropped from ceiling
- **Cost:** $15-30 per mount

**Recommended for:**
- Facilities with dedicated pitching tunnel
- Fixed camera positions (cameras never move)
- High-traffic areas (less risk of bumping)

**Pros:**
- ✅ Very stable (no wobble)
- ✅ No floor clutter
- ✅ Can't be knocked over

**Cons:**
- ❌ Permanent installation (requires drilling)
- ❌ Less flexible (can't easily adjust)
- ❌ Not portable

### Option 3: Custom Mounting (Advanced)

**DIY Options:**
- **PVC Pipe Frame:** Build freestanding frame from PVC pipe
- **Unistrut/T-slotted Aluminum:** Modular industrial framing
- **Ballhead Mounts:** Fine-angle adjustment (for precise calibration)

**See:** `3dModels/` directory for CAD files and mounting designs

**Recommended for:**
- Facilities with fabrication capability
- Custom/unusual setups
- Professional installations

---

## 5. Cable Requirements

### USB Cables

**Camera to Computer:**
- **Length:** 15-25 feet (5-8 meters)
- **Type:** USB 2.0 or USB 3.0 extension cables
- **Connectors:** USB-A male to USB-A female (extension) OR USB-A to camera's connector
- **Quality:** Shielded cables to reduce interference
- **Cost:** $10-20 per cable

**Important Notes:**
- ⚠️ USB cables >15 feet may require **active extension** (signal amplifier built-in)
- ⚠️ USB 3.0 cables >10 feet often need active extension
- ✅ Test cable length during pilot to ensure reliable connection
- ✅ Secure cables to prevent tripping hazards (tape down or cable covers)

**Recommended Vendors:**
- Cable Matters USB Extension Cables (reliable, good shielding)
- Amazon Basics USB Extension (budget option)
- Monoprice USB Active Extension (for longer runs)

### Power Cables (if applicable)

Most webcams are USB-powered (no external power needed). If using industrial cameras:
- Ensure power supply rated for camera requirements
- Use shielded power cables to reduce electrical noise
- Keep power cables separate from USB data cables

---

## 6. Environmental Conditions

### Lighting Requirements

**Minimum Lighting (REQUIRED):**
- **500 lux** minimum at ball trajectory (mid-flight between mound and plate)
- Measured with lux meter or smartphone app (e.g., "Lux Light Meter")

**Recommended Lighting:**
- **800-1200 lux** for optimal detection performance
- Even, diffuse lighting (avoid harsh shadows or bright spots)
- Indoor facility lighting OR outdoor daylight

**Lighting Types:**
- ✅ **LED Panel Lights** (even, bright, low heat)
- ✅ **Metal Halide** (common in sports facilities)
- ✅ **Natural Daylight** (outdoor setups, time-of-day consistent)
- ⚠️ **Fluorescent** (can cause flicker at 30/60 Hz, may affect detection)
- ❌ **Incandescent** (warm color temp, lower brightness, avoid)

**Common Issues:**
- **Too Dark (<500 lux):** Detection rate drops, more false negatives
- **Too Bright (>2000 lux):** Overexposure, ball appears washed out
- **Uneven Lighting:** Shadows cause detection inconsistency
- **Backlighting:** Ball silhouetted, hard to detect

**Solution:**
- Use lux meter to verify lighting levels
- Add supplemental lighting if needed (LED work lights, ~$30-50)
- Position lights to illuminate ball flight path evenly

### Background Requirements

**Ideal Background (Behind Batter):**
- ✅ **Solid, neutral color** (gray, tan, dark green)
- ✅ **Non-reflective** (matte finish, not shiny)
- ✅ **Consistent** (no busy patterns or varying colors)
- ✅ **Contrasts with ball** (white ball against darker background)

**Avoid:**
- ❌ **Bright or white backgrounds** (ball blends in, hard to detect)
- ❌ **Busy patterns** (chain-link fence, cluttered wall)
- ❌ **Reflective surfaces** (mirrors, glass, shiny metal)
- ❌ **Moving backgrounds** (people walking, flags waving)

**Common Facility Backgrounds:**
- ✅ **Batting cage netting** (dark color, fine mesh) - GOOD
- ⚠️ **Chain-link fence** (works but suboptimal, can interfere)
- ✅ **Painted concrete wall** (solid, matte) - IDEAL
- ❌ **Windowed wall** (backlight issues, avoid)

### Temperature & Humidity

**Operating Range:**
- **Temperature:** 50-95°F (10-35°C)
- **Humidity:** 20-80% relative humidity

**Notes:**
- Cameras generally tolerate wide temperature ranges
- Extreme cold (<40°F) may affect camera startup
- High humidity (>80%) may cause lens fogging
- Keep computer/laptop within normal operating range (avoid overheating)

### Physical Space Requirements

**Behind Home Plate (Camera Position):**
- **Width:** 10-15 feet (camera separation + clearance)
- **Depth:** 6-10 feet (backstop to camera distance)
- **Height Clearance:** 6-8 feet (camera mounting height + headroom)
- **Safety:** Area roped off or marked (prevent interference during sessions)

**Mound to Plate Distance:**
- **Standard:** 60.5 feet (MLB regulation)
- **High School:** 60.5 feet
- **Youth:** 46-54 feet (depending on age)
- **Softball:** 43 feet (fastpitch)

**Note:** Treat 54-60.5 feet as the priority validation range. Other distances may work but require calibration and accuracy confirmation.

---

## 7. Software & Firmware

### Operating System Configuration

**Windows 10/11 Settings:**
- ✅ **Disable USB Selective Suspend:** Prevents cameras from going to sleep
  - Control Panel → Power Options → Change plan settings → Advanced → USB settings → Disable
- ✅ **Disable Screen Saver:** Prevents interruption during sessions
- ✅ **Disable Sleep Mode:** Set to "Never" while running sessions
- ✅ **Disable Auto-Updates:** Or schedule for non-session times
- ✅ **Antivirus Exception:** Add PitchTracker folder to antivirus exceptions (prevents scan delays)

### Python Environment

**Version:** Python 3.10 or later (3.11 recommended)

**Key Dependencies (from requirements.txt):**
- opencv-contrib-python==4.10.0.84
- numpy (1.26.4 or 2.2.2 depending on Python version)
- scipy==1.17.0
- PySide6==6.10.1
- scikit-learn==1.8.0 (pattern detection)
- matplotlib==3.10.1 (charts/reports)

**Installation:**
```bash
pip install -r requirements.txt
```

**Estimated:** ~200 MB download, 5-10 minutes install time

### Camera Drivers

**UVC (USB Video Class) Cameras:**
- ✅ Native Windows support (no driver installation needed)
- ✅ Plug-and-play (appears as "USB Video Device")
- ✅ OpenCV auto-detects

**Proprietary Drivers (if required):**
- Install manufacturer's driver software
- Ensure "UVC mode" enabled if available
- Test with OpenCV before assuming compatibility

**Verification:**
```bash
# List detected cameras
python -c "import cv2; print([cv2.VideoCapture(i).isOpened() for i in range(5)])"
```

**Expected Output:** `[True, True, False, False, False]` (2 cameras detected at index 0 and 1)

---

## 8. Complete Hardware Checklist

Use this checklist for pilot partner hardware preparation:

### Pre-Pilot Procurement
- [ ] **2× USB Cameras** (Logitech C920 or better, identical models)
- [ ] **2× Tripods or Mounts** (1/4"-20 threaded, adjustable height)
- [ ] **2× USB Extension Cables** (15-25 feet, active if >15 feet)
- [ ] **Windows 10/11 Laptop/Desktop** (meets recommended specs)
- [ ] **ChArUco Board** (printed at 100% scale, mounted on rigid backing)
- [ ] **Tape Measure** (verify distances)
- [ ] **Lux Meter** (verify lighting, or smartphone app)
- [ ] **Reference Radar Gun** (optional but recommended for validation)

### Pilot Setup Day
- [ ] Cameras mounted behind home plate, 8-12 feet apart
- [ ] Cameras positioned at strike zone eye level (3-5 feet off ground)
- [ ] USB cables connected, tested (cameras detected by Windows)
- [ ] Lighting measured (500+ lux at ball flight path)
- [ ] Background checked (solid, neutral, contrasts with ball)
- [ ] ChArUco board ready (flat, undamaged, correct size)
- [ ] Computer configured (USB suspend disabled, sleep disabled)
- [ ] PitchTracker installed (v1.5.0-pilot)
- [ ] Dependencies installed (requirements.txt)
- [ ] Camera detection verified (2 cameras visible in Device Manager)

### First Session
- [ ] Run ChArUco calibration (10+ board poses captured)
- [ ] Configure ROI (lane + strike zone)
- [ ] Test session (5-10 pitches to verify detection)
- [ ] Verify velocity readings (compare to radar gun if available)
- [ ] Verify detection rate (>90% pitches captured)
- [ ] Document any issues or calibration drift

---

## 9. Candidate Setup Examples

### Example 1: Budget Pilot Setup ($200-300 total)
- **Cameras:** 2× Logitech C920 ($120-160)
- **Mounts:** 2× Amazon Basics Tripods ($50)
- **Cables:** 2× 15-foot USB extensions ($20)
- **Computer:** Existing Windows laptop (8GB RAM, i5 processor)
- **Board:** Printed at local print shop, mounted on foam board ($10)
- **Total:** ~$200-240

**Expected Performance:** 30-40 FPS, suitable for most pitching velocities up to 85 mph

### Example 2: Recommended Pilot Setup ($400-600 total)
- **Cameras:** 2× Logitech BRIO ($300-400)
- **Mounts:** 2× Manfrotto Compact Action Tripods ($100-140)
- **Cables:** 2× 20-foot USB 3.0 active extensions ($40)
- **Computer:** New Windows laptop (16GB RAM, i7 processor, $800+ if needed)
- **Board:** Professional print + lamination ($20-30)
- **Extras:** Lux meter ($25), Pocket Radar ($350, optional)
- **Total:** ~$460-610 (excluding computer if already owned)

**Expected Performance:** 60 FPS, higher accuracy, better reliability

### Example 3: Permanent Installation ($600-1000 total)
- **Cameras:** 2× Logitech BRIO ($300-400)
- **Mounts:** 2× Wall-mounted camera brackets ($30-60)
- **Cables:** 2× 25-foot USB 3.0 active extensions ($50)
- **Computer:** Dedicated Windows desktop (16GB RAM, i7, SSD, $1000-1200)
- **Board:** Professional print + permanent mounting ($50)
- **Lighting:** 2× LED panel lights ($100-150)
- **Extras:** Cable management, surge protector, dedicated monitor ($150)
- **Total:** ~$1630-2010 (full facility setup)

**Expected Performance:** Production-grade, 60 FPS sustained, all-day reliability

---

## 10. Troubleshooting Common Hardware Issues

### Cameras Not Detected

**Symptom:** PitchTracker can't find cameras, or only finds one camera

**Causes & Solutions:**
1. **USB Port Issue:**
   - Try different USB ports
   - Use USB 3.0 ports if available
   - Avoid USB hubs (direct connection preferred)

2. **Driver Issue:**
   - Check Device Manager (Windows: `devmgmt.msc`)
   - Look for "Imaging Devices" or "Cameras"
   - Reinstall camera drivers if "Unknown Device" shown

3. **Cable Too Long:**
   - USB cables >15 feet may not work without active extension
   - Try shorter cable to test

4. **Power Insufficient:**
   - Some cameras draw more power than USB 2.0 provides
   - Use USB 3.0 port (higher power delivery)
   - Try powered USB hub

**Verification Command:**
```bash
python -c "import cv2; [print(f'Camera {i}: {cv2.VideoCapture(i).isOpened()}') for i in range(4)]"
```

### Poor Detection Rate (<80%)

**Symptom:** Many pitches missed, low detection percentage

**Causes & Solutions:**
1. **Lighting Too Dark:**
   - Measure lighting with lux meter
   - Add supplemental LED lights
   - Target 800-1200 lux

2. **Background Too Bright/Busy:**
   - Hang dark backdrop behind batter
   - Solid color preferred (gray, tan, dark green)

3. **Camera Out of Focus:**
   - Manually focus cameras on ball flight path
   - Lock focus (disable autofocus if possible)

4. **Detection Parameters:**
   - Use Review Mode to tune detection parameters
   - Adjust frame_diff_threshold, bg_diff_threshold
   - See REVIEW_TRAINING_MODE_DESIGN.md

### Inaccurate Velocity Readings

**Symptom:** Velocity readings seem wrong (too high or too low)

**Causes & Solutions:**
1. **Calibration Drift:**
   - Recalibrate with ChArUco board
   - Ensure cameras haven't been bumped or moved

2. **Incorrect Distance:**
   - Verify mound-to-plate distance with tape measure
   - Update distance in calibration settings if changed

3. **Frame Rate Too Low:**
   - Check actual FPS in session logs
   - Reduce resolution if FPS <30
   - Upgrade to USB 3.0 or better camera

4. **No Baseline Comparison:**
   - Compare to reference equipment (Pocket Radar)
   - See VELOCITY_VALIDATION_PROTOCOL.md

### Calibration Fails

**Symptom:** ChArUco board not detected, calibration can't complete

**Causes & Solutions:**
1. **Board Printed Wrong:**
   - Verify squares are 30mm × 30mm with ruler
   - Ensure printed at 100% scale (not "Fit to Page")
   - Reprint if sizes don't match

2. **Board Not Flat:**
   - Mount on rigid backing (foam board, wood)
   - Eliminate any warping, curling, bending

3. **Lighting Too Dark/Bright:**
   - Board should be evenly lit
   - Avoid shadows or glare on board surface

4. **Camera Too Far:**
   - Move cameras closer to board (3-6 feet)
   - Board should fill ~30-50% of camera view

---

## 11. Upgrade Paths

### When to Upgrade Cameras

**Upgrade from Logitech C920 to BRIO if:**
- Tracking pitchers >85 mph regularly (higher frame rate helps)
- Detection rate <90% despite tuning (better sensor helps)
- Budget allows ($300-400 for both cameras)

**Upgrade from Budget Cameras (LifeCam, etc.) to C920 if:**
- Detection rate <80%
- Image quality poor (grainy, washed out)
- Reliability issues (cameras disconnect, freeze)

### When to Upgrade Computer

**Upgrade if:**
- FPS drops below 30 during sessions
- CPU usage >80% sustained
- Frequent frame drops or stuttering
- Disk space fills up quickly (upgrade to SSD)

**Recommended Upgrade:**
- Add RAM (8GB → 16GB): ~$40-80, easy install
- Upgrade to SSD: ~$60-100 for 500GB, significant improvement
- Replace laptop: $800-1200 for recommended specs

### When to Move to Permanent Installation

**Consider permanent installation if:**
- Running 15+ sessions per week (high usage)
- Facility has dedicated pitching area
- Tripods frequently bumped or knocked over
- Ready to invest $1000-2000 for full setup

**Benefits:**
- More stable (no wobble or movement)
- Faster session start (cameras always in position)
- Professional appearance
- Less risk of damage or theft

---

## 12. Support & Resources

### Hardware Procurement Support

**PitchTracker Can Provide:**
- Hardware vendor recommendations
- Bulk purchase discounts (if available)
- Setup checklists and guides
- Remote setup assistance

**Pilot Partners Responsible For:**
- Purchasing cameras, mounts, cables
- Printing and mounting ChArUco board
- Providing Windows computer
- Ensuring adequate lighting and background

### Hardware Validation Service (Optional)

**Pre-Pilot Hardware Check:**
- Ship cameras and board to PitchTracker team
- We verify compatibility and calibration quality
- Return with setup notes and configuration
- Cost: $50 service fee + shipping

**Benefits:**
- Ensures hardware will work before pilot starts
- Reduces setup day issues
- Confidence that equipment meets specs

### Documentation References

- **Calibration Guide:** `docs/user/CALIBRATION_TIPS.md`
- **Troubleshooting:** `docs/user/TROUBLESHOOTING.md`
- **FAQ:** `docs/user/FAQ.md`
- **Installation:** `docs/INSTALLATION.md`
- **Setup Doctor:** Built into PitchTracker under Calibration -> Setup Doctor

---

## Appendix A: Hardware Compatibility Matrix

| Component | Tier 1 (Pilot Baseline) | Tier 2 (Compatible) | Tier 3 (Untested) |
|-----------|-------------------|---------------------|-------------------|
| **Cameras** | Logitech C920, BRIO | MS LifeCam HD-3000, ELP USB | Generic webcams |
| **Mounts** | Amazon Basics, Manfrotto | JOBY GorillaPod | DIY PVC, custom |
| **Cables** | Cable Matters, Amazon Basics | Monoprice active | Generic USB ext |
| **Computer** | Dell, HP, Lenovo (i7/16GB) | Any Windows 10/11 (i5/8GB) | macOS, Linux |
| **OS** | Windows 11 | Windows 10 | macOS, Linux (unsupported) |

**Legend:**
- **Tier 1:** Recommended pilot baseline; requires field validation evidence before public claims
- **Tier 2:** Should work, not explicitly tested
- **Tier 3:** May work, no guarantees

---

## Appendix B: Hardware Budget Calculator

### Budget Pilot Setup
| Item | Quantity | Unit Cost | Total |
|------|----------|-----------|-------|
| Logitech C920 Camera | 2 | $70 | $140 |
| Amazon Basics Tripod | 2 | $25 | $50 |
| USB Extension Cable (15') | 2 | $10 | $20 |
| ChArUco Board (print + mount) | 1 | $15 | $15 |
| **SUBTOTAL** | | | **$225** |
| Computer (if needed) | 1 | $600 | $600 |
| **TOTAL (with computer)** | | | **$825** |

### Recommended Pilot Setup
| Item | Quantity | Unit Cost | Total |
|------|----------|-----------|-------|
| Logitech BRIO Camera | 2 | $175 | $350 |
| Manfrotto Tripod | 2 | $65 | $130 |
| USB 3.0 Active Ext (20') | 2 | $20 | $40 |
| ChArUco Board (pro print) | 1 | $25 | $25 |
| Lux Meter | 1 | $25 | $25 |
| Pocket Radar (optional) | 1 | $350 | $350 |
| **SUBTOTAL** | | | **$920** |
| Computer (if needed) | 1 | $1000 | $1000 |
| **TOTAL (with computer)** | | | **$1920** |

---

**Document Status:** Candidate baseline - requires owner confirmation before external pilot distribution
**Owner:** Engineering Lead
**Reviewed By:** Operations, Product
**Last Updated:** 2026-06-22
**Version:** 1.1
