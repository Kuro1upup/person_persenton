"""ColBERT 检索与排序"""
import logging
from typing import List, Dict, Tuple
import torch
import numpy as np

from colbert.infra import ColBERTConfig, Run, RunConfig
from colbert.modeling.checkpoint import Checkpoint

from config import (
    COLBERT_MODEL, INDEX_DIR, RETRIEVAL_K, RERANK_K
)
from src.indexer import ColBERTIndexer

logger = logging.getLogger(__name__)

class ColBERTRetriever:
    """ColBERT 检索器"""
    
    def __init__(self):
        """初始化检索器"""
        logger.info("Initializing ColBERT retriever...")

        # Create config and set both checkpoint and model_name
        from colbert.infra.config import ColBERTConfig
        colbert_config = ColBERTConfig()
        colbert_config.configure(checkpoint=COLBERT_MODEL, model_name=COLBERT_MODEL)
        self.checkpoint = Checkpoint(COLBERT_MODEL, colbert_config=colbert_config)
        self.indexer = ColBERTIndexer()

        # 加载索引
        try:
            with Run().context(RunConfig(name="documents", root=str(INDEX_DIR))):
                self.index = self.indexer.load_index()
            logger.info("Index loaded successfully")
        except Exception as e:
            logger.error(f"Failed to load index: {e}")
            raise

        # 加载文档元数据映射和 ID 映射
        try:
            self.document_metadata, self.reverse_id_mapping = self._load_document_metadata()
            logger.info(f"Loaded metadata for {len(self.document_metadata)} documents")
        except Exception as e:
            logger.warning(f"Failed to load document metadata: {e}")
            self.document_metadata = {}
            self.reverse_id_mapping = {}

        logger.info("ColBERT retriever initialized")

    def _load_document_metadata(self) -> tuple[Dict[str, Dict], Dict[str, str]]:
        """加载文档元数据映射和 ID 映射

        Returns:
            tuple: (metadata, reverse_id_mapping) - 元数据和索引ID到原始ID的反向映射
        """
        # 动态导入配置
        try:
            from config import DATA_DIR
        except ImportError:
            import sys
            from pathlib import Path
            sys.path.insert(0, str(Path(__file__).parent.parent))
            from citation_system.config import DATA_DIR
        import json

        metadata = {}
        reverse_id_mapping = {}  # 索引ID -> 原始ID 的反向映射
        documents_file = DATA_DIR / "documents.jsonl"

        if documents_file.exists():
            try:
                with open(documents_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if line.strip():
                            doc = json.loads(line)
                            # 使用文档ID（现在是整数）作为键
                            doc_id = str(doc.get("id", ""))  # 转换为字符串以保持一致性
                            original_id = doc.get("original_id", doc.get("id", ""))
                            index_id = doc.get("index_id", "")

                            if doc_id:
                                metadata[doc_id] = {
                                    "title": doc.get("title", ""),
                                    "url": doc.get("url", ""),  # 添加 URL 支持
                                    "text": doc.get("text", ""),
                                    "original_id": str(original_id),  # 保存原始 ID
                                    "index_id": index_id or ""  # 保存UUID索引ID
                                }
                                # 如果有UUID索引ID，建立反向映射
                                if index_id and index_id != str(original_id):
                                    reverse_id_mapping[index_id] = str(original_id)

                logger.info(f"Loaded metadata for {len(metadata)} documents")
                if reverse_id_mapping:
                    logger.info(f"Loaded ID mapping for {len(reverse_id_mapping)} documents")
            except Exception as e:
                logger.warning(f"Failed to load document metadata: {e}")
        else:
            logger.warning(f"Documents file not found: {documents_file}")

        return metadata, reverse_id_mapping

    def retrieve(self, query: str, k: int = RETRIEVAL_K) -> List[Dict]:
        """
        检索文档

        Args:
            query: 查询语句
            k: 返回结果数量

        Returns:
            检索结果列表 [{"doc_id": str, "score": float, "text": str}, ...]
        """
        logger.debug(f"Retrieving for query: {query}")

        # Check if we have a dummy index (index_scorer is None)
        if self.index is None:
            logger.warning("Dummy index detected - returning empty results")
            return []


        # 创建配置
        config = ColBERTConfig()
        config.configure(
            checkpoint=self.checkpoint.colbert_config.checkpoint,
            ncells=4  # Match the indexer configuration
        )

        # 编码查询
        try:
            query_encoded = self._encode_query(query)
            logger.debug(f"Query encoded successfully, shape: {query_encoded.shape if hasattr(query_encoded, 'shape') else 'unknown'}")
        except Exception as e:
            logger.error(f"Query encoding failed: {e}")
            raise

        # 搜索
        with Run().context(RunConfig(name="documents", root=str(INDEX_DIR))):
            try:
                results = self.index.retrieve(config, query_encoded)
                # Handle case where results is None
                if results is None:
                    logger.warning("ColBERT retrieval returned None. This may indicate indexing issues.")
                    results = []
                else:
                    logger.debug(f"ColBERT retrieval succeeded: found {len(results)} results")
            except Exception as e:
                logger.warning(f"ColBERT retrieval failed: {e}. This may indicate indexing issues.")
                logger.warning("Consider rebuilding the index or checking the documents.")
                # Don't use fallback - return empty results to indicate the problem
                results = []

        # 格式化结果
        formatted_results = []
        for doc_id, score, text in results:
            doc_id_str = str(doc_id)
            # 从元数据中获取信息
            metadata = self.document_metadata.get(doc_id_str, {})
            url = metadata.get("url", "")

            # 使用原始 ID（如果存在映射的话）
            original_id = self.reverse_id_mapping.get(doc_id_str, doc_id_str)

            formatted_results.append({
                "doc_id": original_id,  # 返回原始 ID
                "score": float(score),
                "text": text,
                "url": url,  # 添加 URL 信息
                "index_id": doc_id_str  # 保留索引 ID 以供内部使用
            })

        logger.debug(f"Retrieved {len(formatted_results)} documents")
        return formatted_results

    def _encode_query(self, query: str):
        """编码查询"""
        # Tokenize the query
        input_ids, attention_mask = self.checkpoint.query_tokenizer.tensorize([query])
        # Encode using checkpoint
        query_embedding = self.checkpoint.query(input_ids, attention_mask)
        # Keep the full 3D tensor: (1, 32, 128) as expected by ColBERT
        return query_embedding

    def retrieve_with_explanations(self, query: str, k: int = RERANK_K) -> List[Dict]:
        """
        检索并返回解释（Token 级匹配）
        
        Args:
            query: 查询语句
            k: 返回结果数量
        
        Returns:
            包含解释的检索结果
        """
        logger.debug(f"Retrieving with explanations for: {query}")
        
        # 获取基础检索结果
        results = self.retrieve(query, k=RETRIEVAL_K)
        
        # 获取详细的匹配信息
        detailed_results = []
        for result in results[:k]:
            explanation = self._get_match_explanation(query, result["text"])
            result["explanation"] = explanation
            detailed_results.append(result)
        
        return detailed_results
    
    def _get_match_explanation(self, query: str, document: str) -> Dict:
        """
        生成匹配解释（Token 级）
        
        Args:
            query: 查询语句
            document: 文档文本
        
        Returns:
            匹配信息 {"query_tokens": [...], "matched_tokens": [...], "match_positions": [...]}
        """
        # 分词
        query_tokens = query.split()
        doc_tokens = document.split()
        
        # 找匹配的 token
        matched_tokens = []
        match_positions = []
        
        for q_token in query_tokens:
            for i, d_token in enumerate(doc_tokens):
                if q_token.lower() in d_token.lower():
                    matched_tokens.append(d_token)
                    match_positions.append(i)
                    break
        
        return {
            "query_tokens": query_tokens,
            "matched_tokens": matched_tokens,
            "match_positions": match_positions,
            "match_rate": len(matched_tokens) / max(1, len(query_tokens))
        }
    
    def rerank(self, query: str, candidates: List[Dict], k: int = RERANK_K) -> List[Dict]:
        """
        对候选文档重排
        
        Args:
            query: 查询语句
            candidates: 候选文档列表
            k: 返回结果数量
        
        Returns:
            重排后的结果
        """
        logger.debug(f"Reranking {len(candidates)} candidates")
        
        if not candidates:
            return []
        
        # 计算相关性分数（这里简化，实际应使用 ColBERT 的评分）
        reranked = sorted(candidates, key=lambda x: x["score"], reverse=True)
        
        return reranked[:k]

class DenseRetrieverComparison:
    """与其他密集检索器对比"""
    
    @staticmethod
    def compare_retrieval_methods(query: str, documents: List[str]):
        """对比不同检索方法"""
        from colbert.infra import ColBERTConfig
        
        results = {
            "colbert": ColBERTRetriever().retrieve(query, k=10)
        }
        
        return results

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    retriever = ColBERTRetriever()
    
    # 测试查询
    query = "如何重置密码"
    results = retriever.retrieve_with_explanations(query, k=5)
    
    print(f"\n查询：{query}\n")
    for i, result in enumerate(results, 1):
        print(f"{i}. 文档 {result['doc_id']} (分数: {result['score']:.4f})")
        print(f"   文本：{result['text'][:100]}...")
        print(f"   解释：{result['explanation']}")
        print()
