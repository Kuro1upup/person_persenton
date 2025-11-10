"""
完整的使用流程示例
"""
import re
import sys
from pathlib import Path
from typing import List, Dict

# 添加项目路径
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

# 动态导入以支持直接运行和模块导入
# 检查是否可以作为模块导入（有包上下文）
if __package__ and __name__ != '__main__':
    # 当作为模块导入时使用相对导入
    try:
        from .indexer import DocumentLoader, ColBERTIndexer
        from .citation_generator import CitationGenerator, CitationFormatter
        from .evaluator import CitationEvaluator
        from ..config import DATA_DIR
    except (ImportError, ValueError, SystemError):
        # 如果相对导入失败，回退到绝对导入
        sys.path.insert(0, str(Path(__file__).parent.parent))
        from citation_system.src.indexer import DocumentLoader, ColBERTIndexer
        from citation_system.src.citation_generator import CitationGenerator, CitationFormatter
        from citation_system.src.evaluator import CitationEvaluator
        from citation_system.config import DATA_DIR
else:
    # 当直接运行时使用绝对导入
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from citation_system.src.indexer import DocumentLoader, ColBERTIndexer
    from citation_system.src.citation_generator import CitationGenerator, CitationFormatter
    from citation_system.src.evaluator import CitationEvaluator
    from citation_system.config import DATA_DIR

def build_index(document_path: str):
    """Build index from documents

    Automatically generates unique IDs for indexing while preserving original IDs.

    Args:
        document_path: Path to JSONL file containing documents with format:
            {"id": str, "title": str, "text"/"content": str, "url": str}
            Supports both 'text' and 'content' fields for document content
    """
    loader = DocumentLoader()
    documents, id_mapping = loader.load_jsonl(document_path)

    indexer = ColBERTIndexer()
    indexer.build_index(documents, force_rebuild=False)

    # 保存 ID 映射关系
    if id_mapping:
        import json
        from pathlib import Path
        # 动态导入 DATA_DIR - 使用与文件顶部相同的逻辑
        if __package__ and __name__ != '__main__':
            try:
                from ..config import DATA_DIR
            except (ImportError, ValueError, SystemError):
                from citation_system.config import DATA_DIR
        else:
            from citation_system.config import DATA_DIR

        mapping_file = DATA_DIR / "id_mapping.json"
        try:
            with open(mapping_file, 'w', encoding='utf-8') as f:
                json.dump(id_mapping, f, ensure_ascii=False, indent=2)
            print(f"Saved ID mapping to {mapping_file}")
        except Exception as e:
            print(f"Warning: Failed to save ID mapping: {e}")

    return True

async def build_index_from_search_content(search_content: str):
    """Build index from JSON format string content

    Automatically generates unique IDs for indexing while preserving original IDs.

    Args:
        search_conten: JSON string containing documents with format:
            {"id": str, "title": str, "text"/"content": str, "url": str}
            Supports both 'text' and 'content' fields for document content
    """
    import json
    import tempfile
    import os

    try:
        # 解析 JSON 字符串
        # 如果是单个 JSON 对象，转换为列表
        try:
            data = json.loads(preprocess_text(search_content))
            if isinstance(data, dict):
                # 单个文档对象
                documents_data = [data]
            elif isinstance(data, list):
                # 多个文档的列表
                documents_data = data
            else:
                raise ValueError("JSON content must be an object or array of objects")
        except json.JSONDecodeError:
            raise ValueError("string_content must be valid JSON")

        # 创建临时文件来存储 JSONL 格式的数据
        with tempfile.NamedTemporaryFile(mode='w', suffix='.jsonl', delete=False, encoding='utf-8') as temp_file:
            for doc in documents_data:
                temp_file.write(json.dumps(doc, ensure_ascii=False) + '\n')
            temp_file_path = temp_file.name

        try:
            # 使用现有的 build_index 函数处理临时文件
            result = build_index(temp_file_path)
            return result
        finally:
            # 清理临时文件
            os.unlink(temp_file_path)

    except Exception as e:
        print(f"Error processing JSON string content: {e}")
        return False    

def preprocess_text(text: str) -> str:
    """Preprocess text"""

    text = re.sub(r'\s+', ' ', text.strip())
    return text

def generate_citations(query):
    """Generate citations for a given query"""
    generator = CitationGenerator()
    citations = generator.generate_citations(query, k=3, include_explanation=True)
    return citations
async def main():
    import asyncio
    import json

    # 首先尝试使用现有的文档构建索引
    print("Building index from existing documents...")
    try:
        # 使用配置中的 DATA_DIR
        document_path = str(DATA_DIR / "documents.jsonl")
        result = build_index(document_path)
        print(f"Index building result: {result}")
    except Exception as e:
        print(f"Index building failed: {e}")
        return

    print("Generating citations...")
    citations = generate_citations("如何重置密码")

    if not citations:
        print("No citations found. This may indicate:")
        print("1. Index building failed (check for 'dummy_index' file)")
        print("2. Query didn't match any documents")
        print("3. Retrieval system encountered an error")
        print("\nTroubleshooting:")
        print("- Check if index was built successfully:")
        print("  ls -la models/colbert_index/documents/")
        print("- If 'dummy_index' exists, the index build failed.")
        print("  Common causes:")
        print("  * Too few documents (ColBERT needs at least 2 documents)")
        print("  * Document format issues")
        print("- Rebuild index with:")
        print("  python scripts/build_index.py build --input data/documents.jsonl --force")
        print("\nCheck the logs above for more details.")
    else:
        print("Generated citations:")
        for citation in citations:
            display_id = citation.original_document_id if citation.original_document_id else citation.document_id
            print(f"- ID: {display_id}")
            print(f"  URL: {citation.document_url if citation.document_url else 'N/A'}")
            print(f"  Score: {citation.score:.4f}")
            print(f"  Content: {citation.document_text[:100]}...")
            print()

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())