from __future__ import annotations

import hashlib
import os
from typing import Iterable, List, Tuple

CHUNK = 1024 * 1024


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_text(text: str) -> str:
    return sha256_bytes(text.encode("utf-8"))


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def aggregate_hash(entries: Iterable[Tuple[str, str]]) -> str:
    ordered = sorted((rel.replace(os.sep, "/"), digest) for rel, digest in entries)
    payload = "\n".join(f"{rel}\0{digest}" for rel, digest in ordered)
    return sha256_text(payload)


def skill_dir_hash(root: str, skill_file: str = "SKILL.md") -> str:
    main_path = os.path.join(root, skill_file)
    digest = hashlib.sha256()
    digest.update(skill_file.encode("utf-8"))
    digest.update(b"\0")
    if os.path.isfile(main_path):
        with open(main_path, "rb") as handle:
            while True:
                chunk = handle.read(CHUNK)
                if not chunk:
                    break
                digest.update(chunk)
    digest.update(b"\0")
    entries: List[Tuple[str, str]] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if not os.path.islink(os.path.join(dirpath, d)))
        for name in sorted(filenames):
            full = os.path.join(dirpath, name)
            if os.path.islink(full):
                continue
            rel = os.path.relpath(full, root).replace(os.sep, "/")
            if rel == skill_file.replace(os.sep, "/"):
                continue
            entries.append((rel, sha256_file(full)))
    digest.update(aggregate_hash(entries).encode("ascii"))
    return digest.hexdigest()


def short_id(content_hash: str, real_path: str) -> str:
    seed = content_hash + "\x00" + os.path.normcase(os.path.realpath(real_path))
    return sha256_text(seed)[:24]