#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = [
#     "openai>=1.0.0",
#     "requests>=2.31.0",
#     "tqdm>=4.66.0",
# ]
# ///
"""
HKT-Memory v5.0 - 自动分层存储系统

核心特性：
- L2 写入后自动触发 L1/L0 生成
- 使用 LLM 智能提取摘要
- 真正的三层文件系统

环境变量:
    HKT_MEMORY_DIR: 记忆存储目录（默认: ./memory）
    ZHIPU_API_KEY: 智谱 AI API Key（用于 L1 摘要提取）
    OPENAI_API_KEY: OpenAI API Key（可选）
    MINIMAX_API_KEY: MiniMax API Key（可选）
    L1_EXTRACTOR_PROVIDER: 摘要提取器提供商 (zhipu/openai/minimax)

使用方法:
    # 基础存储（自动触发三层）
    uv run scripts/hkt_memory_v5.py store --content "长文本..." --layer all
    
    # 仅存储 L2
    uv run scripts/hkt_memory_v5.py store --content "文本..." --layer L2
    
    # 全量同步（重新生成所有 L1/L0）
    uv run scripts/hkt_memory_v5.py sync --full
    
    # 检索
    uv run scripts/hkt_memory_v5.py retrieve --query "关键词" --layer all
"""

import argparse
import os
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# 添加项目路径
SCRIPT_DIR = Path(__file__).parent.parent.absolute()
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from layers.manager_v5 import LayerManagerV5


class HKTMv5:
    """HKT-Memory v5.0 主类"""
    
    def __init__(self, memory_dir: str = None, llm_provider: str = None):
        self.memory_dir = Path(memory_dir or os.environ.get("HKT_MEMORY_DIR", "memory"))
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        
        # 初始化分层管理器
        self.layers = LayerManagerV5(
            base_path=self.memory_dir,
            llm_provider=llm_provider or os.getenv("L1_EXTRACTOR_PROVIDER", "zhipu")
        )
    
    def store(self, 
              content: str, 
              title: str = "", 
              topic: str = "general",
              layer: str = "L2",
              metadata: Dict = None,
              auto_extract: bool = True) -> Dict[str, str]:
        """
        存储记忆
        
        Args:
            content: 内容
            title: 标题
            topic: 主题
            layer: 目标层 (L0/L1/L2/all)
            metadata: 元数据
            auto_extract: 是否自动提取（layer=all 时）
        """
        return self.layers.store(
            content=content,
            title=title,
            topic=topic,
            layer=layer,
            metadata=metadata,
            auto_extract=auto_extract
        )
    
    def retrieve(self, 
                 query: str, 
                 layer: str = "all",
                 topic: str = None,
                 limit: int = 10) -> Dict[str, List[Dict]]:
        """检索记忆"""
        return self.layers.retrieve(
            query=query,
            layer=layer,
            topic=topic,
            limit=limit
        )
    
    def sync(self, full: bool = False):
        """同步各层"""
        self.layers.sync_layers(full_sync=full)
    
    def stats(self) -> Dict[str, Any]:
        """获取统计"""
        return self.layers.get_stats()


