"""Copy-first memory migration and anti-pollution helpers."""

from __future__ import annotations

import fnmatch
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


PUBLIC_MEMORY_GITIGNORE_PATTERNS = [
    "# HKTMemory generated/runtime state (safe to rebuild)",
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "vector_store.*",
    "entity_index.*",
    "session_transcript_index.*",
    "memory.db",
    "_session_transcripts/",
    "_lifecycle/",
    ".cache/",
    "cache/",
    "tmp/",
    "temp/",
    "logs/",
    "*.log",
    "__pycache__/",
    "*.pyc",
    ".env",
    ".DS_Store",
]

_RUNTIME_PATTERNS = [
    "*.db",
    "*.sqlite",
    "*.sqlite3",
    "vector_store.*",
    "entity_index.*",
    "session_transcript_index.*",
    "memory.db",
    "*.log",
    "*.pyc",
    ".env",
    ".DS_Store",
]

_RUNTIME_DIR_NAMES = {
    "_lifecycle",
    "_session_transcripts",
    ".cache",
    "cache",
    "tmp",
    "temp",
    "logs",
    "backups",
    "__pycache__",
}

_DURABLE_TOP_LEVEL = {
    "L2-Full",
    "L1-Overview",
    "L0-Abstract",
    "governance",
    "docs",
    "README.md",
    "SKILL.md",
    "MEMORY_CONFLICT.md",
}


@dataclass(frozen=True)
class ClassifiedPath:
    relative_path: str
    action: str
    reason: str
    bytes: int = 0


def _as_posix(path: Path) -> str:
    return path.as_posix()


def classify_memory_path(relative_path: Path, is_dir: bool = False) -> ClassifiedPath:
    """Classify a memory-root relative path for public migration."""
    rel = _as_posix(relative_path)
    parts = relative_path.parts
    name = parts[-1] if parts else ""

    if not rel or rel == ".":
        return ClassifiedPath(rel, "skip", "root")
    if any(part in _RUNTIME_DIR_NAMES for part in parts):
        return ClassifiedPath(rel, "skip", "runtime-directory")
    if any(fnmatch.fnmatch(name, pattern) or fnmatch.fnmatch(rel, pattern) for pattern in _RUNTIME_PATTERNS):
        return ClassifiedPath(rel, "skip", "runtime-file")
    top = parts[0] if parts else ""
    if top in _DURABLE_TOP_LEVEL:
        return ClassifiedPath(rel, "copy", "durable-memory")
    if is_dir:
        return ClassifiedPath(rel, "scan", "directory")
    return ClassifiedPath(rel, "skip", "not-in-public-memory-contract")


def iter_migration_plan(source: Path) -> Iterable[ClassifiedPath]:
    for path in sorted(source.rglob("*")):
        rel = path.relative_to(source)
        classified = classify_memory_path(rel, is_dir=path.is_dir())
        if path.is_file():
            yield ClassifiedPath(classified.relative_path, classified.action, classified.reason, path.stat().st_size)
        elif classified.action == "skip":
            yield classified


def ensure_public_memory_gitignore(target: Path, dry_run: bool = False) -> Dict[str, Any]:
    gitignore = target / ".gitignore"
    existing = gitignore.read_text(encoding="utf-8").splitlines() if gitignore.exists() else []
    missing = [line for line in PUBLIC_MEMORY_GITIGNORE_PATTERNS if line not in existing]
    if missing and not dry_run:
        gitignore.parent.mkdir(parents=True, exist_ok=True)
        content = existing[:]
        if content and content[-1].strip():
            content.append("")
        content.extend(missing)
        gitignore.write_text("\n".join(content).rstrip() + "\n", encoding="utf-8")
    return {"path": str(gitignore), "added": missing, "changed": bool(missing)}


def migrate_memory_copy_first(
    source: Path,
    target: Path,
    *,
    dry_run: bool = True,
    overwrite: bool = False,
    include_aggregates: bool = True,
) -> Dict[str, Any]:
    """Plan or execute a non-destructive memory-root migration."""
    source = source.expanduser().resolve()
    target = target.expanduser().resolve()
    if not source.exists() or not source.is_dir():
        raise FileNotFoundError(f"source memory root does not exist: {source}")
    if source == target:
        raise ValueError("source and target must be different directories")

    copied: List[Dict[str, Any]] = []
    skipped: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    planned_bytes = 0

    for item in iter_migration_plan(source):
        rel_path = Path(item.relative_path)
        if not include_aggregates and rel_path.parts and rel_path.parts[0] in {"L0-Abstract", "L1-Overview"}:
            skipped.append({"path": item.relative_path, "reason": "aggregate-rebuildable"})
            continue
        if item.action != "copy":
            skipped.append({"path": item.relative_path, "reason": item.reason})
            continue
        src = source / rel_path
        dst = target / rel_path
        if dst.exists() and not overwrite:
            conflicts.append({"path": item.relative_path, "reason": "target-exists"})
            continue
        planned_bytes += item.bytes
        copied.append({"path": item.relative_path, "bytes": item.bytes, "overwrite": dst.exists()})
        if not dry_run:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)

    gitignore_result = ensure_public_memory_gitignore(target, dry_run=dry_run)
    return {
        "success": True,
        "mode": "dry-run" if dry_run else "copy",
        "copy_first": True,
        "source": str(source),
        "target": str(target),
        "overwrite": overwrite,
        "include_aggregates": include_aggregates,
        "counts": {
            "copy": len(copied),
            "skip": len(skipped),
            "conflict": len(conflicts),
            "planned_bytes": planned_bytes,
        },
        "copied": copied,
        "skipped": skipped,
        "conflicts": conflicts,
        "gitignore": gitignore_result,
        "next_steps": [
            f"hkt-memory --memory-dir {target} rebuild-index --full",
            f"hkt-memory --memory-dir {target} doctor --json",
        ],
    }
