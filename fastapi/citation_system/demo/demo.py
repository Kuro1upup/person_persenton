"""
ColBERT 引用生成系统演示 Notebook

这是一个完整的演示，展示如何使用 ColBERT 引用生成系统。
"""

# ==================== 1. 安装和导入 ====================

# !pip install -r requirements.txt

import sys
from pathlib import Path

# 添加项目路径
project_root = Path("/home/spiritai/wpx/fastapi/citation-system/")
sys.path.insert(0, str(project_root))

import logging
logging.basicConfig(level=logging.INFO)

from src.indexer import DocumentLoader, ColBERTIndexer
from src.citation_generator import CitationGenerator, CitationFormatter
from src.highlighter import TokenHighlighter, ExplanationGenerator
from src.evaluator import CitationEvaluator
from config import DATA_DIR, INDEX_DIR

# ==================== 2. 加载和索引文档 ====================

print("=" * 50)
print("第 1 步：加载和索引文档")
print("=" * 50)

# 加载文档
loader = DocumentLoader()
documents = loader.load_txt(str(DATA_DIR / "documents.jsonl"))

print(f"\n✓ 加载了 {len(documents)} 个文档")
for doc in documents[:2]:
    print(f"  - 文档 {doc['id']}: {doc['title']}")

# 构建索引
indexer = ColBERTIndexer()
print("\n正在构建索引...")
indexer.build_index(documents, force_rebuild=True)
print("✓ 索引构建完成")

# ==================== 3. 生成引用 ====================

print("\n" + "=" * 50)
print("第 2 步：生成引用")
print("=" * 50)

generator = CitationGenerator()

# 单个查询
query = "如何重置密码"
print(f"\n查询：{query}")

citations = generator.generate_citations(query, k=3, include_explanation=True)

print(f"✓ 生成了 {len(citations)} 个引用\n")

for i, citation in enumerate(citations, 1):
    print(f"引用 {i}:")
    print(f"  文档 ID: {citation.document_id}")
    print(f"  相关性分数: {citation.score:.4f}")
    print(f"  匹配率: {citation.match_rate:.1%}")
    print(f"  解释: {citation.explanation}")
    print(f"  文档: {citation.document_text[:100]}...")
    print()

# ==================== 4. 高亮和解释 ====================

print("=" * 50)
print("第 3 步：高亮和解释")
print("=" * 50)

# 获取第一个引用
citation = citations[0]

print(f"\n原始文档:")
print(f"  {citation.document_text}\n")

print(f"高亮文档:")
print(f"  {citation.highlighted_text}\n")

print(f"匹配详情:")
for match in citation.matches:
    print(f"  - {match['text']} (相似度: {match['score']:.1%})")

# ==================== 5. 格式化输出 ====================

print("\n" + "=" * 50)
print("第 4 步：格式化输出")
print("=" * 50)

# Markdown 格式
print("\nMarkdown 格式:")
markdown = CitationFormatter.format_as_markdown(citation)
print(markdown[:300] + "...")

# JSON 格式
print("\nJSON 格式:")
json_str = CitationFormatter.format_as_json(citations[:1])
print(json_str)

# ==================== 6. 批量处理 ====================

print("\n" + "=" * 50)
print("第 5 步：批量处理")
print("=" * 50)

queries = [
    "如何重置密码",
    "API 基础 URL 是什么",
    "如何保护账户安全"
]

print(f"\n处理 {len(queries)} 个查询...")

batch_results = generator.batch_generate_citations(queries, k=2)

for query, citations_list in batch_results.items():
    print(f"\n查询: {query}")
    print(f"  找到 {len(citations_list)} 个引用")
    if citations_list:
        print(f"  最佳引用: {citations_list[0].document_text[:80]}...")

# 重新获取密码重置指南文档的引用，用于后续的高级特性演示
password_reset_citation = None
for cit in citations:
    if "密码重置指南" in cit.document_text:
        password_reset_citation = cit
        break

if password_reset_citation:
    citation = password_reset_citation

# 恢复正确的查询，用于高级特性演示
query = "如何重置密码"

# ==================== 7. 评测 ====================

print("\n" + "=" * 50)
print("第 6 步：评测")
print("=" * 50)

# 检索评测
retrieved = ["1", "2", "3"]
relevant = ["1", "3"]

metrics = CitationEvaluator.evaluate_retrieval(retrieved, relevant)

print(f"\n检索评测:")
print(f"  精度 (Precision): {metrics['precision']:.2%}")
print(f"  召回 (Recall): {metrics['recall']:.2%}")
print(f"  F1 分数: {metrics['f1']:.4f}")

# 排序评测
ranked = ["1", "2", "3", "4", "5"]
ranking_metrics = CitationEvaluator.evaluate_ranking(ranked, relevant)

print(f"\n排序评测:")
print(f"  Recall@1: {ranking_metrics['recall@1']:.2%}")
print(f"  Recall@5: {ranking_metrics['recall@5']:.2%}")
print(f"  MRR: {ranking_metrics['mrr']:.4f}")
print(f"  NDCG: {ranking_metrics['ndcg']:.4f}")

# ==================== 8. 高级特性 ====================

print("\n" + "=" * 50)
print("第 7 步：高级特性")
print("=" * 50)

# 上下文窗口
print(f"\n上下文窗口:")
windows = TokenHighlighter.get_context_windows(query, citation.document_text)
for i, window in enumerate(windows[:2], 1):
    print(f"  窗口 {i}: {window['highlighted']}")

# 详细解释
explanation = ExplanationGenerator.generate_explanation(
    query, citation.document_text, citation.score
)

print(f"\n详细解释:")
print(f"  摘要: {explanation['summary']}")
print(f"  匹配数: {explanation['match_statistics']['total_matches']}")
print(f"  匹配率: {explanation['match_statistics']['match_rate']:.1%}")
print(f"  平均匹配分数: {explanation['match_statistics']['avg_match_score']:.4f}")

# ==================== 9. 总结 ====================

print("\n" + "=" * 50)
print("演示完成！")
print("=" * 50)

print("\n关键要点:")
print("✓ 成功加载和索引了文档")
print("✓ 生成了高质量的引用")
print("✓ 进行了 Token 级高亮")
print("✓ 评测了检索性能")
print("✓ 支持批量处理和多种输出格式")
