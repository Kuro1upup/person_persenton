"""检索测试"""
import pytest
import logging
import warnings
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# 抑制 swig 相关的弃用警告
warnings.filterwarnings('ignore', message='builtin type SwigPyPacked has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type SwigPyObject has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type swigvarlink has no __module__ attribute', category=DeprecationWarning)
# 添加项目路径 - 添加包含 src 目录的父目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
logger = logging.getLogger(__name__)
from src.retriever import ColBERTRetriever
from src.highlighter import TokenHighlighter, ExplanationGenerator

logger = logging.getLogger(__name__)

class TestTokenHighlighter:
    """Token 高亮测试"""
    
    def test_highlight_exact_match(self):
        """测试精确匹配高亮"""
        query = "重置密码"
        document = "如何重置密码的步骤"
        
        result = TokenHighlighter.highlight_matches(query, document)
        
        assert result is not None
        assert "highlighted" in result
        assert len(result["matches"]) > 0
    
    def test_highlight_partial_match(self):
        """测试部分匹配高亮"""
        query = "密码"
        document = "密码重置指南"
        
        result = TokenHighlighter.highlight_matches(query, document)
        
        assert len(result["matches"]) > 0
        assert result["match_rate"] > 0
    
    def test_highlight_no_match(self):
        """测试无匹配"""
        query = "xyz"
        document = "这是一个完全无关的文档"
        
        result = TokenHighlighter.highlight_matches(query, document)
        
        assert len(result["matches"]) == 0 or result["match_rate"] == 0
    
    def test_context_windows(self):
        """测试上下文窗口"""
        query = "重置"
        document = "如何 重置 密码 的 步骤 是 什么"
        
        windows = TokenHighlighter.get_context_windows(query, document, window_size=2)
        
        assert len(windows) > 0
        assert all("highlighted" in w for w in windows)

class TestExplanationGenerator:
    """解释生成器测试"""
    
    def test_generate_explanation(self):
        """测试生成解释"""
        query = "重置密码"
        document = "如何重置密码：访问登录页面，点击忘记密码。"
        score = 0.95
        
        explanation = ExplanationGenerator.generate_explanation(query, document, score)
        
        assert explanation is not None
        assert "summary" in explanation
        assert "matches" in explanation
        assert "match_statistics" in explanation
    
    def test_explanation_summary_high_match(self):
        """测试高匹配率摘要"""
        query = "重置密码"
        document = "重置密码的步骤"
        
        explanation = ExplanationGenerator.generate_explanation(query, document, 0.95)
        summary = explanation["summary"]
        
        assert "匹配" in summary or "非常" in summary

class TestColBERTRetriever:
    """检索器测试"""
    
    @pytest.fixture
    def mock_retriever(self):
        """模拟检索器"""
        with patch('src.retriever.ColBERTIndexer'):
            with patch('src.retriever.Checkpoint') as mock_checkpoint:
                mock_checkpoint_instance = MagicMock()
                # 模拟tokenizer
                mock_tokenizer = MagicMock()
                mock_tokenizer.tensorize.return_value = ([1, 2, 3], [1, 1, 1])
                mock_checkpoint_instance.query_tokenizer = mock_tokenizer
                # 模拟query方法
                mock_checkpoint_instance.query.return_value = [[0.1, 0.2, 0.3]]
                # 模拟colbert_config
                mock_config = MagicMock()
                mock_config.checkpoint = "test_checkpoint"
                mock_checkpoint_instance.colbert_config = mock_config

                mock_checkpoint.return_value = mock_checkpoint_instance
                retriever = ColBERTRetriever()
                # 模拟索引
                retriever.index = MagicMock()
                return retriever
    
    def test_retriever_initialization(self, mock_retriever):
        """测试检索器初始化"""
        assert mock_retriever is not None
        assert mock_retriever.checkpoint is not None
    
    def test_retrieve_with_mock(self, mock_retriever):
        """测试检索（使用模拟）"""
        # 模拟搜索结果 - ColBERT返回(doc_id, score, text)元组列表
        mock_retriever.index.retrieve.return_value = [
            (1, 0.95, "密码重置指南"),
            (2, 0.85, "API 文档")
        ]
        
        results = mock_retriever.retrieve("重置密码", k=2)
        
        assert len(results) == 2
        assert results[0]["score"] == 0.95
        assert results[1]["doc_id"] == "2"
