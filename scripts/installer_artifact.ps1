function Get-FreshInstallerArtifact {
    param(
        [Parameter(Mandatory = $true)][string]$DefinitionPath,
        [Parameter(Mandatory = $true)][string]$OutputDirectory,
        [Parameter(Mandatory = $true)][datetime]$BuiltAfter
    )
    $definition = Get-Content -LiteralPath $DefinitionPath -Raw
    $versionMatch = [regex]::Match($definition, '#define AppVersion "([A-Za-z0-9.-]+)"')
    $tagMatch = [regex]::Match($definition, '#define ReleaseTag "([A-Za-z0-9.-]+)"')
    if (-not $versionMatch.Success -or -not $tagMatch.Success) {
        throw "Cannot determine installer version/tag from installer.iss"
    }
    $name = "PitchTracker-Setup-v$($versionMatch.Groups[1].Value)-$($tagMatch.Groups[1].Value).exe"
    $path = Join-Path $OutputDirectory $name
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Expected installer not found: $path"
    }
    $artifact = Get-Item -LiteralPath $path
    if ($artifact.LastWriteTime -lt $BuiltAfter) {
        throw "Compiler did not produce a fresh installer: $path"
    }
    return $artifact
}
