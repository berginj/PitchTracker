"""Checksum selection binds to this build, despite retained older installers."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


@pytest.mark.parametrize("scenario", ["fresh", "missing", "stale"])
def test_installer_selection_ignores_old_output_and_requires_fresh_expected(tmp_path, scenario):
    shell = shutil.which("pwsh") or shutil.which("powershell")
    if not shell:
        pytest.skip("PowerShell is required to execute the build helper")
    root = Path(__file__).resolve().parents[1]
    definition = tmp_path / "installer.iss"
    definition.write_text('#define AppVersion "2.0.0"\n#define ReleaseTag "stereo"\n')
    output = tmp_path / "outputs"
    output.mkdir()
    (output / "PitchTracker-Setup-v1.0.0-old.exe").write_bytes(b"old installer")
    expected = output / "PitchTracker-Setup-v2.0.0-stereo.exe"
    if scenario != "missing":
        expected.write_bytes(b"current installer")
        if scenario == "stale":
            os.utime(expected, (0, 0))
    script = tmp_path / "check.ps1"
    script.write_text(
        'param($Helper, $Definition, $Output)\n$ErrorActionPreference="Stop"\n. $Helper\n'
        '$artifact = Get-FreshInstallerArtifact -DefinitionPath $Definition '
        '-OutputDirectory $Output -BuiltAfter ([datetime]"2000-01-01")\n$artifact.FullName\n'
    )
    result = subprocess.run(
        [shell, "-NoProfile", "-NonInteractive", "-File", str(script),
         "-Helper", str(root / "scripts" / "installer_artifact.ps1"),
         "-Definition", str(definition), "-Output", str(output)],
        capture_output=True, text=True, timeout=20,
    )
    if scenario == "fresh":
        assert result.returncode == 0, result.stderr
        assert result.stdout.strip() == str(expected)
    else:
        assert result.returncode != 0
