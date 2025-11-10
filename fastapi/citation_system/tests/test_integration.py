"""集成测试"""
import pytest
import logging
import warnings
import json
from pathlib import Path
import tempfile
import sys

# 抑制 swig 相关的弃用警告
warnings.filterwarnings('ignore', message='builtin type SwigPyPacked has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type SwigPyObject has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type swigvarlink has no __module__ attribute', category=DeprecationWarning)
# 添加项目路径 - 添加包含 src 目录的父目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
logger = logging.getLogger(__name__)
from src.indexer import DocumentLoader
from src.highlighter import TokenHighlighter, ExplanationGenerator
from src.citation_generator import CitationFormatter
from src.evaluator import CitationEvaluator

logger = logging.getLogger(__name__)

class TestEndToEnd:
    """端到端集成测试"""
    
    @pytest.fixture
    def sample_data(self):
        """示例数据"""
        return {
            "documents": [
                {
                    "id": "1",
                    "title": "密码重置指南",
                    "text": "如何重置密码：1. 访问登录页面 2. 点击忘记密码 3. 输入邮箱 4. 检查邮件中的链接 5. 设置新密码"
                },
                {
                    "id": "2",
                    "title": "账户安全",
                    "text": "账户安全很重要。定期更改密码可以保护您的账户。使用强密码和双因素认证。"
                }
            ],
            "queries": [
                {
                    "query": "如何重置密码",
                    "relevant_docs": ["1"]
                },
                {
                    "query": "密码安全",
                    "relevant_docs": ["1", "2"]
                }
            ]
        }
    
    def test_highlight_and_format(self, sample_data):
        """测试高亮和格式化"""
        doc = sample_data["documents"][0]
        query = sample_data["queries"][0]["query"]
        
        # 高亮
        highlight_info = TokenHighlighter.highlight_matches(query, doc["text"])
        assert highlight_info is not None
        assert "highlighted" in highlight_info
        
        # 生成解释
        explanation = ExplanationGenerator.generate_explanation(
            query, doc["text"], 0.95
        )
        assert explanation is not None
        assert "summary" in explanation
    
    def test_evaluation(self, sample_data):
        """测试评测"""
        retrieved_docs = ["1", "2"]
        relevant_docs = ["1"]
        
        metrics = CitationEvaluator.evaluate_retrieval(retrieved_docs, relevant_docs)
        
        assert "precision" in metrics
        assert "recall" in metrics
        assert "f1" in metrics
        assert metrics["precision"] == 0.5  # 1/2
        assert metrics["recall"] == 1.0     # 1/1
    
    def test_ranking_evaluation(self, sample_data):
        """测试排序评测"""
        ranked_docs = ["1", "2", "3"]
        relevant_docs = ["1", "3"]
        
        metrics = CitationEvaluator.evaluate_ranking(ranked_docs, relevant_docs)
        
        assert "recall@1" in metrics
        assert "recall@5" in metrics
        assert "mrr" in metrics
        assert "ndcg" in metrics
