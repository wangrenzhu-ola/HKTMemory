#!/usr/bin/env python3
"""
Layer Manager v5.0 - 自动分层存储

核心特性：
- L2 写入后自动触发 L1/L0 生成
- 使用 LLM 智能提取摘要
- 维护层间关联关系
"""

import sys
import re
from pathlib import Path
from typing import Dict, List, Optional, Any, Set
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from .l0_abstract import L0AbstractLayer
from .l1_overview import L1OverviewLayer
from .l2_full import L2FullLayer
from .query_matcher import match_query_corpus
from config.loader import ConfigLoader
from governance import ErrorTracker, LearningTracker
from lifecycle import MemoryLifecycleManager
from vector_store import VectorStore


class LayerManagerV5:
    """
    分层存储管理器 v5.0
    
    主要改进：
    1. L2 写入后自动触发 L1/L0 提取
    2. 支持 LLM 智能摘要
    3. 统一的三层文件格式
    """
    
    def __init__(self, base_path: Path, llm_provider: str = None, config: Optional[Dict[str, Any]] = None):
        """
        初始化管理器
        
        Args:
            base_path: 记忆根目录
            llm_provider: LLM 提供商 (zhipu/openai/minimax)
        """
        self.base_path = Path(base_path)
        self.config = config or ConfigLoader(self.base_path.parent).load()
        
        # 初始化各层
        self.l0 = L0AbstractLayer(self.base_path / "L0-Abstract")
        self.l1 = L1OverviewLayer(self.base_path / "L1-Overview")
        self.l2 = L2FullLayer(self.base_path / "L2-Full")
        
        # 向量存储
        self.vector_store = None
        self._vector_store_error: Optional[str] = None
        try:
            self.vector_store = VectorStore(str(self.base_path / "vector_store.db"))
        except Exception as e:
            self._vector_store_error = str(e)
            print(f"⚠️ Vector store unavailable: {e}")
        self.lifecycle = MemoryLifecycleManager(self.base_path, self.config.get("lifecycle", {}))
        self.learnings = LearningTracker(self.base_path / "governance")
        self.errors = ErrorTracker(self.base_path / "governance")
        
        # 触发器（延迟加载，避免循环导入）
        self._trigger = None
        self._llm_provider = llm_provider
        self.lifecycle.bootstrap(self.l2.iter_entries())
        self.lifecycle.cleanup_expired_events_on_startup()
    
    @property
    def trigger(self):
        """延迟初始化触发器"""
        if self._trigger is None:
            from extractors import LayerTrigger
            self._trigger = LayerTrigger(
                memory_dir=str(self.base_path),
                llm_provider=self._llm_provider
            )
        return self._trigger
    
    def store(self,
              content: str,
              title: str = "",
              layer: str = "L2",
              topic: str = "general",
              metadata: Optional[Dict[str, Any]] = None,
              auto_extract: bool = True) -> Dict[str, str]:
        """
        分层存储记忆 - v5.0 版本
        
        Args:
            content: 主要内容
            title: 标题
            layer: 目标层 (L0/L1/L2/all)
            topic: 主题
            metadata: 元数据
            auto_extract: 是否自动提取 L1/L0（当 layer=all 时）
            
        Returns:
            各层生成的ID映射
        """
        metadata = metadata or {}
        
        # 根据 layer 参数决定存储策略
        if layer == "L2":
            result = self._store_l2_only(content, title, topic, metadata)
            if result.get("pruned"):
                result["aggregate_rebuild"] = self.rebuild_aggregates()
            return result
        
        elif layer == "L1":
            # 存储到 L2，然后提取 L1
            l2_result = self._store_l2_only(content, title, topic, metadata)
            l1_result = self.trigger.on_l2_stored(
                l2_id=l2_result['L2'],
                content=content,
                title=title,
                topic=topic,
                enable_l1=True,
                enable_l0=False
            )
            result = {**l2_result, **l1_result}
            if l2_result.get("pruned"):
                result["aggregate_rebuild"] = self.rebuild_aggregates()
            return result
        
        elif layer == "L0":
            # 存储到 L2，然后提取 L0
            l2_result = self._store_l2_only(content, title, topic, metadata)
            l0_result = self.trigger.on_l2_stored(
                l2_id=l2_result['L2'],
                content=content,
                title=title,
                topic=topic,
                enable_l1=False,
                enable_l0=True
            )
            result = {**l2_result, **l0_result}
            if l2_result.get("pruned"):
                result["aggregate_rebuild"] = self.rebuild_aggregates()
            return result
        
        elif layer == "all":
            # ✅ v5.0 核心：存储 L2 并自动触发 L1/L0 提取
            l2_result = self._store_l2_only(content, title, topic, metadata)
            
            if auto_extract:
                all_results = self.trigger.on_l2_stored(
                    l2_id=l2_result['L2'],
                    content=content,
                    title=title,
                    topic=topic,
                    enable_l1=True,
                    enable_l0=True
                )
                result = {**l2_result, **all_results}
                if l2_result.get("pruned"):
                    result["aggregate_rebuild"] = self.rebuild_aggregates()
                return result
            else:
                return l2_result
        
        else:
            raise ValueError(f"Unknown layer: {layer}")
    
    def _store_l2_only(self, content: str, title: str, topic: str, 
                       metadata: Dict) -> Dict[str, str]:
        """仅存储到 L2 层"""
        content_lines = content.split('\n')
        l2_id = self.l2.store_daily(
            title=title or "Untitled",
            content_lines=content_lines,
            metadata={**metadata, "topic": topic}
        )
        
        # 同时存储到向量数据库
        if self._vector_store_can_add():
            try:
                add_success = self.vector_store.add(
                    doc_id=l2_id,
                    content=content,
                    layer="L2",
                    source=l2_id,
                    metadata={
                        "title": title,
                        "topic": topic,
                        **metadata
                    }
                )
                if not add_success:
                    print(f"⚠️ Vector store add returned false for {l2_id}")
            except Exception as e:
                print(f"⚠️ Vector store failed: {e}")

        entry = self.l2.get_entry(l2_id)
        if entry:
            self.lifecycle.register_memory(
                memory_id=l2_id,
                title=entry.get("title", title or "Untitled"),
                topic=entry.get("topic", topic),
                layer_type=entry.get("type", "daily"),
                source_path=entry.get("source_path", ""),
                metadata={**entry.get("metadata", {}), **metadata},
            )
            prune_result = self.lifecycle.prune_scope(entry.get("scope", f"topic:{topic}"))
        else:
            prune_result = {"triggered": False, "pruned": []}

        result = {"L2": l2_id}
        if prune_result.get("triggered"):
            result["pruned"] = prune_result.get("pruned", [])
        return result
    
    def store_episode(self,
                     episode_type: str,
                     content: str,
                     source: str = "",
                     topic: str = "general",
                     auto_extract: bool = True) -> Dict[str, str]:
        """存储 episode 并触发分层"""
        # 存储到 L2 episode
        l2_id = self.l2.store_episode(
            episode_type=episode_type,
            content=content,
            source=source
        )
        
        if auto_extract:
            result = self.trigger.on_l2_stored(
                l2_id=l2_id,
                content=content,
                title=f"Episode: {episode_type}",
                topic=topic,
                layer_type="episode"
            )
        else:
            result = {"L2": l2_id}

        entry = self.l2.get_entry(l2_id)
        if entry:
            self.lifecycle.register_memory(
                memory_id=l2_id,
                title=entry.get("title", f"Episode: {episode_type}"),
                topic=entry.get("topic", topic),
                layer_type=entry.get("type", "episode"),
                source_path=entry.get("source_path", ""),
                metadata=entry.get("metadata", {}),
            )
            prune_result = self.lifecycle.prune_scope(entry.get("scope", f"topic:{topic}"))
            if prune_result.get("triggered"):
                result["pruned"] = prune_result.get("pruned", [])
                result["aggregate_rebuild"] = self.rebuild_aggregates()
        return result
    
    def store_evergreen(self,
                       title: str,
                       content_lines: List[str],
                       category: str = "general",
                       topic: str = "general",
                       importance: str = "medium",
                       auto_extract: bool = True) -> Dict[str, str]:
        """存储永久记忆并触发分层"""
        # 存储到 L2 evergreen
        l2_id = self.l2.store_evergreen(
            title=title,
            content_lines=content_lines,
            category=category,
            importance=importance
        )
        
        content = '\n'.join(content_lines)
        
        if auto_extract:
            result = self.trigger.on_l2_stored(
                l2_id=l2_id,
                content=content,
                title=title,
                topic=topic,
                layer_type="evergreen"
            )
        else:
            result = {"L2": l2_id}

        entry = self.l2.get_entry(l2_id)
        if entry:
            self.lifecycle.register_memory(
                memory_id=l2_id,
                title=entry.get("title", title),
                topic=entry.get("topic", topic),
                layer_type=entry.get("type", "evergreen"),
                source_path=entry.get("source_path", ""),
                metadata={**entry.get("metadata", {}), "importance": importance},
            )
            prune_result = self.lifecycle.prune_scope(entry.get("scope", f"topic:{topic}"))
            if prune_result.get("triggered"):
                result["pruned"] = prune_result.get("pruned", [])
                result["aggregate_rebuild"] = self.rebuild_aggregates()
        return result
    
    def retrieve(self,
                 query: str = "",
                 layer: str = "all",
                 topic: Optional[str] = None,
                 limit: int = 10,
                 min_similarity: Optional[float] = None,
                 vector_weight: Optional[float] = None,
                 bm25_weight: Optional[float] = None,
                 debug: bool = False) -> Dict[str, List[Dict]]:
        """
        分层检索
        
        Args:
            query: 查询关键词
            layer: 目标层 (L0/L1/L2/all)
            topic: 主题过滤
            limit: 数量限制
            
        Returns:
            按层分组的结果
        """
        results = {}
        hybrid_options = self._get_hybrid_options(
            min_similarity=min_similarity,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )
        debug_info: Dict[str, Any] = {
            "query": query,
            "topic": topic,
            "layer": layer,
            "config": hybrid_options,
        }
        vector_l2_results = self._vector_retrieve_l2(
            query=query,
            topic=topic,
            limit=limit * 3,
            min_similarity=hybrid_options["min_similarity"],
            debug_info=debug_info if debug else None,
        )
        vector_l2_ids = {item.get("id") for item in vector_l2_results if item.get("id")}
        vector_scores = {
            item.get("id"): float(item.get("_vector_score", 0.0))
            for item in vector_l2_results
            if item.get("id")
        }

        if layer in ("L0", "all"):
            l0_results = self.l0.retrieve(query=query, topic=topic, limit=limit * 3)
            if vector_l2_ids:
                l0_related = self._retrieve_l0_by_sources(topic=topic, source_ids=vector_l2_ids, vector_scores=vector_scores)
                l0_results = self._merge_results(l0_results, l0_related, key_field="source_l2")
            self._apply_hybrid_scores(l0_results, hybrid_options["vector_weight"], hybrid_options["bm25_weight"])
            if debug:
                debug_info.setdefault("layers", {})["L0"] = self._build_layer_debug(l0_results)
            results['L0'] = self._sort_by_lifecycle(
                [item for item in l0_results if self.lifecycle.is_visible(item.get("source_l2"))],
                limit,
            )

        if layer in ("L1", "all"):
            l1_results = self._retrieve_l1(query=query, topic=topic, limit=limit * 3)
            if vector_l2_ids:
                l1_related = self._retrieve_l1_by_sources(topic=topic, source_ids=vector_l2_ids, vector_scores=vector_scores)
                l1_results = self._merge_results(l1_results, l1_related, key_field="source_l2")
            self._apply_hybrid_scores(l1_results, hybrid_options["vector_weight"], hybrid_options["bm25_weight"])
            if debug:
                debug_info.setdefault("layers", {})["L1"] = self._build_layer_debug(l1_results)
            results['L1'] = self._sort_by_lifecycle(
                [item for item in l1_results if self.lifecycle.is_visible(item.get("source_l2"))],
                limit,
            )

        if layer in ("L2", "all"):
            l2_results = self.l2.search(query=query, scope="all")
            if topic:
                l2_results = [item for item in l2_results if item.get("topic") == topic]
            l2_results = self._merge_results(l2_results, vector_l2_results, key_field="id")
            self._apply_hybrid_scores(l2_results, hybrid_options["vector_weight"], hybrid_options["bm25_weight"])
            if debug:
                debug_info.setdefault("layers", {})["L2"] = self._build_layer_debug(l2_results)
            l2_results = [item for item in l2_results if self.lifecycle.is_visible(item.get("id"))]
            results['L2'] = self._sort_by_lifecycle(l2_results, limit)

        touched_ids: List[str] = []
        for items in results.values():
            for item in items:
                source_id = item.get("source_l2") or item.get("id")
                if source_id:
                    touched_ids.append(source_id)
        self.lifecycle.touch(list(dict.fromkeys(touched_ids)))
        if debug:
            debug_info["final_counts"] = {
                layer_name: len(items)
                for layer_name, items in results.items()
            }
            debug_info["top_hits"] = {
                layer_name: [self._compact_debug_item(item) for item in items[:min(limit, 5)]]
                for layer_name, items in results.items()
            }
            results["debug"] = debug_info
        return results
    
    def _retrieve_l1(self, query: str, topic: Optional[str], limit: int) -> List[Dict]:
        """检索 L1 层"""
        results = []
        
        # 从 topics 目录检索
        topics_dir = self.base_path / "L1-Overview" / "topics"
        if topics_dir.exists():
            if topic:
                files = [topics_dir / f"{topic}.md"]
            else:
                files = list(topics_dir.glob("*.md"))
            
            for file in files:
                if not file.exists():
                    continue
                
                content = file.read_text(encoding='utf-8')
                entries = self._parse_l1_file(content, file.stem)
                if not query:
                    results.extend(entries)
                    continue
                haystacks = [
                    "\n".join(
                        [
                            str(entry.get("title", "")),
                            str(entry.get("summary", "")),
                            str(entry.get("content", "")),
                            str(entry.get("topic", "")),
                            str(entry.get("source_l2", "")),
                        ]
                    )
                    for entry in entries
                ]
                matches = match_query_corpus(query, haystacks)
                for entry, match in zip(entries, matches):
                    if not match["matched"]:
                        continue
                    entry["_match_score"] = match["score"]
                    entry["_bm25_score"] = match["bm25_score"]
                    entry["_debug_match"] = match
                    results.append(entry)
        
        # 从 sessions 目录检索（向后兼容）
        sessions_dir = self.base_path / "L1-Overview" / "sessions"
        if sessions_dir.exists():
            for file in sessions_dir.glob("*.md"):
                content = file.read_text(encoding='utf-8')
                if not query or query.lower() in content.lower():
                    results.append({
                        "type": "session",
                        "id": file.stem,
                        "content": content[:500]
                    })
        
        # 按时间排序并限制数量
        results.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        return results[:limit]

    def _retrieve_l1_by_sources(self, topic: Optional[str], source_ids: Set[str], vector_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        if not source_ids:
            return []
        entries = self._retrieve_l1(query="", topic=topic, limit=10000)
        return [
            {**entry, "_vector_score": float(vector_scores.get(entry.get("source_l2"), 0.0))}
            for entry in entries
            if entry.get("source_l2") in source_ids
        ]

    def _retrieve_l0_by_sources(self, topic: Optional[str], source_ids: Set[str], vector_scores: Dict[str, float]) -> List[Dict[str, Any]]:
        if not source_ids:
            return []
        entries = self.l0.retrieve(query="", topic=topic, limit=10000)
        return [
            {**entry, "_vector_score": float(vector_scores.get(entry.get("source_l2"), 0.0))}
            for entry in entries
            if entry.get("source_l2") in source_ids
        ]
    
    def _parse_l1_file(self, content: str, topic: str) -> List[Dict]:
        """解析 L1 topic 文件"""
        entries = []
        
        # 按 ### 分割条目
        sections = content.split('###')[1:]  # 跳过标题
        
        for section in sections:
            lines = section.strip().split('\n')
            if not lines:
                continue
            
            title = lines[0].strip()
            
            # 提取时间
            timestamp = ""
            for line in lines:
                if '**时间**:' in line:
                    timestamp = line.split(':', 1)[1].strip()
                    break
            
            # 提取摘要
            summary = ""
            for line in lines:
                if '**摘要**:' in line:
                    summary = line.split(':', 1)[1].strip()
                    break

            source_l2 = None
            for line in lines:
                if '**来源**:' in line:
                    match = re.search(r'\[([^\]]+)\]', line)
                    if match:
                        source_l2 = match.group(1)
                    else:
                        source_l2 = line.split(':', 1)[1].strip()
                    break
            
            entries.append({
                "type": "topic",
                "topic": topic,
                "title": title,
                "timestamp": timestamp,
                "summary": summary,
                "content": section[:1000],
                "source_l2": source_l2,
            })
        
        return entries
    
    def progressive_retrieve(self,
                            query: str,
                            limit_per_layer: int = 5) -> Dict[str, List[Dict]]:
        """渐进式检索 - 先 L0，再 L1，最后 L2"""
        return self.retrieve(query=query, layer="all", limit=limit_per_layer)
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """获取各层统计"""
        # L0 统计
        l0_stats = self.l0.get_stats()
        
        # L1 统计（包含新的 topics）
        l1_stats = self.l1.get_stats()
        topics_dir = self.base_path / "L1-Overview" / "topics"
        if topics_dir.exists():
            l1_stats['topics_files'] = len(list(topics_dir.glob("*.md")))
            l1_stats['total_topic_entries'] = sum(
                len(self._parse_l1_file(f.read_text(encoding='utf-8'), f.stem))
                for f in topics_dir.glob("*.md")
            )
        
        # L2 统计
        l2_stats = self.l2.get_stats()
        vector_stats = self.vector_store.get_stats() if self._vector_store_can_query() and hasattr(self.vector_store, "get_stats") else {"enabled": False}
        if not vector_stats.get("enabled", False):
            vector_stats["reason"] = self._vector_store_unavailable_reason()
        
        return {
            'L0': l0_stats,
            'L1': l1_stats,
            'L2': l2_stats,
            'vector_store': vector_stats,
            'lifecycle': self.lifecycle.get_stats(),
        }

    def forget(self, memory_id: str, force: bool = False) -> Dict[str, Any]:
        result = self.lifecycle.forget(memory_id=memory_id, force=force)
        if not result.get("success"):
            return result
        if force:
            removed = self.l2.delete_entry(memory_id)
            vector_removed = self.vector_store.delete(memory_id) if self.vector_store is not None else False
            self.lifecycle.delete_manifest_entry(memory_id)
            return {
                **result,
                "removed_from_l2": removed,
                "removed_from_vector_store": vector_removed,
                "aggregate_rebuild": self.rebuild_aggregates(),
            }
        return {**result, "aggregate_rebuild": self.rebuild_aggregates()}

    def restore(self, memory_id: str) -> Dict[str, Any]:
        result = self.lifecycle.restore(memory_id)
        if not result.get("success"):
            return result
        return {**result, "aggregate_rebuild": self.rebuild_aggregates()}

    def cleanup(self, dry_run: bool = False, scope: Optional[str] = None) -> Dict[str, Any]:
        return self.lifecycle.cleanup_events(dry_run=dry_run, scope=scope)

    def set_pinned(self, memory_id: str, pinned: bool) -> Dict[str, Any]:
        return self.lifecycle.set_pinned(memory_id=memory_id, pinned=pinned)

    def set_importance(self, memory_id: str, importance: str) -> Dict[str, Any]:
        return self.lifecycle.set_importance(memory_id=memory_id, importance=importance)

    def feedback(
        self,
        label: str,
        memory_id: Optional[str] = None,
        topic: Optional[str] = None,
        query: Optional[str] = None,
        note: str = "",
    ) -> Dict[str, Any]:
        result = self.lifecycle.record_feedback(
            label=label,
            memory_id=memory_id,
            topic=topic,
            query=query,
            note=note,
        )
        if not result.get("success"):
            return result
        memory = self.lifecycle.get_memory(memory_id) if memory_id else None
        title = memory.get("title") if memory else (query or result.get("scope"))
        context = "\n".join(
            [
                f"memory_id={memory_id or 'N/A'}",
                f"scope={result.get('scope', 'unknown')}",
                f"query={query or ''}",
                f"note={note}",
            ]
        )
        tags = [label, result.get("scope", "unknown").replace(":", "-")]
        if label == "useful":
            governance_log_id = self.learnings.record(
                content=f"记忆反馈 useful: {title}",
                category="insight",
                context=context,
                tags=tags,
            )
        else:
            governance_log_id = self.errors.record(
                error_description=f"记忆反馈 {label}: {title}",
                severity="high" if label == "wrong" else "medium",
                context=context,
                error_message=note or query or "",
                tags=tags,
            )
        return {**result, "governance_log_id": governance_log_id}

    def rebuild_aggregates(self, include_archived: bool = False) -> Dict[str, Any]:
        entries = [
            entry
            for entry in self.l2.iter_entries()
            if self.lifecycle.is_visible(entry.get("id"), include_archived=include_archived)
        ]
        result = self.trigger.rebuild_from_entries(entries)
        self.lifecycle.mark_rebuild()
        return {**result, "source_entries": len(entries), "include_archived": include_archived}

    def _sort_by_lifecycle(self, items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
        ranked = sorted(
            items,
            key=lambda item: (
                item.get("_hybrid_score", 0.0),
                item.get("_vector_score", 0.0),
                item.get("_bm25_score", 0.0),
                item.get("_match_score", 0.0),
                self.lifecycle.rank_bonus(
                    item.get("source_l2") or item.get("id"),
                    scope=item.get("scope") or (f"topic:{item.get('topic')}" if item.get("topic") else None),
                ),
                item.get("timestamp", ""),
            ),
            reverse=True,
        )
        return ranked[:limit]

    def _vector_retrieve_l2(
        self,
        query: str,
        topic: Optional[str],
        limit: int,
        min_similarity: float,
        debug_info: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if not query:
            if debug_info is not None:
                debug_info["vector"] = {
                    "enabled": self._vector_store_can_query(),
                    "reason": "empty_query",
                    "requested_limit": limit,
                    "raw_hits": 0,
                    "returned_hits": 0,
                    "min_similarity": min_similarity,
                    "filtered_out": [],
                    "top_hits": [],
                }
            return []
        if not self._vector_store_can_query():
            if debug_info is not None:
                debug_info["vector"] = {
                    "enabled": False,
                    "reason": self._vector_store_unavailable_reason(),
                    "requested_limit": limit,
                    "raw_hits": 0,
                    "returned_hits": 0,
                    "min_similarity": min_similarity,
                    "filtered_out": [],
                    "top_hits": [],
                }
            return []
        try:
            raw_results = self.vector_store.search(query=query, top_k=max(limit, 10), layer="L2")
        except Exception as e:
            print(f"⚠️ Vector search failed: {e}")
            if debug_info is not None:
                debug_info["vector"] = {
                    "enabled": False,
                    "reason": str(e),
                    "requested_limit": limit,
                    "raw_hits": 0,
                    "returned_hits": 0,
                    "min_similarity": min_similarity,
                    "filtered_out": [],
                    "top_hits": [],
                }
            return []
        results: List[Dict[str, Any]] = []
        filtered_out: List[Dict[str, Any]] = []
        for item in raw_results:
            memory_id = item.get("id")
            if not memory_id:
                continue
            entry = self.l2.get_entry(memory_id)
            if not entry:
                continue
            if topic and entry.get("topic") != topic:
                continue
            similarity = float(item.get("score", 0.0))
            if similarity < min_similarity:
                filtered_out.append(
                    {
                        "id": memory_id,
                        "score": similarity,
                        "title": entry.get("title"),
                    }
                )
                continue
            results.append({
                "type": entry.get("type"),
                "id": entry.get("id"),
                "title": entry.get("title"),
                "topic": entry.get("topic"),
                "scope": entry.get("scope"),
                "timestamp": entry.get("timestamp"),
                "content": entry.get("content", ""),
                "preview": entry.get("content", "")[:200],
                "_vector_score": similarity,
            })
        if debug_info is not None:
            debug_info["vector"] = {
                "enabled": True,
                "requested_limit": limit,
                "raw_hits": len(raw_results),
                "returned_hits": len(results),
                "min_similarity": min_similarity,
                "filtered_out": filtered_out[:10],
                "top_hits": [
                    {
                        "id": item.get("id"),
                        "title": item.get("title"),
                        "score": round(float(item.get("_vector_score", 0.0)), 4),
                    }
                    for item in results[:10]
                ],
            }
        return results

    def _merge_results(self, primary: List[Dict[str, Any]], secondary: List[Dict[str, Any]], key_field: str) -> List[Dict[str, Any]]:
        merged: Dict[str, Dict[str, Any]] = {}
        ordered: List[Dict[str, Any]] = []
        for item in primary + secondary:
            key = item.get(key_field)
            if not key:
                ordered.append(item)
                continue
            existing = merged.get(key)
            if existing is None:
                merged[key] = dict(item)
                continue
            existing_match_score = float(existing.get("_match_score", 0.0))
            incoming_match_score = float(item.get("_match_score", 0.0))
            self._merge_score_field(existing, item, "_match_score")
            self._merge_score_field(existing, item, "_vector_score")
            self._merge_score_field(existing, item, "_bm25_score")
            if incoming_match_score > existing_match_score and item.get("_debug_match"):
                existing["_debug_match"] = item.get("_debug_match")
            for field, value in item.items():
                if existing.get(field) in (None, "", []):
                    existing[field] = value
        for item in merged.values():
            item.pop("_score_counts", None)
            ordered.append(item)
        return ordered

    def _vector_store_can_query(self) -> bool:
        return self.vector_store is not None and callable(getattr(self.vector_store, "search", None))

    def _vector_store_can_add(self) -> bool:
        return self.vector_store is not None and callable(getattr(self.vector_store, "add", None))

    def _vector_store_unavailable_reason(self) -> str:
        if self._vector_store_error:
            return self._vector_store_error
        if self.vector_store is None:
            return "vector store unavailable"
        if not callable(getattr(self.vector_store, "search", None)):
            return "vector search interface unavailable"
        return ""

    def _merge_score_field(self, existing: Dict[str, Any], item: Dict[str, Any], field: str) -> None:
        score_counts = existing.setdefault("_score_counts", {})
        existing_score = float(existing.get(field, 0.0))
        incoming_score = float(item.get(field, 0.0))
        existing_count = int(score_counts.get(field, 1 if existing_score > 0 else 0))
        incoming_count = 1 if incoming_score > 0 else 0
        if incoming_count == 0:
            return
        total_count = existing_count + incoming_count
        if existing_count == 0:
            existing[field] = incoming_score
        else:
            existing[field] = ((existing_score * existing_count) + incoming_score) / total_count
        score_counts[field] = total_count

    def _get_hybrid_options(
        self,
        min_similarity: Optional[float],
        vector_weight: Optional[float],
        bm25_weight: Optional[float],
    ) -> Dict[str, float]:
        hybrid_config = self.config.get("retrieval", {}).get("hybrid", {})
        resolved_min_similarity = float(
            min_similarity
            if min_similarity is not None
            else hybrid_config.get("min_similarity", 0.35)
        )
        raw_vector_weight = float(
            vector_weight
            if vector_weight is not None
            else hybrid_config.get("vector_weight", 0.7)
        )
        raw_bm25_weight = float(
            bm25_weight
            if bm25_weight is not None
            else hybrid_config.get("bm25_weight", 0.3)
        )
        total_weight = raw_vector_weight + raw_bm25_weight
        if total_weight <= 0:
            raw_vector_weight = 0.7
            raw_bm25_weight = 0.3
            total_weight = 1.0
        return {
            "min_similarity": max(0.0, min(1.0, resolved_min_similarity)),
            "vector_weight": raw_vector_weight / total_weight,
            "bm25_weight": raw_bm25_weight / total_weight,
        }

    def _apply_hybrid_scores(self, items: List[Dict[str, Any]], vector_weight: float, bm25_weight: float) -> None:
        for item in items:
            vector_score = float(item.get("_vector_score", 0.0))
            bm25_score = float(item.get("_bm25_score", 0.0))
            hybrid_score = vector_weight * vector_score + bm25_weight * bm25_score
            item["_hybrid_score"] = hybrid_score
            lifecycle_bonus = self.lifecycle.rank_bonus(
                item.get("source_l2") or item.get("id"),
                scope=item.get("scope") or (f"topic:{item.get('topic')}" if item.get("topic") else None),
            )
            item["_lifecycle_score"] = lifecycle_bonus
            match_debug = item.get("_debug_match") or {}
            reasons: List[str] = []
            if vector_score > 0:
                reasons.append(f"vector={vector_score:.4f}")
            if bm25_score > 0:
                reasons.append(f"bm25={bm25_score:.4f}")
            if match_debug.get("matched_terms"):
                reasons.append(
                    f"terms={len(match_debug.get('matched_terms', []))}/{match_debug.get('total_terms', 0)}"
                )
            reasons.append(f"lifecycle={lifecycle_bonus:.4f}")
            item["_debug_explain"] = {
                "hybrid_score": round(hybrid_score, 4),
                "vector_score": round(vector_score, 4),
                "bm25_score": round(bm25_score, 4),
                "match_score": round(float(item.get("_match_score", 0.0)), 4),
                "lifecycle_score": round(lifecycle_bonus, 4),
                "reasons": reasons,
                "matched_terms": match_debug.get("matched_terms", []),
                "coverage": round(float(match_debug.get("coverage", 0.0)), 4),
                "exact_match": bool(match_debug.get("exact_match", False)),
            }

    def _build_layer_debug(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {
            "candidate_count": len(items),
            "top_candidates": [self._compact_debug_item(item) for item in self._sort_by_lifecycle(items, min(5, len(items) or 1))]
            if items else [],
        }

    def _compact_debug_item(self, item: Dict[str, Any]) -> Dict[str, Any]:
        explanation = item.get("_debug_explain", {})
        return {
            "id": item.get("source_l2") or item.get("id"),
            "title": item.get("title"),
            "topic": item.get("topic"),
            "hybrid_score": explanation.get("hybrid_score", round(float(item.get("_hybrid_score", 0.0)), 4)),
            "vector_score": explanation.get("vector_score", round(float(item.get("_vector_score", 0.0)), 4)),
            "bm25_score": explanation.get("bm25_score", round(float(item.get("_bm25_score", 0.0)), 4)),
            "match_score": explanation.get("match_score", round(float(item.get("_match_score", 0.0)), 4)),
            "lifecycle_score": explanation.get("lifecycle_score", round(float(item.get("_lifecycle_score", 0.0)), 4)),
            "matched_terms": explanation.get("matched_terms", []),
            "reasons": explanation.get("reasons", []),
        }
    
    def sync_layers(self, full_sync: bool = False):
        """
        同步各层数据
        
        Args:
            full_sync: 是否全量重新生成
        """
        if full_sync:
            return self.rebuild_aggregates(include_archived=False)
        else:
            print("🔄 增量同步模式...")
            return {"success": False, "message": "增量同步暂未实现"}
