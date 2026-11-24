from __future__ import annotations

import os
from types import SimpleNamespace

from skillmerge.config.loader import load_config
from skillmerge.services.exporter.registry import PlatformRegistry
from skillmerge.services.merger.merge_service import MergeService
from skillmerge.services.scanner.scanner_service import ScanOptions, ScannerService
from skillmerge.storage.db import Database
from skillmerge.storage.models import Skill
from skillmerge.storage.repos.skills_repo import SkillsRepo

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLATFORMS = os.path.join(ROOT, "platforms")


def write_skill(root, folder, name, description, body, assets=None, extra=None):
    directory = os.path.join(str(root), folder)
    os.makedirs(directory, exist_ok=True)
    lines = ["---", f"name: {name}", f"description: {description}"]
    for key, value in (extra or {}).items():
        if isinstance(value, list):
            lines.append(f"{key}:")
            for item in value:
                lines.append(f"  - {item}")
        else:
            lines.append(f"{key}: {value}")
    lines.append("---")
    with open(os.path.join(directory, "SKILL.md"), "w", encoding="utf-8", newline="\n") as handle:
        handle.write("\n".join(lines) + "\n\n" + body.strip() + "\n")
    for rel_path, content in (assets or {}).items():
        target = os.path.join(directory, rel_path.replace("/", os.sep))
        os.makedirs(os.path.dirname(target), exist_ok=True)
        mode = "wb" if isinstance(content, bytes) else "w"
        with open(target, mode) as handle:
            handle.write(content)
    return directory


def build_env(tmp_path):
    data_dir = str(tmp_path / "data")
    config, _ = load_config(data_dir)
    db = Database(str(tmp_path / "index.db"))
    db.initialize()
    repo = SkillsRepo(db)
    registry = PlatformRegistry(PLATFORMS)
    merge = MergeService(db, config, registry)
    scanner = ScannerService(db, config)
    return SimpleNamespace(
        config=config,
        db=db,
        repo=repo,
        registry=registry,
        merge=merge,
        scanner=scanner,
        data_dir=data_dir,
    )


def scan(env, root, depth=10):
    return env.scanner.scan(options=ScanOptions(roots=[str(root)], depth=depth))


def named_skills(env, names):
    result = []
    for name in names:
        row = env.db.query_one("SELECT * FROM skills WHERE name=? ORDER BY real_path LIMIT 1", (name,))
        result.append(Skill.from_row(row) if row else None)
    return result