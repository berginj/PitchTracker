# PitchTracker Installer Build Script
# Builds PyInstaller bundle and creates Inno Setup installer

param(
    [switch]$Clean = $false,
    [switch]$SkipPyInstaller = $false,
    [switch]$SkipInnoSetup = $false
)

$ErrorActionPreference = "Stop"

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "PitchTracker Installer Build Script" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Get script directory
$ScriptDir = $PSScriptRoot
Set-Location $ScriptDir

# Check for required tools
function Test-Command {
    param($CommandName)
    return [bool](Get-Command -Name $CommandName -ErrorAction SilentlyContinue)
}

# Check Python and PyInstaller
if (-not $SkipPyInstaller) {
    if (-not (Test-Command "python")) {
        Write-Host "ERROR: Python not found in PATH" -ForegroundColor Red
        exit 1
    }

    $pythonVersion = python --version 2>&1
    Write-Host "✓ Found: $pythonVersion" -ForegroundColor Green

    try {
        python -c "import PyInstaller" 2>&1 | Out-Null
        Write-Host "✓ PyInstaller is installed" -ForegroundColor Green
    } catch {
        Write-Host "ERROR: PyInstaller not installed" -ForegroundColor Red
        Write-Host "Install with: pip install pyinstaller" -ForegroundColor Yellow
        exit 1
    }
}

# Check Inno Setup
if (-not $SkipInnoSetup) {
    $InnoSetupPath = "${env:ProgramFiles(x86)}\Inno Setup 6\ISCC.exe"
    if (-not (Test-Path $InnoSetupPath)) {
        Write-Host "ERROR: Inno Setup 6 not found at: $InnoSetupPath" -ForegroundColor Red
        Write-Host "Download from: https://jrsoftware.org/isdl.php" -ForegroundColor Yellow
        exit 1
    }
    Write-Host "✓ Found: Inno Setup 6" -ForegroundColor Green
}

Write-Host ""

# Clean previous builds
if ($Clean) {
    Write-Host "[1/4] Cleaning previous builds..." -ForegroundColor Yellow

    $DirsToClean = @("build", "dist", "installer_output")
    foreach ($dir in $DirsToClean) {
        if (Test-Path $dir) {
            Write-Host "  Removing $dir/" -ForegroundColor Gray
            Remove-Item -Path $dir -Recurse -Force
        }
    }

    Write-Host "  ✓ Clean complete" -ForegroundColor Green
    Write-Host ""
}

# Step 1: Build with PyInstaller
if (-not $SkipPyInstaller) {
    Write-Host "[2/4] Building with PyInstaller..." -ForegroundColor Yellow
    Write-Host "  This may take 2-5 minutes..." -ForegroundColor Gray
    Write-Host ""

    $startTime = Get-Date

    # Run PyInstaller
    python -m PyInstaller --clean launcher.spec

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: PyInstaller build failed" -ForegroundColor Red
        exit 1
    }

    $elapsedTime = (Get-Date) - $startTime
    Write-Host "  ✓ PyInstaller build complete ($($elapsedTime.TotalSeconds.ToString('0.0'))s)" -ForegroundColor Green

    # Check output
    if (-not (Test-Path "dist\PitchTracker\PitchTracker.exe")) {
        Write-Host "ERROR: PitchTracker.exe not found in dist/" -ForegroundColor Red
        exit 1
    }

    # Calculate bundle size
    $bundleSize = (Get-ChildItem "dist\PitchTracker" -Recurse | Measure-Object -Property Length -Sum).Sum / 1MB
    Write-Host "  Bundle size: $($bundleSize.ToString('0.0')) MB" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "[2/4] Skipping PyInstaller build" -ForegroundColor Gray
    Write-Host ""
}

# Step 2: Create icon (if missing)
Write-Host "[3/4] Checking assets..." -ForegroundColor Yellow

if (-not (Test-Path "assets")) {
    New-Item -ItemType Directory -Path "assets" | Out-Null
    Write-Host "  Created assets/ directory" -ForegroundColor Gray
}

if (-not (Test-Path "assets\icon.ico")) {
    Write-Host "  Warning: assets\icon.ico not found" -ForegroundColor Yellow
    Write-Host "  Installer will use default icon" -ForegroundColor Gray
} else {
    Write-Host "  ✓ Found assets\icon.ico" -ForegroundColor Green
}

Write-Host ""

# Step 3: Build Inno Setup installer
if (-not $SkipInnoSetup) {
    Write-Host "[4/4] Building Inno Setup installer..." -ForegroundColor Yellow
    Write-Host "  This may take 1-2 minutes..." -ForegroundColor Gray
    Write-Host ""

    $startTime = Get-Date

    # Run Inno Setup compiler
    & $InnoSetupPath "installer.iss"

    if ($LASTEXITCODE -ne 0) {
        Write-Host "ERROR: Inno Setup build failed" -ForegroundColor Red
        exit 1
    }

    $elapsedTime = (Get-Date) - $startTime
    Write-Host "  ✓ Installer build complete ($($elapsedTime.TotalSeconds.ToString('0.0'))s)" -ForegroundColor Green

    # Check output
    $installerFiles = Get-ChildItem "installer_output\*.exe"
    if ($installerFiles.Count -eq 0) {
        Write-Host "ERROR: Installer not found in installer_output/" -ForegroundColor Red
        exit 1
    }

    $installerPath = $installerFiles[0].FullName
    $installerSize = $installerFiles[0].Length / 1MB

    Write-Host ""
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host "Build Complete!" -ForegroundColor Green
    Write-Host "========================================" -ForegroundColor Cyan
    Write-Host ""
    Write-Host "Installer: $installerPath" -ForegroundColor Yellow
    Write-Host "Size:      $($installerSize.ToString('0.0')) MB" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Next steps:" -ForegroundColor Cyan
    Write-Host "  1. Test installer on clean Windows machine" -ForegroundColor Gray
    Write-Host "  2. Upload to GitHub Releases" -ForegroundColor Gray
    Write-Host "  3. Distribute to coaches" -ForegroundColor Gray
    Write-Host ""
} else {
    Write-Host "[4/4] Skipping Inno Setup build" -ForegroundColor Gray
    Write-Host ""
}
