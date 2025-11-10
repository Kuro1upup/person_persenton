#!/bin/bash
# ColBERT 索引构建示例脚本

# 激活虚拟环境（如果存在）
if [ -d "venv" ]; then
    source venv/bin/activate
fi

# 1. 从 JSONL 文件构建索引
python scripts/build_index.py build \
  --input data/documents.jsonl \
  --index-name documents \
  --force

# 2. 从文本文件构建索引
python scripts/build_index.py build \
  --input data/sample_docs.txt \
  --index-name documents_txt \
  --chunk-size 512

# 3. 验证索引
python scripts/build_index.py verify \
  --index-name documents

# 4. 获取索引信息
python scripts/build_index.py info \
  --index-name documents

# 5. 列出所有索引
python scripts/build_index.py list

# 6. 删除索引
python scripts/build_index.py delete \
  --index-name old_index
