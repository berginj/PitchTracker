<#
.SYNOPSIS
Runs the reproducible software preflight for a physical PitchTracker validation.

.DESCRIPTION
This script does not claim physical accuracy. It verifies the software baseline,
records privacy-safe environment metadata, and prints the manual evidence steps
that require cameras and an independent calibrated reference.
#>

param(
    [string]$OutputDirectory = "validation_output",
    [switch]$SkipTests
)

$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot
$output = Join-Path $root $OutputDirectory
New-Item -ItemType Directory -Path $output -Force | Out-Null

function Invoke-Checked {
    param(
        [Parameter(Mandatory = $true)]
        [scriptblock]$Command,
        [Parameter(Mandatory = $true)]
        [string]$Description
    )

    & $Command
    if ($LASTEXITCODE -ne 0) {
        throw "$Description failed with exit code $LASTEXITCODE."
    }
}

Push-Location $root
try {
    Invoke-Checked { python setup_validator.py } "Setup validation"
    Invoke-Checked { python scripts/check_release_versions.py } "Release version validation"
    Invoke-Checked { python scripts/sync_schema.py --check } "Schema mirror validation"

    if (-not $SkipTests) {
        Invoke-Checked {
            python -m pytest tests/test_physical_validation_v2.py `
                tests/test_capture_qualification.py `
                tests/test_setup_snapshot.py -q
        } "Physical-validation software tests"
    }

    $metadata = [ordered]@{
        created_utc = (Get-Date).ToUniversalTime().ToString("o")
        commit = (git rev-parse HEAD)
        worktree_clean = -not [bool](git status --short)
        python = (python --version 2>&1)
        operating_system = [System.Environment]::OSVersion.VersionString
        app_version = (python -c "from contracts.versioning import APP_VERSION; print(APP_VERSION)")
        physical_measurements_collected = $false
    }
    $metadata | ConvertTo-Json | Set-Content (Join-Path $output "environment.json") -Encoding utf8

    Write-Host ""
    Write-Host "Software preflight complete. Physical validation is still required."
    Write-Host "Next: follow docs\PHYSICAL_VALIDATION_PROTOCOL_V2.md and docs\PHYSICAL_VALIDATION_EXECUTION_CHECKLIST.md."
    Write-Host "Do not place athlete names, video, serial numbers, or facility details in public reports."
}
finally {
    Pop-Location
}
