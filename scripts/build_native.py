"""Build the optional CPU module with an installed Zig compiler (development only).

Production wheels use native/pyproject.toml and the platform CMake toolchain.
"""

from pathlib import Path
import os
import subprocess
import sys
import sysconfig


def main():
    import pybind11

    target = Path(sysconfig.get_path("platlib")) / ("_pitchtracker_native" + sysconfig.get_config_var("EXT_SUFFIX"))
    source = Path(__file__).resolve().parents[1] / "native" / "bindings.cpp"
    compiler = (
        [os.environ["PITCHTRACKER_ZIG"]] if os.environ.get("PITCHTRACKER_ZIG") else [sys.executable, "-m", "ziglang"]
    )
    command = [
        *compiler,
        "c++",
        "-shared",
        "-O3",
        "-std=c++17",
        "-ffp-contract=off",
        "-I" + pybind11.get_include(),
        "-I" + sysconfig.get_path("include"),
        str(source),
        "-o",
        str(target),
    ]
    if sys.platform == "win32":
        architecture = "aarch64" if sysconfig.get_platform() == "win-arm64" else "x86_64"
        command.extend(
            [
                str(Path(sys.base_prefix) / "libs" / f"python{sys.version_info.major}{sys.version_info.minor}.lib"),
                "-target",
                f"{architecture}-windows-gnu",
                "-static-libstdc++",
            ]
        )
    subprocess.run(command, check=True, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    print(target)


if __name__ == "__main__":
    main()
