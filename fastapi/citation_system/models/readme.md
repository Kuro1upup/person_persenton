models/
└── colbert_index/
    └── documents/                          # 索引名称（可自定义）
        ├── metadata.json                   # 索引元数据
        ├── docid_to_pid.npy               # 文档 ID 到段落 ID 映射
        ├── doclens.npy                    # 每个文档的长度
        ├── embeddings.npy                 # 所有段落的嵌入向量
        ├── ivf.npy                        # IVF 聚类中心（可选）
        ├── pid_to_docid.npy               # 段落 ID 到文档 ID 映射
        ├── residuals.npy                  # 残差向量（可选）
        ├── centroid_scores.npy            # 聚类中心分数
        ├── index.faiss                    # FAISS 索引文件
        └── code.faiss                     # FAISS 编码文件

索引文件说明
| 文件       | 大小       | 说明           |
|------------|------------|----------------|
| metadata.json | < 1KB      | 索引配置和元数据 |
| docid_to_pid.npy | 文档数 × 4 字节 | 文档到段落映射 |
| doclens.npy | 文档数 × 4 字节 | 文档长度数组 |
| embeddings.npy | 段落数 × 128 × 4 字节 | Token 嵌入（最大） |
| index.faiss | 段落数 × 128 × 4 字节 | FAISS 向量索引 |
| pid_to_docid.npy | 段落数 × 4 字节 | 段落到文档映射 |
| residuals.npy | 段落数 × 128 × 4 字节 | 残差向量（可选） |
| centroid_scores.npy | 段落数 × 4 字节 | 聚类中心分数 |
| index.faiss | 段落数 × 128 × 4 字节 | FAISS 向量索引 |
| code.faiss | 段落数 × 128 × 4 字节 | FAISS 编码文件 |


索引文件大小预估
文档数量 | 平均长度 | 索引大小 | 构建时间 | 查询延迟
---------|---------|---------|---------|----------
1K       | 100     | 50MB    | 1分钟   | 10ms
10K      | 100     | 500MB   | 5分钟   | 20ms
100K     | 100     | 5GB     | 30分钟  | 50ms
1M       | 100     | 50GB    | 2小时   | 100ms
10M      | 100     | 500GB   | 20小时  | 200ms



估算大小（百万文档）：
假设：
- 100 万文档
- 平均 100 token/文档
- 共 1 亿段落
总大小 ≈ 100M × 128 × 4 字节 ≈ 50GB