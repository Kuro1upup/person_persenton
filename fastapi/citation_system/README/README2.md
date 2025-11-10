# ColBERT 引用生成系统

基于 Stanford ColBERT 的高精度引用生成系统，支持 Token 级匹配、可解释性解释、批量处理等功能。

## 特性

- 🎯 **高精度检索**：基于 ColBERT Token 级密集匹配
- 🔍 **可解释匹配**：Token 级高亮和上下文窗口
- 📊 **完整评测**：支持 Precision、Recall、MRR、NDCG 等指标
- 🚀 **高效处理**：支持批量处理和并行化
- 📝 **多格式输出**：Markdown、HTML、JSON 格式
- 💾 **智能缓存**：自动缓存检索结果

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt

2. 准备数据
# 将文档放入 data/documents.jsonl
# 格式：{"id": "1", "title": "标题", "text": "文本内容"}

3. 构建索引
from src.indexer import DocumentLoader, ColBERTIndexer

loader = DocumentLoader()
docs = loader.load_jsonl("data/documents.jsonl")

indexer = ColBERTIndexer()
indexer.build_index(docs, force_rebuild=True)

4. 生成引用
from src.citation_generator import CitationGenerator

generator = CitationGenerator()
citations = generator.generate_citations("如何重置密码", k=3)

for citation in citations:
    print(f"文档: {citation.document_id}")
    print(f"分数: {citation.score:.4f}")
    print(f"高亮: {citation.highlighted_text}")

API 使用
启动服务
python app.py
复制代码
生成引用
curl -X POST http://localhost:8000/cite \
  -H "Content-Type: application/json" \
  -d '{
    "query": "如何重置密码",
    "k": 3,
    "include_explanation": true
  }'
复制代码
批量处理
curl -X POST http://localhost:8000/cite/batch \
  -H "Content-Type: application/json" \
  -d '{
    "queries": ["如何重置密码", "API 基础 URL"],
    "k": 3
  }'
复制代码
高亮文档
curl -X POST http://localhost:8000/highlight \
  -H "Content-Type: application/json" \
  -d '{
    "query": "重置密码",
    "document": "如何重置密码：访问登录页面..."
  }'

评测
运行评测：

pytest tests/ -v
复制代码
运行性能测试：

pytest tests/ -v -m slow
复制代码
性能指标
操作	时间	吞吐量
检索（Top-100）	50-200ms	5-20 查询/秒
引用生成	100-500ms	2-10 引用/秒
高亮	10-50ms	20-100 文档/秒
批量处理	线性扩展	支持并行化
高级用法
自定义缓存
from src.cache_manager import CacheManager

cache = CacheManager(cache_dir="./cache", ttl_hours=24)

# 获取缓存
result = cache.get("查询词")

# 设置缓存
cache.set("查询词", result)

# 清空缓存
cache.clear()
复制代码
批量处理
from src.batch_processor import BatchProcessor

queries = ["查询1", "查询2", "查询3"]

def process_query(q):
    return generator.generate_citations(q, k=3)

results = BatchProcessor.process_queries(
    queries,
    process_query,
    batch_size=32,
    use_parallel=True,
    max_workers=4
)
复制代码
性能监控
from src.performance_monitor import PerformanceMonitor, TimingContext

monitor = PerformanceMonitor()

with TimingContext("检索", monitor):
    results = retriever.retrieve(query)

monitor.log_summary()
复制代码
常见问题
Q: 索引构建需要多长时间？
A: 取决于文档数量和硬件。百万级文档通常需要 1-2 小时。

Q: 可以使用 CPU 运行吗？
A: 可以，但会显著降低速度。建议使用 GPU。

Q: 支持中文吗？
A: 完全支持中文，包括分词、高亮等。

Q: 如何自定义模型？
A: 修改 config.py 中的 COLBERT_MODEL 参数。

许可证
MIT License

引用
如果使用本系统，请引用：

@inproceedings{khattab2021colbert,
  title={ColBERT: Efficient and Effective Passage Search via Contextualized Late Interaction over BERT},
  author={Khattab, Omar and Zaharia, Matei},
  booktitle={Proceedings of the 44th International ACM SIGIR Conference on Research and Development in Information Retrieval},
  pages={39--48},
  year={2021}
}      