from __future__ import annotations

import os
from typing import Any, Dict, List, Tuple

from ...config.paths import expand_path
from ...util.errors import DomainError
from ..fsops import is_system_path, move_to_trash, reserve_dir
from .validate import errors, run_postflight


def install_root(rule: Dict[str, Any], scope: str, base_dir: str) -> str:
    value = str((rule.get("install") or {}).get(scope, ""))
    if not value:
        raise DomainError("EXPORT_BLOCKED", f"平台未提供 {scope} 安装目录", "改用 zip 下载或选择其他平台", 466)
    target = expand_path(value, base_dir)
    if is_system_path(target):
        raise DomainError("PATH_OUT_OF_BOUNDS", "拒绝安装到系统目录", "改用项目目录或 zip 下载", 400)
    return target


def _copy_tree(source_dir: str, target_dir: str) -> None:
    for dirpath, dirnames, filenames in os.walk(source_dir):
        dirnames[:] = sorted(dirnames)
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full) or name == "manifest.json":
                continue
            rel = os.path.relpath(full, source_dir)
            destination = os.path.join(target_dir, rel)
            os.makedirs(os.path.dirname(destination), exist_ok=True)
            with open(full, "rb") as source, open(destination, "wb") as target:
                target.write(source.read())


def install_copy(
    source_dir: str,
    rule: Dict[str, Any],
    scope: str,
    name: str,
    spec: Dict[str, Any],
    base_dir: str,
    save_dir: str,
) -> Tuple[str, List[Dict[str, str]]]:
    root = install_root(rule, scope, base_dir)
    os.makedirs(root, exist_ok=True)
    target = reserve_dir(root, name)
    try:
        _copy_tree(source_dir, target)
        installed_spec = dict(spec)
        installed_spec["mode"] = "install"
        installed_spec["layout_name"] = ""
        checks = run_postflight(rule, installed_spec)
        if errors(checks):
            move_to_trash(target, save_dir)
            raise DomainError("EXPORT_BLOCKED", "安装后校验未通过", "；".join(item["fix"] for item in errors(checks)), 466)
        return target, checks
    except DomainError:
        raise
    except Exception as exc:
        if os.path.isdir(target):
            move_to_trash(target, save_dir)
        raise DomainError("STORAGE_ERROR", "安装复制失败", f"检查目标目录权限：{exc}", 500)