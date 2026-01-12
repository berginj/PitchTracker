param(
  [Parameter(Mandatory = $true)]
  [string]$Version,
  [string]$Message = "Update contract schema"
)

$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = Split-Path -Parent $root
$contractPath = Join-Path $repo "contracts-shared"
$versionFile = Join-Path $contractPath "schema/version.json"
$changelog = Join-Path $contractPath "CHANGELOG.md"

if (-not (Test-Path $contractPath)) {
  Write-Error "contracts-shared submodule not found."
}

if (-not (Test-Path $versionFile)) {
  Write-Error "contracts-shared/schema/version.json not found."
}

$versionJson = Get-Content $versionFile | ConvertFrom-Json
$versionJson.schema_version = $Version
$versionJson | ConvertTo-Json -Depth 3 | Set-Content $versionFile

if (-not (Select-String -Path $changelog -Pattern "## $Version" -Quiet)) {
  Add-Content $changelog "`n## $Version`n- $Message"
}

Push-Location $contractPath
git add schema/version.json CHANGELOG.md
git commit -m "$Message ($Version)"
Pop-Location

git add contracts-shared
git commit -m "update contracts submodule ($Version)"
