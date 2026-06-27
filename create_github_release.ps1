# Create GitHub Release v2.0.0-stereo
# Run this script after authenticating with: gh auth login

$ReleaseTag = "v2.0.0-stereo"
$InstallerPath = "installer_output\PitchTracker-Setup-v2.0.0-stereo.exe"

Write-Host "Creating GitHub Release $ReleaseTag..." -ForegroundColor Yellow
Write-Host ""

if (-not (Test-Path $InstallerPath)) {
    Write-Host "ERROR: Installer not found: $InstallerPath" -ForegroundColor Red
    Write-Host "Please build the installer first with: .\build_installer.ps1 -Clean" -ForegroundColor Yellow
    exit 1
}

$installerSize = (Get-Item $InstallerPath).Length / 1MB
Write-Host "Installer: $InstallerPath" -ForegroundColor Gray
Write-Host "Size:      $($installerSize.ToString('0.0')) MB" -ForegroundColor Gray
Write-Host ""

$releaseNotes = @"
# PitchTracker v2.0.0-stereo

Stereo-foundation rebuild. The product now proves it can receive, pair,
compare, and calibrate left/right camera images through a coherent setup
state machine before any pitch-tracking logic runs.

## Installation

1. Download ``PitchTracker-Setup-v2.0.0-stereo.exe``.
2. Run the installer on Windows 10/11.
3. Complete the stereo setup wizard before coaching use.
4. Use a fixed dual-camera rig and the hardware checklist.

## Included

- Rebuilt stereo capture foundation: buffer-safe pairing, timestamp-at-read,
  sync-check contract, and L/R persistence by hardware id
- Qt-free setup state machine driving a 7-step stereo wizard
  (cameras, calibration, ROI, detector, validation, export, quality report)
- Targetless coarse stereo rectification with epipolar error scoring;
  ChArUco demoted to optional fine-tuning
- Manual fixed-focus and exposure-lock scoring before calibration
- Left/right overlap + feature-match validation
- Camera catalog service (carry-over of known devices by hardware id)
- Durable calibration quality report with grading
- Service-oriented pipeline runtime with ``PipelineOrchestrator``

## Known Limitations

- Accuracy validation against reference equipment is pending.
- Setup requires a trained operator and controlled camera placement.
- Best suited to fixed facility/academy deployments.
- Cloud/mobile/TAG production integrations are deferred.

## Documentation

- ``README.md``
- ``docs/CURRENT_STATUS.md``
- ``CHANGELOG.md``

**Full Changelog**: https://github.com/berginj/PitchTracker/blob/main/CHANGELOG.md
"@

Write-Host "Creating release on GitHub..." -ForegroundColor Yellow
gh release create $ReleaseTag `
    --title "PitchTracker $ReleaseTag" `
    --notes $releaseNotes `
    $InstallerPath

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Release created successfully!" -ForegroundColor Green
    Write-Host ""
    Write-Host "View release at: https://github.com/berginj/PitchTracker/releases/tag/$ReleaseTag" -ForegroundColor Cyan
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to create release" -ForegroundColor Red
    Write-Host "You may need to authenticate first with: gh auth login" -ForegroundColor Yellow
}
