"""索引构建测试"""
import pytest
import logging
import warnings
from pathlib import Path
import json
import tempfile
import shutil
import sys

# 抑制 swig 相关的弃用警告
warnings.filterwarnings('ignore', message='builtin type SwigPyPacked has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type SwigPyObject has no __module__ attribute', category=DeprecationWarning)
warnings.filterwarnings('ignore', message='builtin type swigvarlink has no __module__ attribute', category=DeprecationWarning)
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))
logger = logging.getLogger(__name__)
from src.indexer import ColBERTIndexer, DocumentLoader
from config import DATA_DIR, INDEX_DIR
# 添加项目路径 - 添加包含 src 目录的父目录


class TestDocumentLoader:
    """文档加载器测试"""
    
    def test_load_jsonl(self):
        """测试加载 JSONL"""
        # 创建临时文件
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as f:
            f.write(json.dumps({"id": "1", "title": "Test", "text": "Hello world"}) + '\n')
            f.write(json.dumps({"id": "2", "title": "Test2", "text": "Foo bar"}) + '\n')
            temp_file = f.name
        
        try:
            docs, _ = DocumentLoader.load_jsonl(temp_file)
            assert len(docs) == 2
            # 现在文档会有自动生成的唯一 ID
            assert "original_id" in docs[0]
            assert docs[0]["original_id"] == "1"  # 原始 ID
            assert docs[1]["text"] == "Foo bar"
        finally:
            Path(temp_file).unlink()
    
    def test_load_txt(self):
        """测试加载文本文件"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("第一句话。第二句话。第三句话。")
            temp_file = f.name
        
        try:
            docs = DocumentLoader.load_txt(temp_file)
            assert len(docs) > 0
            assert all("id" in doc and "text" in doc for doc in docs)
        finally:
            Path(temp_file).unlink()

class TestColBERTIndexer:
    """索引构建器测试"""
    
    @pytest.fixture
    def sample_documents(self):
        """示例文档"""
        return [
            {
                "id": "1",
                "title": "密码重置指南",
                "text": "如何重置密码：访问登录页面，点击忘记密码，输入邮箱，检查邮件中的链接。"
            },
            {
                "id": "2",
                "title": "API 文档",
                "text": "API 使用指南：基础 URL 是 https://api.example.com/v1，需要 Bearer Token 认证。"
            }
        ]
    
    def test_indexer_initialization(self):
        """测试索引器初始化"""
        indexer = ColBERTIndexer()
        assert indexer is not None
        assert indexer.checkpoint is not None
    
    def test_prepare_collection(self, sample_documents):
        """测试集合文件准备"""
        with tempfile.TemporaryDirectory() as temp_dir:
            output_file = Path(temp_dir) / "collection.tsv"
            indexer = ColBERTIndexer()
            indexer._prepare_collection(sample_documents, output_file)
            
            assert output_file.exists()
            
            # 验证文件内容
            with open(output_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            
            assert len(lines) == len(sample_documents)
            assert "密码重置指南" in lines[0]

class TestIndexBuild:
    """索引构建集成测试"""
    
    @pytest.mark.slow
    def test_build_and_load_index(self):
        """测试构建和加载索引"""
        # 这是一个慢速测试，需要实际的 ColBERT 模型
        # 可以跳过或使用 mock
        
        sample_docs = [
            {
                "id": "1",
                "title": "Test Doc",
                "text": "This is a test document for indexing."
            }
        ]
        
        indexer = ColBERTIndexer()
        
        # 注意：实际的索引构建需要 GPU 和大量时间
        # 这里只是验证接口
        assert indexer.checkpoint is not None
