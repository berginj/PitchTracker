"""Local qualification identity without persisting a raw machine identifier."""

import hashlib
import os
import platform
from importlib.util import find_spec
from pathlib import Path
from contracts.model_bundle import file_hash


def native_cpu_identity():
    spec = find_spec("_pitchtracker_native")
    path = Path(spec.origin) if spec is not None and spec.origin else None
    return file_hash(path) if path is not None and path.is_file() else None


def hardware_identity():
    values = [platform.machine(), platform.processor(), str(os.cpu_count())]
    identifier = platform.node()
    if os.name == "nt":
        import winreg

        try:
            with winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\Cryptography",
                0,
                winreg.KEY_READ | winreg.KEY_WOW64_64KEY,
            ) as key:
                identifier = str(winreg.QueryValueEx(key, "MachineGuid")[0])
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"HARDWARE\DESCRIPTION\System\CentralProcessor\0") as key:
                values.append(str(winreg.QueryValueEx(key, "ProcessorNameString")[0]))
        except OSError as exc:
            raise ValueError("Cannot establish local qualification hardware identity") from exc
    value = "|".join([identifier, *values])
    return hashlib.sha256(value.encode()).hexdigest()
