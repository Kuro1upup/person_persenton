"""引用生成测试"""
import sys
import warnings
from pathlib import Path

# 抑制 swig 相关的弃用警告
warnings.filterwarnings('ignore', message='builtin type SwigPyPacked has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type SwigPyObject has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type swigvarlink has no __module__ attribute', category=DeprecationWarning)

# 添加项目路径 - 添加包含 src 目录的父目录
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import pytest
import logging
import json
from unittest.mock import Mock, patch, MagicMock

from src.citation_generator import (
    Citation, CitationGenerator, CitationFormatter
)
from src.highlighter import TokenHighlighter

logger = logging.getLogger(__name__)
class TestCitation:
    """引用数据类测试"""
    
    def test_citation_creation(self):
        """测试引用创建"""
        citation = Citation(
            document_id="1",
            document_text="重置密码步骤",
            query="如何重置密码",
            score=0.95,
            highlighted_text="**重置**密码步骤",
            matches=[{"text": "重置", "position": 0, "score": 1.0}],
            match_rate=0.5,
            explanation="高度匹配",
            context_windows=[]
        )
        
        assert citation.document_id == "1"
        assert citation.score == 0.95
        assert citation.timestamp is not None
    
    def test_citation_to_dict(self):
        """测试引用转字典"""
        citation = Citation(
            document_id="1",
            document_text="test",
            query="test",
            score=0.9,
            highlighted_text="test",
            matches=[],
            match_rate=0.5,
            explanation="test",
            context_windows=[]
        )
        
        data = citation.to_dict()
        assert isinstance(data, dict)
        assert data["document_id"] == "1"
    
    def test_citation_to_json(self):
        """测试引用转 JSON"""
        citation = Citation(
            document_id="1",
            document_text="test",
            query="test",
            score=0.9,
            highlighted_text="test",
            matches=[],
            match_rate=0.5,
            explanation="test",
            context_windows=[]
        )
        
        json_str = citation.to_json()
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert data["document_id"] == "1"

class TestCitationFormatter:
    """引用格式化器测试"""
    
    @pytest.fixture
    def sample_citation(self):
        """示例引用"""
        return Citation(
            document_id="1",
            document_text="如何重置密码：访问登录页面，点击忘记密码。",
            query="重置密码",
            score=0.95,
            highlighted_text="如何**重置密码**：访问登录页面，点击忘记密码。",
            matches=[
                {"text": "重置", "position": 2, "score": 1.0},
                {"text": "密码", "position": 3, "score": 1.0}
            ],
            match_rate=0.7,
            explanation="高度匹配：文档中大部分查询 token 都被找到",
            context_windows=[
                {
                    "text": "如何 重置 密码",
                    "highlighted": "如何 **重置** 密码",
                    "position": 2,
                    "match_token": "重置",
                    "match_score": 1.0
                }
            ]
        )
    
    def test_format_as_markdown(self, sample_citation):
        """测试 Markdown 格式化"""
        md = CitationFormatter.format_as_markdown(sample_citation)
        
        assert isinstance(md, str)
        assert "文档 ID" in md or "文档" in md
        assert "相关性" in md or "分数" in md
    
    def test_format_as_html(self, sample_citation):
        """测试 HTML 格式化"""
        html = CitationFormatter.format_as_html(sample_citation)
        
        assert isinstance(html, str)
        assert "<div" in html
        assert "citation" in html
    
    def test_format_as_json(self, sample_citation):
        """测试 JSON 格式化"""
        json_str = CitationFormatter.format_as_json([sample_citation])
        
        assert isinstance(json_str, str)
        data = json.loads(json_str)
        assert isinstance(data, list)
        assert len(data) == 1

class TestCitationGenerator:
    """引用生成器测试"""
    
    @pytest.fixture
    def mock_generator(self):
        """模拟生成器"""
        with patch('src.citation_generator.ColBERTRetriever'):
            generator = CitationGenerator()
            # 模拟检索器
            generator.retriever = MagicMock()
            return generator
    
    def test_generator_initialization(self, mock_generator):
        """测试生成器初始化"""
        assert mock_generator is not None
        assert mock_generator.retriever is not None
    
    def test_generate_citations(self, mock_generator):
        """测试生成引用"""
        # 模拟检索结果
        mock_generator.retriever.retrieve_with_explanations.return_value = [
            {
                "doc_id": "1",
                "text": "如何重置密码：访问登录页面",
                "score": 0.95,
                "explanation": {"summary": "高度匹配"}
            }
        ]
        
        citations = mock_generator.generate_citations("重置密码", k=1)
        
        assert len(citations) > 0
        assert isinstance(citations[0], Citation)