def main():
    parser = argparse.ArgumentParser(
        prog="hkt-memory-v5.0",
        description="HKT-Memory v5.0 - 自动分层存储系统"
    )
    
    parser.add_argument(
        "--memory-dir",
        default=os.getenv("HKT_MEMORY_DIR", "memory"),
        help="记忆存储目录"
    )
    parser.add_argument(
        "--llm-provider",
        default=os.getenv("L1_EXTRACTOR_PROVIDER", "zhipu"),
        choices=["zhipu", "openai", "minimax"],
        help="LLM 提供商"
    )
    
    subparsers = parser.add_subparsers(dest="command", help="命令")
    
    # Store command
    store_parser = subparsers.add_parser("store", help="存储记忆")
    store_parser.add_argument("--content", "-c", required=True, help="内容")
    store_parser.add_argument("--title", "-t", default="", help="标题")
    store_parser.add_argument("--topic", default="general", help="主题")
    store_parser.add_argument(
        "--layer", 
        choices=["L0", "L1", "L2", "all"], 
        default="all",
        help="目标层（默认: all，自动触发三层）"
    )
    store_parser.add_argument(
        "--no-extract", 
        action="store_true",
        help="禁用自动提取（仅当 layer=all 时有效）"
    )
    
    # Retrieve command
    retrieve_parser = subparsers.add_parser("retrieve", help="检索记忆")
    retrieve_parser.add_argument("--query", "-q", required=True, help="查询")
    retrieve_parser.add_argument(
        "--layer",
        choices=["L0", "L1", "L2", "all"],
        default="all",
        help="目标层"
    )
    retrieve_parser.add_argument("--topic", help="主题过滤")
    retrieve_parser.add_argument("--limit", "-n", type=int, default=10, help="数量限制")
    
    # Sync command
    sync_parser = subparsers.add_parser("sync", help="同步各层")
    sync_parser.add_argument(
        "--full",
        action="store_true",
        help="全量同步（重新生成所有 L1/L0）"
    )
    
    # Stats command
    subparsers.add_parser("stats", help="显示统计")
    
    # Test command
    test_parser = subparsers.add_parser("test", help="测试存储和检索")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return
    
    # 初始化
    memory = HKTMv5(
        memory_dir=args.memory_dir,
        llm_provider=args.llm_provider
    )
    
    if args.command == "store":
        print("📝 存储记忆...")
        print(f"   Layer: {args.layer}")
        print(f"   Topic: {args.topic}")
        print(f"   Title: {args.title or 'Untitled'}")
        print()
        
        result = memory.store(
            content=args.content,
            title=args.title,
            topic=args.topic,
            layer=args.layer,
            auto_extract=not args.no_extract
        )
        
        print("\n✅ 存储完成!")
        print(f"   L2: {result.get('L2', 'N/A')}")
        print(f"   L1: {result.get('L1', 'N/A')}")
        print(f"   L0: {result.get('L0', 'N/A')}")
    
    elif args.command == "retrieve":
        print(f"🔍 检索: {args.query}")
        print(f"   Layer: {args.layer}")
        print()
        
        results = memory.retrieve(
            query=args.query,
            layer=args.layer,
            topic=args.topic,
            limit=args.limit
        )
        
        for layer_name, items in results.items():
            print(f"\n{'='*60}")
            print(f"📂 {layer_name} 层 ({len(items)} 条结果)")
            print(f"{'='*60}")
            
            for i, item in enumerate(items[:5], 1):
                title = item.get('title', item.get('id', 'Untitled'))
                content = item.get('summary', item.get('content', ''))[:100]
                print(f"\n{i}. {title}")
                print(f"   {content}...")
    
    elif args.command == "sync":
        print("🔄 同步各层...")
        if args.full:
            print("   模式: 全量同步")
        else:
            print("   模式: 增量同步")
        print()
        
        memory.sync(full=args.full)
    
    elif args.command == "stats":
        print("📊 统计信息\n")
        stats = memory.stats()
        
        for layer_name, layer_stats in stats.items():
            print(f"\n{'='*60}")
            print(f"📂 {layer_name} 层")
            print(f"{'='*60}")
            for key, value in layer_stats.items():
                print(f"   {key}: {value}")
    
    elif args.command == "test":
        print("🧪 运行测试...\n")
        
        test_content = """# MiniMax 语音转纪要工具

基于 MiniMax CodePlan API 的语音转文字工具，支持一键将录音文件转为结构化会议纪要。

## 核心特性

- 支持多种音频格式（mp3, m4a, mp4 等）
- 自动触发 L1/L0 分层存储
- 使用 LLM 智能提取摘要

## 决策

- 采用 MiniMax API 而非飞书妙记（成本考虑）
- 使用智谱 AI 进行摘要提取

## 行动项

- [ ] 测试 API 连接（负责人: 开发团队，截止: 今天）
- [ ] 编写使用文档（负责人: PM，截止: 明天）
"""
        
        print("Step 1/3: 存储测试内容（layer=all）...")
        result = memory.store(
            content=test_content,
            title="MiniMax 语音转纪要",
            topic="tools",
            layer="all"
        )
        print(f"   结果: L2={result.get('L2')}, L1={result.get('L1')}, L0={result.get('L0')}")
        
        print("\nStep 2/3: 检索测试...")
        results = memory.retrieve(query="MiniMax", layer="all", limit=3)
        for layer, items in results.items():
            print(f"   {layer}: {len(items)} 条结果")
        
        print("\nStep 3/3: 统计...")
        stats = memory.stats()
        for layer, layer_stats in stats.items():
            total = layer_stats.get('total_entries') or layer_stats.get('total_topics', 0)
            print(f"   {layer}: {total} 条记录")
        
        print("\n✅ 测试完成!")
        print(f"\n查看生成的文件:")
        print(f"   L2: {args.memory_dir}/L2-Full/daily/")
        print(f"   L1: {args.memory_dir}/L1-Overview/topics/tools.md")
        print(f"   L0: {args.memory_dir}/L0-Abstract/topics/tools.md")


if __name__ == "__main__":
    main()
