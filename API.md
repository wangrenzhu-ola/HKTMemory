# HKT-Memory v5.0 API 参考

> v5 默认入口：`uv run scripts/hkt_memory_v5.py`

---

## 全局

```bash
uv run scripts/hkt_memory_v5.py <command> [options]
```

全局参数：

```bash
--memory-dir <path>                     # 默认 memory
--llm-provider <zhipu|openai|minimax>   # 默认 zhipu
```

---

## store - 存储记忆

```bash
uv run scripts/hkt_memory_v5.py store \
  --content "..."           # 记忆内容 (必需)
  --title "..."             # 标题（可选）
  --topic "general"         # 主题（可选）
  --layer all               # L0/L1/L2/all，默认 all
  --no-extract              # layer=all 时禁用自动提取
```

### 示例

```bash
uv run scripts/hkt_memory_v5.py store \
  --content "# API设计评审\n\n决定采用 RESTful" \
  --title "API设计评审" \
  --topic "meetings" \
  --layer all
```

---

## retrieve - 检索记忆

```bash
uv run scripts/hkt_memory_v5.py retrieve \
  --query "..."             # 查询文本 (必需)
  --layer all               # L0/L1/L2/all
  --topic "meetings"        # 主题过滤（可选）
  --limit 10                # 返回数量
```

### 示例

```bash
uv run scripts/hkt_memory_v5.py retrieve \
  --query "RESTful 决策" \
  --layer all \
  --limit 5
```

---

## sync - 层级同步

```bash
uv run scripts/hkt_memory_v5.py sync
uv run scripts/hkt_memory_v5.py sync --full
```

- `sync`：增量同步
- `sync --full`：全量重建 L1/L0

---

## stats - 统计信息

```bash
uv run scripts/hkt_memory_v5.py stats
```

---

## test - 端到端测试

```bash
uv run scripts/hkt_memory_v5.py test
```

---

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `HKT_MEMORY_DIR` | 记忆存储目录 | `memory` |
| `L1_EXTRACTOR_PROVIDER` | L1 提取 Provider | `zhipu` |
| `ZHIPU_API_KEY` | 智谱 API Key | - |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `MINIMAX_API_KEY` | MiniMax API Key | - |

---

## 兼容说明

- `scripts/hkt_memory_v4.py` 作为历史兼容入口保留
- v4 的 `bm25/test-retrieval/learn/error/maintenance/mcp/auto` 不属于 v5 主命令面
- 如需迁移旧命令，请参考 [MIGRATION_v4_to_v5.md](./MIGRATION_v4_to_v5.md)
