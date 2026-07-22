<#
.SYNOPSIS
Publishes a pre-tagged, pre-verified PitchTracker release.

.DESCRIPTION
This script intentionally requires explicit inputs. It refuses to reuse an
existing release, requires an existing tag, and verifies that the supplied
checksum file matches the installer before uploading either asset.
#>

param(
    [Parameter(Mandatory = $true)]
    [ValidatePattern('^v\d+\.\d+\.\d+$')]
    [string]$Tag,

    [Parameter(Mandatory = $true)]
    [string]$InstallerPath,

    [Parameter(Mandatory = $true)]
    [string]$ChecksumPath,

    [Parameter(Mandatory = $true)]
    [string]$NotesFile,

    [string]$Title = ""
)

$ErrorActionPreference = "Stop"

foreach ($path in @($InstallerPath, $ChecksumPath, $NotesFile)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Required release input does not exist: $path"
    }
}

gh auth status | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "GitHub CLI is not authenticated. Run 'gh auth login'."
}

git rev-parse --verify "refs/tags/$Tag" | Out-Null
if ($LASTEXITCODE -ne 0) {
    throw "Tag $Tag does not exist locally. Create and review the tag first."
}

gh release view $Tag *> $null
if ($LASTEXITCODE -eq 0) {
    throw "Release $Tag already exists. Refusing to replace or modify it."
}

$expectedHash = (Get-Content -LiteralPath $ChecksumPath -Raw).Trim().Split()[0].ToLowerInvariant()
if ($expectedHash -notmatch '^[a-f0-9]{64}$') {
    throw "Checksum file must begin with a 64-character SHA-256 digest."
}

$actualHash = (Get-FileHash -LiteralPath $InstallerPath -Algorithm SHA256).Hash.ToLowerInvariant()
if ($actualHash -ne $expectedHash) {
    throw "Installer SHA-256 does not match the supplied checksum file."
}

if ([string]::IsNullOrWhiteSpace($Title)) {
    $Title = "PitchTracker $Tag"
}

gh release create $Tag `
    --verify-tag `
    --title $Title `
    --notes-file $NotesFile `
    $InstallerPath `
    $ChecksumPath

if ($LASTEXITCODE -ne 0) {
    throw "GitHub release creation failed for $Tag."
}

Write-Host "Published $Tag with verified installer SHA-256 $actualHash"
