#!/bin/bash

# ColBERT 引用生成系统初始化脚本

set -e

echo "================================"
echo "ColBERT 引用生成系统初始化"
echo "================================"

# 1. 创建目录结构
echo ""
echo "[1/6] 创建目录结构..."
mkdir -p data
mkdir -p models/colbert_index
mkdir -p logs
mkdir -p tests
mkdir -p notebooks
mkdir -p scripts

echo "✓ 目录创建完成"

# 2. 安装依赖
echo ""
echo "[2/6] 安装 Python 依赖..."

if command -v pip &> /dev/null; then
    pip install -r requirements.txt
    echo "✓ 依赖安装完成"
else
    echo "✗ 找不到 pip，请手动安装依赖"
    exit 1
fi

# 3. 下载示例数据
echo ""
echo "[3/6] 准备示例数据..."

# 创建示例 JSONL 文件
cat > data/documents.jsonl << 'EOF'
{"id": "1", "title": "密码重置指南", "text": "如何重置密码：访问登录页面，点击忘记密码，输入邮箱，检查邮件中的链接，设置新密码。"}
{"id": "2", "title": "API 文档", "text": "API 使用指南：基础 URL 是 https://api.example.com/v1，需要 Bearer Token 认证。支持 JSON 和 XML 格式。"}
{"id": "3", "title": "账户安全", "text": "账户安全很重要。定期更改密码可以保护您的账户。使用强密码和双因素认证。"}
{"id": "4", "title": "常见问题", "text": "常见问题解答：如何登录、如何注册、如何修改个人信息、如何联系支持。"}
{"id": "5", "title": "用户指南", "text": "用户指南：账户创建、登录、密码管理、隐私设置、数据导出等功能说明。"}
EOF

echo "✓ 示例数据准备完成"

# 4. 创建评测数据集
echo ""
echo "[4/6] 创建评测数据集..."

cat > data/eval_dataset.jsonl << 'EOF'
{"query": "如何重置密码", "relevant_docs": ["1"], "expected_answer": "访问登录页面，点击忘记密码，输入邮箱，检查邮件中的链接，设置新密码。"}
{"query": "API 基础 URL 是什么", "relevant_docs": ["2"], "expected_answer": "API 基础 URL 是 https://api.example.com/v1"}
{"query": "如何保护账户安全", "relevant_docs": ["3", "1"], "expected_answer": "定期更改密码，使用强密码，启用双因素认证。"}
EOF

echo "✓ 评测数据集创建完成"

# 5. 构建索引
echo ""
echo "[5/6] 构建 ColBERT 索引..."
echo "这可能需要几分钟时间，请耐心等待..."

python scripts/build_index.py build \
  --input data/documents.jsonl \
  --index-name documents \
  --force

echo "✓ 索引构建完成"

# 6. 验证安装
echo ""
echo "[6/6] 验证安装..."

python -c "
import sys
try:
    from src.indexer import ColBERTIndexer
    from src.citation_generator import CitationGenerator
    print('✓ 所有模块导入成功')
except ImportError as e:
    print(f'✗ 导入失败: {e}')
    sys.exit(1)
"

echo ""
echo "================================"
echo "初始化完成！"
echo "================================"
echo ""
echo "下一步："
echo "1. 启动 API 服务：python app.py"
echo "2. 运行演示：jupyter notebook notebooks/demo.ipynb"
echo "3. 运行测试：pytest tests/"
echo ""
