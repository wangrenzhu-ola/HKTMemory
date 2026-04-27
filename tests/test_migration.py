import json
import os
import subprocess
import sys
from pathlib import Path

from runtime.migration import classify_memory_path, migrate_memory_copy_first


def test_classify_memory_path_skips_runtime_state():
    assert classify_memory_path(Path("vector_store.db")).action == "skip"
    assert classify_memory_path(Path("_lifecycle/manifest.json")).action == "skip"
    assert classify_memory_path(Path("cache/tmp.json")).action == "skip"
    assert classify_memory_path(Path("L2-Full/daily/2026-04-27.md")).action == "copy"


def test_migrate_dry_run_is_copy_first_and_reports_gitignore(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "L2-Full" / "daily").mkdir(parents=True)
    (source / "L2-Full" / "daily" / "note.md").write_text("durable", encoding="utf-8")
    (source / "vector_store.db").write_text("generated", encoding="utf-8")
    (source / "_lifecycle").mkdir()
    (source / "_lifecycle" / "manifest.json").write_text("{}", encoding="utf-8")

    result = migrate_memory_copy_first(source, target, dry_run=True)

    assert result["success"] is True
    assert result["copy_first"] is True
    assert result["counts"]["copy"] == 1
    assert result["counts"]["skip"] >= 2
    assert result["gitignore"]["changed"] is True
    assert (source / "L2-Full" / "daily" / "note.md").exists()
    assert not (target / "L2-Full" / "daily" / "note.md").exists()


def test_migrate_apply_copies_durable_only_and_writes_gitignore(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "L2-Full" / "daily").mkdir(parents=True)
    (source / "L2-Full" / "daily" / "note.md").write_text("durable", encoding="utf-8")
    (source / "session_transcript_index.db").write_text("generated", encoding="utf-8")

    result = migrate_memory_copy_first(source, target, dry_run=False)

    assert result["mode"] == "copy"
    assert (target / "L2-Full" / "daily" / "note.md").read_text(encoding="utf-8") == "durable"
    assert not (target / "session_transcript_index.db").exists()
    gitignore = (target / ".gitignore").read_text(encoding="utf-8")
    assert "session_transcript_index.*" in gitignore
    assert "backups/" in gitignore


def test_migrate_conflict_and_overwrite(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    rel = Path("L2-Full/daily/note.md")
    (source / rel.parent).mkdir(parents=True)
    (target / rel.parent).mkdir(parents=True)
    (source / rel).write_text("new", encoding="utf-8")
    (target / rel).write_text("old", encoding="utf-8")

    conflict = migrate_memory_copy_first(source, target, dry_run=False)
    assert conflict["counts"]["conflict"] == 1
    assert (target / rel).read_text(encoding="utf-8") == "old"

    overwritten = migrate_memory_copy_first(source, target, dry_run=False, overwrite=True)
    assert overwritten["counts"]["conflict"] == 0
    assert (target / rel).read_text(encoding="utf-8") == "new"


def test_migrate_no_aggregates_skips_l0_l1(tmp_path):
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "L0-Abstract" / "topics").mkdir(parents=True)
    (source / "L0-Abstract" / "topics" / "x.md").write_text("aggregate", encoding="utf-8")
    (source / "L2-Full" / "daily").mkdir(parents=True)
    (source / "L2-Full" / "daily" / "note.md").write_text("durable", encoding="utf-8")

    result = migrate_memory_copy_first(source, target, dry_run=True, include_aggregates=False)

    assert any(item["reason"] == "aggregate-rebuildable" for item in result["skipped"])
    assert result["counts"]["copy"] == 1


def test_cli_migrate_json_dry_run(tmp_path):
    repo_root = Path(__file__).parent.parent
    source = tmp_path / "source"
    target = tmp_path / "target"
    (source / "L2-Full" / "daily").mkdir(parents=True)
    (source / "L2-Full" / "daily" / "note.md").write_text("durable", encoding="utf-8")
    env = os.environ.copy()
    env["HKT_MEMORY_ROOT"] = str(tmp_path / "runtime")

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "hkt_memory_v5.py"),
            "migrate",
            "--source",
            str(source),
            "--target",
            str(target),
            "--json",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["mode"] == "dry-run"
    assert payload["counts"]["copy"] == 1


def test_cli_rebuild_index_json(tmp_path):
    repo_root = Path(__file__).parent.parent
    env = os.environ.copy()
    env["HKT_MEMORY_ROOT"] = str(tmp_path / "runtime")

    result = subprocess.run(
        [
            sys.executable,
            str(repo_root / "scripts" / "hkt_memory_v5.py"),
            "rebuild-index",
            "--json",
        ],
        cwd=repo_root,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert "vector_store" in payload["steps"]
    assert "session_transcript_index" in payload["steps"]
