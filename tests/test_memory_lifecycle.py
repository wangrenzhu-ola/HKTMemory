import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.hkt_memory_v5 import HKTMv5


def test_soft_delete_restore_and_hard_delete(tmp_path):
    memory = HKTMv5(memory_dir=str(tmp_path / "memory"), llm_provider="zhipu")

    first = memory.store(
        content="部署策略需要保留 staging 验证",
        title="部署策略",
        topic="tools",
        layer="all",
    )
    memory_id = first["L2"]
    l1_topic_file = tmp_path / "memory" / "L1-Overview" / "topics" / "tools.md"
    l0_topic_file = tmp_path / "memory" / "L0-Abstract" / "topics" / "tools.md"

    initial = memory.retrieve(query="staging", layer="L2", limit=10)
    assert any(item["id"] == memory_id for item in initial["L2"])
    assert memory_id in l1_topic_file.read_text(encoding="utf-8")
    assert memory_id in l0_topic_file.read_text(encoding="utf-8")

    soft_deleted = memory.forget(memory_id=memory_id)
    assert soft_deleted["success"] is True
    assert soft_deleted["status"] == "disabled"
    assert soft_deleted["aggregate_rebuild"]["rebuilt"] == 0

    after_soft_delete = memory.retrieve(query="staging", layer="L2", limit=10)
    assert all(item["id"] != memory_id for item in after_soft_delete["L2"])
    assert not l1_topic_file.exists() or memory_id not in l1_topic_file.read_text(encoding="utf-8")
    assert not l0_topic_file.exists() or memory_id not in l0_topic_file.read_text(encoding="utf-8")

    restored = memory.restore(memory_id=memory_id)
    assert restored["success"] is True
    assert restored["status"] == "active"
    assert restored["aggregate_rebuild"]["rebuilt"] == 1

    after_restore = memory.retrieve(query="staging", layer="L2", limit=10)
    assert any(item["id"] == memory_id for item in after_restore["L2"])
    assert memory_id in l1_topic_file.read_text(encoding="utf-8")
    assert memory_id in l0_topic_file.read_text(encoding="utf-8")

    hard_deleted = memory.forget(memory_id=memory_id, force=True)
    assert hard_deleted["success"] is True
    assert hard_deleted["removed_from_l2"] is True
    assert hard_deleted["aggregate_rebuild"]["rebuilt"] == 0

    after_hard_delete = memory.retrieve(query="staging", layer="L2", limit=10)
    assert all(item["id"] != memory_id for item in after_hard_delete["L2"])
    assert not l1_topic_file.exists() or memory_id not in l1_topic_file.read_text(encoding="utf-8")
    assert not l0_topic_file.exists() or memory_id not in l0_topic_file.read_text(encoding="utf-8")


def test_cleanup_and_prune(monkeypatch, tmp_path):
    monkeypatch.setenv("HKT_MEMORY_MAX_ENTRIES_PER_SCOPE", "1")
    monkeypatch.setenv("HKT_MEMORY_PRUNE_MODE", "archive")
    memory = HKTMv5(memory_dir=str(tmp_path / "memory"), llm_provider="zhipu")

    first = memory.store(
        content="共享上下文 A",
        title="共享上下文 A",
        topic="tools",
        layer="L2",
    )
    second = memory.store(
        content="共享上下文 B",
        title="共享上下文 B",
        topic="tools",
        layer="L2",
    )

    stats = memory.stats()["lifecycle"]
    assert stats["statuses"]["archived"] >= 1
    visible = memory.retrieve(query="共享上下文", layer="L2", limit=10)["L2"]
    assert len([item for item in visible if item["id"] in {first["L2"], second["L2"]}]) == 1

    lifecycle = memory.layers.lifecycle
    old_event = {
        "timestamp": (datetime.now(timezone.utc) - timedelta(days=200)).isoformat(),
        "type": "recall",
        "memory_id": second["L2"],
        "scope": "topic:tools",
        "data": {},
    }
    with open(lifecycle.events_path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(old_event, ensure_ascii=False) + "\n")

    preview = memory.cleanup(dry_run=True)
    assert preview["deleted_count"] >= 1

    cleaned = memory.cleanup(dry_run=False)
    assert cleaned["deleted_count"] >= 1

    remaining_events = lifecycle.events_path.read_text(encoding="utf-8")
    assert old_event["timestamp"] not in remaining_events


def test_pin_importance_feedback_and_rebuild(tmp_path):
    memory = HKTMv5(memory_dir=str(tmp_path / "memory"), llm_provider="zhipu")

    first = memory.store(
        content="部署窗口需要灰度验证和回滚开关",
        title="灰度验证",
        topic="tools",
        layer="all",
    )
    second = memory.store(
        content="部署窗口需要预先准备回滚预案",
        title="回滚预案",
        topic="tools",
        layer="all",
    )

    pin_result = memory.pin(memory_id=first["L2"], pinned=True)
    importance_result = memory.set_importance(memory_id=first["L2"], importance="high")
    useful_result = memory.feedback(
        label="useful",
        memory_id=first["L2"],
        topic="tools",
        query="部署窗口",
        note="命中正确",
    )
    wrong_result = memory.feedback(
        label="wrong",
        memory_id=second["L2"],
        topic="tools",
        query="部署窗口",
        note="内容已经过时",
    )
    missing_result = memory.feedback(
        label="missing",
        topic="tools",
        query="部署窗口",
        note="还缺审批流细节",
    )
    rebuild_result = memory.rebuild()

    assert pin_result["success"] is True
    assert importance_result["importance"] == "high"
    assert useful_result["scope"] == "topic:tools"
    assert wrong_result["scope"] == "topic:tools"
    assert missing_result["scope"] == "topic:tools"
    assert rebuild_result["rebuilt"] == 2

    ranked = memory.retrieve(query="部署窗口", layer="L2", limit=10)["L2"]
    assert ranked[0]["id"] == first["L2"]

    lifecycle_stats = memory.stats()["lifecycle"]
    assert lifecycle_stats["feedback"]["by_label"]["useful"] >= 1
    assert lifecycle_stats["feedback"]["by_label"]["wrong"] >= 1
    assert lifecycle_stats["feedback"]["by_label"]["missing"] >= 1
    assert lifecycle_stats["feedback"]["scope_feedback"]["topic:tools"]["missing"] >= 1

    manifest = memory.layers.lifecycle.get_memory(first["L2"])
    assert manifest["pinned"] is True
    assert manifest["importance"] == "high"
    assert manifest["feedback_stats"]["useful"] >= 1

    learnings = (tmp_path / "memory" / "governance" / "LEARNINGS.md").read_text(encoding="utf-8")
    errors = (tmp_path / "memory" / "governance" / "ERRORS.md").read_text(encoding="utf-8")
    assert "记忆反馈 useful" in learnings
    assert "记忆反馈 wrong" in errors
    assert "记忆反馈 missing" in errors
