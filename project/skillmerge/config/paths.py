from __future__ import annotations

import os
import sys
from typing import Optional

DATA_DIR_ENV = "SKILLMERGE_DATA_DIR"


def base_dir() -> str:
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def data_dir(env: Optional[dict] = None) -> str:
    source = env if env is not None else os.environ
    override = source.get(DATA_DIR_ENV, "")
    if override:
        return os.path.abspath(os.path.expanduser(os.path.expandvars(override)))
    return os.path.join(base_dir(), "data")


def expand_path(value: str, base: Optional[str] = None) -> str:
    if not value:
        return ""
    expanded = os.path.expanduser(os.path.expandvars(value))
    if not os.path.isabs(expanded):
        expanded = os.path.join(base or base_dir(), expanded)
    return os.path.normpath(os.path.abspath(expanded))


def realpath(value: str) -> str:
    return os.path.realpath(os.path.abspath(os.path.expanduser(value)))


def norm_path(value: str) -> str:
    return os.path.normcase(realpath(value))


def is_within(target: str, root: str) -> bool:
    try:
        target_real = realpath(target)
        root_real = realpath(root)
        return os.path.commonpath([target_real, root_real]) == root_real
    except ValueError:
        return False


def ensure_dir(path: str) -> str:
    os.makedirs(path, exist_ok=True)
    return path


def default_save_dir(dd: Optional[str] = None) -> str:
    return os.path.join(dd or data_dir(), "artifacts")


def db_path(dd: Optional[str] = None) -> str:
    return os.path.join(dd or data_dir(), "index.db")


def config_path(dd: Optional[str] = None) -> str:
    return os.path.join(dd or data_dir(), "config.json")


def port_path(dd: Optional[str] = None) -> str:
    return os.path.join(dd or data_dir(), "port.txt")


def pid_path(dd: Optional[str] = None) -> str:
    return os.path.join(dd or data_dir(), "pid.txt")


def web_dir() -> str:
    return os.path.join(base_dir(), "web")


def platforms_dir() -> str:
    return os.path.join(base_dir(), "platforms")


def trash_dir(save_dir: str, stamp: str) -> str:
    return os.path.join(save_dir, ".trash", stamp)


def staging_dir(save_dir: str, token: str) -> str:
    return os.path.join(save_dir, ".staging", token)


def is_windows() -> bool:
    return os.name == "nt"