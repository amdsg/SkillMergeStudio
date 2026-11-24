from __future__ import annotations

import os
import string
from typing import Dict, List


def _windows_drives() -> List[Dict[str, str]]:
    try:
        import ctypes

        mask = ctypes.windll.kernel32.GetLogicalDrives()
        types = {2: "removable", 3: "fixed", 4: "network", 5: "cdrom", 6: "ramdisk"}
        drives: List[Dict[str, str]] = []
        for index, letter in enumerate(string.ascii_uppercase):
            if not (mask >> index) & 1:
                continue
            path = f"{letter}:\\"
            code = int(ctypes.windll.kernel32.GetDriveTypeW(ctypes.c_wchar_p(path)))
            drives.append({"path": path, "type": types.get(code, "unknown")})
        return drives
    except Exception:
        drives = []
        for letter in string.ascii_uppercase:
            path = f"{letter}:\\"
            if os.path.exists(path):
                drives.append({"path": path, "type": "unknown"})
        return drives


def _posix_drives() -> List[Dict[str, str]]:
    drives: List[Dict[str, str]] = [{"path": os.path.abspath(os.sep), "type": "fixed"}]
    for base in ("/Volumes", "/mnt", "/media"):
        if not os.path.isdir(base):
            continue
        try:
            names = sorted(os.listdir(base))
        except OSError:
            continue
        for name in names:
            path = os.path.join(base, name)
            if os.path.ismount(path):
                drives.append({"path": path, "type": "unknown"})
    return drives


def enumerate_drives() -> List[Dict[str, str]]:
    return _windows_drives() if os.name == "nt" else _posix_drives()


def select_drives(include_removable: bool = False, include_network: bool = False) -> List[Dict[str, str]]:
    result = []
    for drive in enumerate_drives():
        kind = drive["type"]
        if kind == "removable" and not include_removable:
            continue
        if kind == "network" and not include_network:
            continue
        if kind in ("cdrom", "ramdisk"):
            continue
        result.append(drive)
    return result