"""
Hybrid Retrieval Fusion

混合检索融合器 - 结合向量搜索和BM25搜索结果
"""

import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FusionConfig:
    """融合配置"""
    vector_weight: float = 0.7
    bm25_weight: float = 0.3
    min_score: float = 0.35
    candidate_pool_size: int = 20
    normalize_scores: bool = True


class HybridFusion:
    """
    混合检索融合器
    
    将向量搜索和BM25搜索结果融合为统一的候选池
    
    融合策略:
    1. 归一化两种搜索的分数到统一空间
    2. 以Vector分数为基准
    3. BM25命中的文档获得加权boost
    4. 只返回超过min_score的结果
    """
    
    def __init__(self, config: Optional[FusionConfig] = None):
        self.config = config or FusionConfig()
    
    def fuse(self,
             vector_results: List[Dict[str, Any]],
             bm25_results: List[Dict[str, Any]],
             query: str = "") -> List[Dict[str, Any]]:
        """
        融合两种检索结果
        
        Args:
            vector_results: 向量搜索结果 [{id, content, score, ...}]
            bm25_results: BM25搜索结果 [{id, content, score, ...}]
            query: 原始查询（用于调试）
            
        Returns:
            融合后的结果列表，按综合分数排序
        """
        # 归一化分数
        if self.config.normalize_scores:
            vector_results = self._normalize_scores(vector_results)
            bm25_results = self._normalize_scores(bm25_results)
        
        # 构建候选池
        candidate_pool = {}
        
        # 添加向量结果
        for result in vector_results:
            doc_id = result['id']
            candidate_pool[doc_id] = {
                'vector_score': result.get('score', 0),
                'bm25_score': 0,
                'result': result
            }
        
        # 添加BM25结果，合并已有候选
        for result in bm25_results:
            doc_id = result['id']
            if doc_id in candidate_pool:
                candidate_pool[doc_id]['bm25_score'] = result.get('score', 0)
            else:
                candidate_pool[doc_id] = {
                    'vector_score': 0,
                    'bm25_score': result.get('score', 0),
                    'result': result
                }
        
        # 计算融合分数
        fused_results = []
        for doc_id, data in candidate_pool.items():
            vector_score = data['vector_score']
            bm25_score = data['bm25_score']
            
            # 融合公式
            if vector_score > 0 and bm25_score > 0:
                # 两种搜索都命中 - 使用加权融合
                fused_score = (
                    self.config.vector_weight * vector_score +
                    self.config.bm25_weight * bm25_score
                )
                # 双命中boost
                fused_score = min(1.0, fused_score * 1.05)
            elif vector_score > 0:
                # 只有向量命中
                fused_score = vector_score
            else:
                # 只有BM25命中
                fused_score = bm25_score * 0.9  # 轻微降权
            
            # 过滤低分结果
            if fused_score < self.config.min_score:
                continue
            
            result = dict(data['result'])
            result['score'] = round(fused_score, 4)
            result['vector_score'] = round(vector_score, 4)
            result['bm25_score'] = round(bm25_score, 4)
            
            fused_results.append(result)
        
        # 按融合分数排序
        fused_results.sort(key=lambda x: x['score'], reverse=True)
        
        return fused_results[:self.config.candidate_pool_size]
    
    def _normalize_scores(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        归一化分数到0-1空间
        
        使用min-max归一化
        """
        if not results:
            return results
        
        scores = [r.get('score', 0) for r in results]
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            return results
        
        normalized = []
        for result in results:
            new_result = dict(result)
            raw_score = result.get('score', 0)
            new_result['score'] = (raw_score - min_score) / (max_score - min_score)
            normalized.append(new_result)
        
        return normalized
    
    def fuse_with_rrf(self,
                      vector_results: List[Dict[str, Any]],
                      bm25_results: List[Dict[str, Any]],
                      k: int = 60) -> List[Dict[str, Any]]:
        """
        使用RRF (Reciprocal Rank Fusion)融合
        
        RRF公式: score = Σ 1/(k + rank)
        
        Args:
            vector_results: 向量搜索结果
            bm25_results: BM25搜索结果
            k: RRF常数（通常60）
            
        Returns:
            融合结果
        """
        # 构建rank字典
        vector_ranks = {r['id']: i + 1 for i, r in enumerate(vector_results)}
        bm25_ranks = {r['id']: i + 1 for i, r in enumerate(bm25_results)}
        
        # 收集所有文档ID
        all_ids = set(vector_ranks.keys()) | set(bm25_ranks.keys())
        
        # 计算RRF分数
        rrf_scores = {}
        for doc_id in all_ids:
            score = 0
            result_data = None
            
            if doc_id in vector_ranks:
                score += 1.0 / (k + vector_ranks[doc_id])
                result_data = next(r for r in vector_results if r['id'] == doc_id)
            
            if doc_id in bm25_ranks:
                score += 1.0 / (k + bm25_ranks[doc_id])
                if result_data is None:
                    result_data = next(r for r in bm25_results if r['id'] == doc_id)
            
            rrf_scores[doc_id] = {
                'score': score,
                'result': result_data
            }
        
        # 排序并返回
        sorted_results = sorted(rrf_scores.items(), key=lambda x: x[1]['score'], reverse=True)
        
        final_results = []
        for doc_id, data in sorted_results[:self.config.candidate_pool_size]:
            result = dict(data['result'])
            result['score'] = round(data['score'], 4)
            result['rrf_score'] = True
            final_results.append(result)
        
        return final_results
