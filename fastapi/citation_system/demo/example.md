---

## 二、完整的使用示例与说明

### 2.1 示例 1：基础使用

```python
"""
示例 1：基础使用
展示如何快速开始使用 ColBERT 引用生成系统
"""

import logging
from pathlib import Path

# 设置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 导入必要的模块
from src.indexer import DocumentLoader, ColBERTIndexer
from src.citation_generator import CitationGenerator, CitationFormatter
from config import DATA_DIR

def example_basic_usage():
    """基础使用示例"""
    
    print("\n" + "="*60)
    print("示例 1：基础使用")
    print("="*60)
    
    # 第 1 步：加载文档
    print("\n[第 1 步] 加载文档...")
    loader = DocumentLoader()
    documents = loader.load_jsonl(str(DATA_DIR / "documents.jsonl"))
    print(f"✓ 加载了 {len(documents)} 个文档")
    
    # 第 2 步：构建索引
    print("\n[第 2 步] 构建索引...")
    indexer = ColBERTIndexer()
    indexer.build_index(documents, force_rebuild=False)
    print("✓ 索引构建完成")
    
    # 第 3 步：初始化引用生成器
    print("\n[第 3 步] 初始化引用生成器...")
    generator = CitationGenerator()
    print("✓ 引用生成器已初始化")
    
    # 第 4 步：生成引用
    print("\n[第 4 步] 生成引用...")
    query = "如何重置密码"
    citations = generator.generate_citations(query, k=3, include_explanation=True)
    print(f"✓ 生成了 {len(citations)} 个引用")
    
    # 第 5 步：显示结果
    print("\n[第 5 步] 显示结果...")
    print(f"\n查询：{query}\n")
    
    for i, citation in enumerate(citations, 1):
        print(f"引用 {i}:")
        print(f"  • 文档 ID：{citation.document_id}")
        print(f"  • 相关性分数：{citation.score:.4f}")
        print(f"  • 匹配率：{citation.match_rate:.1%}")
        print(f"  • 解释：{citation.explanation}")
        print(f"  • 文本：{citation.document_text[:80]}...")
        print()
    
    return citations

if __name__ == "__main__":
    citations = example_basic_usage()
复制代码
输出示例：

============================================================
示例 1：基础使用
============================================================

[第 1 步] 加载文档...
✓ 加载了 5 个文档

[第 2 步] 构建索引...
✓ 索引构建完成

[第 3 步] 初始化引用生成器...
✓ 引用生成器已初始化

[第 4 步] 生成引用...
✓ 生成了 3 个引用

[第 5 步] 显示结果...

查询：如何重置密码

引用 1:
  • 文档 ID：1
  • 相关性分数：0.9500
  • 匹配率：66.7%
  • 解释：非常匹配：文档中大部分查询 token 都被找到
  • 文本：如何重置密码：访问登录页面，点击忘记密码，输入邮箱，检查邮件中的链接，设置新密码。

引用 2:
  • 文档 ID：3
  • 相关性分数：0.7200
  • 匹配率：33.3%
  • 解释：部分匹配：文档中部分查询 token 被找到
  • 文本：账户安全很重要。定期更改密码可以保护您的账户。使用强密码和双因素认证。

引用 3:
  • 文档 ID：4
  • 相关性分数：0.5800
  • 匹配率：16.7%
  • 解释：弱匹配：文档中很少查询 token 被找到
  • 文本：常见问题解答：如何登录、如何注册、如何修改个人信息、如何联系支持。
复制代码
2.2 示例 2：高级格式化与导出
"""
示例 2：高级格式化与导出
展示如何将引用导出为多种格式
"""

from src.citation_generator import CitationGenerator, CitationFormatter
from pathlib import Path
import json

def example_formatting_export():
    """格式化与导出示例"""
    
    print("\n" + "="*60)
    print("示例 2：高级格式化与导出")
    print("="*60)
    
    # 生成引用
    generator = CitationGenerator()
    citations = generator.generate_citations("如何重置密码", k=2)
    
    # Markdown 格式
    print("\n[格式 1] Markdown 输出：")
    print("-" * 40)
    for citation in citations:
        md = CitationFormatter.format_as_markdown(citation)
        print(md)
    
    # JSON 格式
    print("\n[格式 2] JSON 输出：")
    print("-" * 40)
    json_output = CitationFormatter.format_as_json(citations)
    print(json_output)
    
    # HTML 格式
    print("\n[格式 3] HTML 输出：")
    print("-" * 40)
    for citation in citations:
        html = CitationFormatter.format_as_html(citation)
        print(html[:200] + "...")
    
    # 保存到文件
    print("\n[保存] 保存到文件...")
    
    # 保存 JSON
    with open("citations.json", "w", encoding="utf-8") as f:
        f.write(json_output)
    print("✓ 已保存到 citations.json")
    
    # 保存 Markdown
    with open("citations.md", "w", encoding="utf-8") as f:
        for citation in citations:
            f.write(CitationFormatter.format_as_markdown(citation))
            f.write("\n\n")
    print("✓ 已保存到 citations.md")

if __name__ == "__main__":
    example_formatting_export()
复制代码
2.3 示例 3：批量处理
"""
示例 3：批量处理
展示如何批量处理多个查询
"""

from src.citation_generator import CitationGenerator
from src.batch_processor import BatchProcessor
from datetime import datetime
import json

def example_batch_processing():
    """批量处理示例"""
    
    print("\n" + "="*60)
    print("示例 3：批量处理")
    print("="*60)
    
    generator = CitationGenerator()
    
    # 查询列表
    queries = [
        "如何重置密码",
        "API 基础 URL 是什么",
        "如何保护账户安全",
        "密码应该包含什么",
        "API 认证方式"
    ]
    
    print(f"\n处理 {len(queries)} 个查询...")
    print("-" * 40)
    
    # 方式 1：使用生成器的批量方法
    start_time = datetime.now()
    batch_results = generator.batch_generate_citations(queries, k=2)
    elapsed = (datetime.now() - start_time).total_seconds()
    
    print(f"\n✓ 处理完成，耗时 {elapsed:.2f} 秒")
    print(f"  平均每个查询 {elapsed/len(queries):.4f} 秒\n")
    
    # 显示结果
    for query, citations_list in batch_results.items():
        print(f"查询：{query}")
        print(f"  找到 {len(citations_list)} 个引用")
        for i, citation in enumerate(citations_list, 1):
            print(f"    {i}. {citation.document_text[:60]}... (分数: {citation.score:.4f})")
        print()
    
    # 保存结果
    output_data = []
    for query, citations_list in batch_results.items():
        output_data.append({
            "query": query,
            "citations": [c.to_dict() for c in citations_list]
        })
    
    with open("batch_results.jsonl", "w", encoding="utf-8") as f:
        for item in output_data:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
    
    print("✓ 结果已保存到 batch_results.jsonl")

if __name__ == "__main__":
    example_batch_processing()
复制代码
输出示例：

============================================================
示例 3：批量处理
============================================================

处理 5 个查询...
----------------------------------------

✓ 处理完成，耗时 2.34 秒
  平均每个查询 0.4680 秒

查询：如何重置密码
  找到 2 个引用
    1. 如何重置密码：访问登录页面，点击忘记密码，输入邮箱，检查邮件中的链接，设置新密码。 (分数: 0.9500)
    2. 账户安全很重要。定期更改密码可以保护您的账户。使用强密码和双因素认证。 (分数: 0.7200)

查询：API 基础 URL 是什么
  找到 2 个引用
    1. API 使用指南：基础 URL 是 https://api.example.com/v1，需要 Bearer Token 认证。支持 JSON 和 XML 格式。 (分数: 0.9800)
    2. 常见问题解答：如何登录、如何注册、如何修改个人信息、如何联系支持。