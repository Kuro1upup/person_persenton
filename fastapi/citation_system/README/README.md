citation-system/
├── README.md
├── requirements.txt
├── config.py
├── data/
│   ├── documents.jsonl              # 文档数据
│   ├── queries.jsonl                # 查询数据
│   ├── eval_dataset.jsonl           # 评测数据集
│   └── sample_docs.txt              # 示例文档
├── src/
│   ├── __init__.py
│   ├── indexer.py                   # 索引构建
│   ├── retriever.py                 # 检索与排序
│   ├── citation_generator.py        # 引用生成
│   ├── highlighter.py               # Token 级高亮
│   ├── evaluator.py                 # 评测指标
│   └── utils.py
├── models/
│   └── colbert_index/               # 索引存储
├── tests/
│   ├── test_indexer.py
│   ├── test_retriever.py
│   ├── test_citation.py
│   └── test_integration.py
├── notebooks/
│   └── demo.ipynb
└── app.py                           # FastAPI 服务
