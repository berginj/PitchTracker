# Create GitHub Release v1.5.0-pilot
# Run this script after authenticating with: gh auth login

$ReleaseTag = "v1.5.0-pilot"
$InstallerPath = "installer_output\PitchTracker-Setup-v1.5.0-pilot.exe"

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
# PitchTracker v1.5.0-pilot

Canonical pilot build for controlled facility deployments.

## Installation

1. Download ``PitchTracker-Setup-v1.5.0-pilot.exe``.
2. Run the installer on Windows 10/11.
3. Complete Setup Doctor before coaching use.
4. Use a fixed dual-camera rig and the pilot hardware checklist.

## Included

- Service-oriented pipeline runtime with ``PipelineOrchestrator``
- Setup Doctor and rig profile workflow
- Stereo capture, detection, recording, review, and analysis
- Pattern detection and pitcher profile workflows
- Local recording artifacts with manifests and summaries

## Known Limitations

- Accuracy validation against reference equipment is pending.
- Setup requires a trained operator and controlled camera placement.
- Best suited to fixed facility/academy deployments.
- Cloud/mobile/TAG production integrations are deferred.

## Documentation

- ``README.md``
- ``docs/CURRENT_STATUS.md``
- ``docs/VERSION_ALIGNMENT.md``
- ``docs/HARDWARE_PROFILE.md``
- ``docs/VELOCITY_VALIDATION_PROTOCOL.md``

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
