"""
快速启动脚本
一键初始化和测试系统
"""

import sys
import logging
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def check_dependencies():
    """检查依赖"""
    print("\n[检查] 检查依赖...")
    
    required_packages = [
        'torch',
        'transformers',
        'colbert',  # colbert-ir package imports as 'colbert'
        'faiss',
        'numpy',
        'pydantic',
        'fastapi'
    ]
    
    missing = []
    for package in required_packages:
        try:
            __import__(package)
        except ImportError:
            missing.append(package)
    
    if missing:
        print(f"✗ 缺失依赖: {', '.join(missing)}")
        print("  请运行: pip install -r requirements.txt")
        return False
    
    print("✓ 所有依赖已安装")
    return True

def check_data_files():
    """检查数据文件"""
    print("\n[检查] 检查数据文件...")
    
    from config import DATA_DIR
    
    required_files = [
        DATA_DIR / "documents.jsonl"
    ]
    
    missing = []
    for file in required_files:
        if not file.exists():
            missing.append(file)
    
    if missing:
        print(f"✗ 缺失数据文件:")
        for f in missing:
            print(f"  - {f}")
        return False
    
    print("✓ 所有数据文件已准备")
    return True

def build_index():
    """构建索引"""
    print("\n[构建] 构建 ColBERT 索引...")
    
    from src.indexer import DocumentLoader, ColBERTIndexer
    from config import DATA_DIR, INDEX_DIR
    
    try:
        loader = DocumentLoader()
        documents, _ = loader.load_jsonl(str(DATA_DIR / "documents.jsonl"))
        
        indexer = ColBERTIndexer()
        indexer.build_index(documents, force_rebuild=False)
        
        print("✓ 索引构建完成")
        return True
    
    except Exception as e:
        print(f"✗ 索引构建失败: {e}")
        return False

def test_citation_generation():
    """测试引用生成"""
    print("\n[测试] 测试引用生成...")
    
    try:
        from src.citation_generator import CitationGenerator
        
        generator = CitationGenerator()
        citations = generator.generate_citations("如何重置密码", k=2)
        
        if citations:
            print(f"✓ 成功生成 {len(citations)} 个引用")
            for i, citation in enumerate(citations, 1):
                print(f"  {i}. {citation.document_text[:60]}... (分数: {citation.score:.4f})")
            return True
        else:
            print("✗ 未生成任何引用")
            return False
    
    except Exception as e:
        print(f"✗ 引用生成测试失败: {e}")
        return False

def main():
    """主函数"""
    print("=" * 60)
    print("ColBERT 引用生成系统 - 快速启动")
    print("=" * 60)
    
    # 检查依赖
    if not check_dependencies():
        sys.exit(1)
    
    # 检查数据文件
    if not check_data_files():
        print("\n提示：可以运行 scripts/init_environment.sh 创建示例数据")
        sys.exit(1)
    
    # 构建索引
    if not build_index():
        sys.exit(1)
    
    # 测试引用生成
    if not test_citation_generation():
        sys.exit(1)
    
    print("\n" + "=" * 60)
    print("✓ 系统启动成功！")
    print("=" * 60)
    
    print("\n下一步：")
    print("1. 启动 API 服务：")
    print("   python app.py")
    print("")
    print("2. 运行演示 Notebook：")
    print("   jupyter notebook notebooks/demo.ipynb")
    print("")
    print("3. 运行测试：")
    print("   pytest tests/")

if __name__ == "__main__":
    main()
