# HKT-Memory v5.0

自动分层长期记忆系统：L2 写入后自动触发 L1/L0 生成，支持结构化摘要与分层检索。

## 快速开始

```bash
cd .claude/skills/hkt-memory
bash install.sh

uv run scripts/hkt_memory_v5.py store \
  --content "# 会议纪要\n\n讨论 API 设计，决定采用 RESTful" \
  --title "API设计评审" \
  --topic "meetings" \
  --layer all

uv run scripts/hkt_memory_v5.py retrieve --query "RESTful" --layer all
```

## 主要命令

```bash
uv run scripts/hkt_memory_v5.py store --content "..." --layer all
uv run scripts/hkt_memory_v5.py retrieve --query "..." --layer all
uv run scripts/hkt_memory_v5.py sync --full
uv run scripts/hkt_memory_v5.py stats
uv run scripts/hkt_memory_v5.py test
```

## 文档

- [README_v5.md](./README_v5.md)
- [API.md](./API.md)
- [MIGRATION_v4_to_v5.md](./MIGRATION_v4_to_v5.md)
