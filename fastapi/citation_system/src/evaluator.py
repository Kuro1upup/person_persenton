"""评测指标"""
import logging
import json
from typing import List, Dict, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)

class CitationEvaluator:
    """引用评测器"""
    
    @staticmethod
    def evaluate_retrieval(
        retrieved_docs: List[str],
        relevant_docs: List[str]
    ) -> Dict:
        """
        评测检索性能
        
        Args:
            retrieved_docs: 检索到的文档 ID
            relevant_docs: 相关的文档 ID（金标准）
        
        Returns:
            评测指标
        """
        retrieved_set = set(retrieved_docs)
        relevant_set = set(relevant_docs)
        
        # 计算指标
        tp = len(retrieved_set & relevant_set)  # 真正例
        fp = len(retrieved_set - relevant_set)  # 假正例
        fn = len(relevant_set - retrieved_set)  # 假负例
        
        precision = tp / len(retrieved_set) if retrieved_set else 0
        recall = tp / len(relevant_set) if relevant_set else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1,
            "tp": tp,
            "fp": fp,
            "fn": fn
        }
    
    @staticmethod
    def evaluate_ranking(
        ranked_docs: List[str],
        relevant_docs: List[str],
        k_values: List[int] = [1, 5, 10]
    ) -> Dict:
        """
        评测排序性能
        
        Args:
            ranked_docs: 排序后的文档 ID
            relevant_docs: 相关文档 ID
            k_values: 评测 Top-K 值
        
        Returns:
            排序指标
        """
        relevant_set = set(relevant_docs)
        metrics = {}
        
        # Recall@K
        for k in k_values:
            top_k = set(ranked_docs[:k])
            recall_k = len(top_k & relevant_set) / len(relevant_set) if relevant_set else 0
            metrics[f"recall@{k}"] = recall_k
        
        # MRR (Mean Reciprocal Rank)
        mrr = 0
        for i, doc in enumerate(ranked_docs, 1):
            if doc in relevant_set:
                mrr = 1 / i
                break
        metrics["mrr"] = mrr
        
        # NDCG (Normalized Discounted Cumulative Gain)
        dcg = 0
        idcg = 0
        for i, doc in enumerate(ranked_docs, 1):
            if doc in relevant_set:
                dcg += 1 / (i + 1)  # log2(i+1)
        
        for i in range(min(len(relevant_set), len(ranked_docs))):
            idcg += 1 / (i + 2)
        
        ndcg = dcg / idcg if idcg > 0 else 0
        metrics["ndcg"] = ndcg
        
        return metrics
    
    @staticmethod
    def evaluate_citation_quality(
        citation,
        relevant_documents: List[Dict]
    ) -> Dict:
        """
        评测引用质量
        
        Args:
            citation: 引用对象
            relevant_documents: 相关文档列表
        
        Returns:
            质量指标
        """
        # 检查引用的文档是否相关
        is_relevant = citation.document_id in [d.get("id") for d in relevant_documents]
        
        # 检查匹配率
        match_rate = citation.match_rate
        
        # 综合评分
        quality_score = 0
        if is_relevant:
            quality_score += 0.5
        
        if match_rate >= 0.8:
            quality_score += 0.3
        elif match_rate >= 0.5:
            quality_score += 0.2
        elif match_rate >= 0.2:
            quality_score += 0.1
        
        # 引用覆盖度
        coverage = len(citation.matches) / len(citation.query.split()) if citation.query else 0
        if coverage >= 0.8:
            quality_score += 0.2
        elif coverage >= 0.5:
            quality_score += 0.1
        
        return {
            "is_relevant": is_relevant,
            "match_rate": match_rate,
            "coverage": coverage,
            "quality_score": min(1.0, quality_score)
        }

class BenchmarkEvaluator:
    """基准评测"""
    
    @staticmethod
    def evaluate_dataset(
        eval_file: str,
        citation_generator,
        k: int = 3
    ) -> Dict:
        """
        评测整个数据集
        
        Args:
            eval_file: 评测数据集文件（JSONL）
            citation_generator: 引用生成器
            k: 每个查询的引用数量
        
        Returns:
            评测结果
        """
        logger.info(f"Evaluating dataset: {eval_file}")
        
        results = {
            "total": 0,
            "recall_at_1": [],
            "recall_at_5": [],
            "recall_at_10": [],
            "mrr": [],
            "ndcg": [],
            "quality_scores": []
        }
        
        with open(eval_file, 'r', encoding='utf-8') as f:
            for line in f:
                if not line.strip():
                    continue
                
                item = json.loads(line)
                query = item.get("query")
                relevant_docs = item.get("relevant_docs", [])
                
                if not query or not relevant_docs:
                    continue
                
                # 生成引用
                citations = citation_generator.generate_citations(query, k=k)
                retrieved_docs = [c.document_id for c in citations]
                
                # 评测
                ranking_metrics = CitationEvaluator.evaluate_ranking(
                    retrieved_docs, relevant_docs
                )
                
                results["recall_at_1"].append(ranking_metrics.get("recall@1", 0))
                results["recall_at_5"].append(ranking_metrics.get("recall@5", 0))
                results["recall_at_10"].append(ranking_metrics.get("recall@10", 0))
                results["mrr"].append(ranking_metrics.get("mrr", 0))
                results["ndcg"].append(ranking_metrics.get("ndcg", 0))
                
                # 引用质量
                for citation in citations:
                    quality = CitationEvaluator.evaluate_citation_quality(
                        citation, relevant_docs
                    )
                    results["quality_scores"].append(quality["quality_score"])
                
                results["total"] += 1
        
        # 计算平均值
        if results["total"] > 0:
            results["avg_recall_at_1"] = sum(results["recall_at_1"]) / results["total"]
            results["avg_recall_at_5"] = sum(results["recall_at_5"]) / results["total"]
            results["avg_recall_at_10"] = sum(results["recall_at_10"]) / results["total"]
            results["avg_mrr"] = sum(results["mrr"]) / results["total"]
            results["avg_ndcg"] = sum(results["ndcg"]) / results["total"]
            results["avg_quality"] = sum(results["quality_scores"]) / len(results["quality_scores"]) if results["quality_scores"] else 0
        
        logger.info("Evaluation completed: total_queries=%d, "
                    "avg_recall@1=%.4f, avg_recall@5=%.4f, avg_recall@10=%.4f, "
                    "avg_mrr=%.4f, avg_ndcg=%.4f, avg_quality=%.4f",
                    results['total'],
                    results.get('avg_recall_at_1', 0),
                    results.get('avg_recall_at_5', 0),
                    results.get('avg_recall_at_10', 0),
                    results.get('avg_mrr', 0),
                    results.get('avg_ndcg', 0),
                    results.get('avg_quality', 0))

        return results