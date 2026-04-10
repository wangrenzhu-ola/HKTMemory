---
name: "hkt-memory"
description: "生产级长期记忆系统 v5.0，支持 L2→L1/L0 自动分层与智能摘要提取"
triggers:
  - memory
  - recall
  - store
  - retrieve
---

# HKT-Memory v5.0

> 自动分层长期记忆系统：L2 写入后自动触发 L1/L0 生成，支持 LLM 智能摘要与分层检索

## 核心特性

- **三层自动提取**：L2 存储后自动触发 L1/L0 生成
- **LLM 智能摘要**：结构化提取标题、要点、决策、行动项
- **混合检索**：向量相似度 + BM25 融合召回
- **Weibull 衰减**：基于访问频率/重要性的生命周期管理
- **多作用域隔离**：global/agent/project/user/session 维度

## 快速开始

```bash
# 设置 API Key（智谱AI，用于 LLM 摘要提取）
export ZHIPU_API_KEY="your-api-key"

# 存储记忆（自动三层）
uv run scripts/hkt_memory_v5.py store \
  --content "# 会议纪要\n\n讨论 API 设计，决定采用 RESTful" \
  --title "API设计评审" \
  --topic "meetings" \
  --layer all

# 检索记忆
uv run scripts/hkt_memory_v5.py retrieve --query "API设计" --layer all
```

## 架构

```
┌─────────────────────────────────────────────────────────────┐
│                      HKT-Memory v5.0                        │
├─────────────────────────────────────────────────────────────┤
│  User Input                                                 │
│     │                                                       │
│     ▼                                                       │
│  ┌──────────────┐                                          │
│  │  Store L2    │ ◀── 完整内容存储                          │
│  └──────────────┘                                          │
│     │                                                       │
│     ▼                                                       │
│  ┌──────────────────┐                                      │
│  │  LayerTrigger    │ ◀── 自动触发器                        │
│  └──────────────────┘                                      │
│     │                                                       │
│     ├──▶ L1Extractor ──▶ 结构化摘要                         │
│     │                                                       │
│     └──▶ L0Extractor ──▶ 关键词 + 核心观点                   │
└─────────────────────────────────────────────────────────────┘

检索流程:
Query → Adaptive → HybridFusion → Rerank → Lifecycle → MMR → Scope → Results
```

## 三层记忆

| 层 | 用途 | 内容 |
|----|------|------|
| **L0** | 最小索引 | 关键词、核心观点、来源引用 |
| **L1** | 结构化摘要 | 标题、一句话摘要、要点、决策、行动项、人员、主题、重要性 |
| **L2** | 完整内容 | 原始 Markdown 内容 |

## 命令参考

```bash
# 存储
uv run scripts/hkt_memory_v5.py store --content "..." --layer all
uv run scripts/hkt_memory_v5.py store --content "..." --layer L2    # 仅 L2

# 检索
uv run scripts/hkt_memory_v5.py retrieve --query "关键词" --layer all
uv run scripts/hkt_memory_v5.py retrieve --query "关键词" --layer L1

# 同步
uv run scripts/hkt_memory_v5.py sync --full       # 全量重建索引
uv run scripts/hkt_memory_v5.py rebuild           # 重建并压缩聚合文件

# 统计
uv run scripts/hkt_memory_v5.py stats

# 遗忘/恢复
uv run scripts/hkt_memory_v5.py forget --memory-id "xxx"
uv run scripts/hkt_memory_v5.py restore --memory-id "xxx"

# 重要性标记
uv run scripts/hkt_memory_v5.py pin --memory-id "xxx" --value true
uv run scripts/hkt_memory_v5.py importance --memory-id "xxx" --value high

# 反馈
uv run scripts/hkt_memory_v5.py feedback --label useful --memory-id "xxx"
uv run scripts/hkt_memory_v5.py feedback --label wrong --memory-id "xxx"

# 测试
uv run scripts/hkt_memory_v5.py test
```

## 触发条件（Claude Code Skills 集成）

| 触发条件 | 动作 |
|----------|------|
| 用户要求"记住/存档/沉淀"偏好、决策、约束 | `store --layer all` |
| 需要回忆历史上下文 | `retrieve --layer all` |
| 需要按主题聚合信息 | `store/retrieve --topic <topic>` |
| 需要全量重建索引与摘要 | `sync --full` |
| 需要检查健康状态 | `stats` |

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `ZHIPU_API_KEY` | 智谱 AI API Key | - |
| `OPENAI_API_KEY` | OpenAI API Key | - |
| `L1_EXTRACTOR_PROVIDER` | LLM 提供商 | `zhipu` |
| `HKT_MEMORY_DIR` | 记忆存储目录 | `memory` |
| `HKT_MEMORY_LIFECYCLE_ENABLED` | 启用生命周期 | `true` |

## 项目结构

```
HKTMemory/
├── scripts/                    # CLI 入口
│   ├── hkt_memory_v5.py      # 主脚本
│   └── hkt_memory_v4.py      # 兼容 v4
├── layers/                     # 三层存储
│   ├── l0_abstract.py        # L0 抽象层
│   ├── l1_overview.py        # L1 概述层
│   ├── l2_full.py            # L2 完整层
│   └── manager_v5.py         # 分层管理器
├── extractors/                # 提取器
│   ├── l0_extractor.py       # L0 关键词提取
│   ├── l1_extractor.py      # L1 LLM 提取
│   └── trigger.py            # 层间触发器
├── retrieval/                 # 检索管道
│   ├── adaptive_retriever.py # 自适应查询分析
│   ├── hybrid_fusion.py      # 向量+BM25 融合
│   ├── bm25_index.py         # BM25 索引
│   └── mmr_diversifier.py    # MMR 多样性
├── lifecycle/                 # 生命周期
│   ├── memory_lifecycle.py   # 生命周期管理
│   ├── tier_manager.py       # 层 级 管理
│   └── weibull_decay.py      # Weibull 衰减模型
├── reranker/                  # 重排
├── scopes/                    # 作用域隔离
├── governance/                # 治理
│   ├── errors.py             # 错误跟踪
│   └── learnings.py          # 学习跟踪
├── vector_store/             # 向量存储
├── mcp/                      # MCP 协议服务
└── config/                   # 配置
```

## 文档

- [README_v5.md](./README_v5.md) - 详细文档
- [API.md](./API.md) - API 参考
- [DESIGN.md](./DESIGN.md) - 架构设计
- [MIGRATION_v4_to_v5.md](./MIGRATION_v4_to_v5.md) - v4 迁移指南

## 版本

**当前版本**: v5.0
