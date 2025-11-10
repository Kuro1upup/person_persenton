"""ColBERT 引用系统配置"""
import os
from pathlib import Path

# 路径
BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
MODEL_DIR = BASE_DIR / "models"
INDEX_DIR = MODEL_DIR / "colbert_index"
LOG_DIR = BASE_DIR / "logs"

for d in [DATA_DIR, MODEL_DIR, INDEX_DIR, LOG_DIR]:
    d.mkdir(exist_ok=True, parents=True)

# ColBERT 模型配置
COLBERT_MODEL = "colbert-ir/colbertv2.0"
COLBERT_BATCH_SIZE = 32
COLBERT_MAX_TOKENS = 300

# 检索配置
RETRIEVAL_K = 100  # 初始检索 Top-K
RERANK_K = 10      # 精排后 Top-K
CITATION_K = 3     # 最终引用数量

# 高亮配置
MIN_HIGHLIGHT_LENGTH = 3  # 最小高亮 token 数
MAX_HIGHLIGHTS = 5        # 最多高亮数量

# 评测配置
EVAL_K_VALUES = [1, 5, 10, 50, 100]
MRR_K = 10

# 日志
LOG_LEVEL = "INFO"
DEBUG_MODE = os.getenv("DEBUG_MODE", "false").lower() == "true"

# 缓存
CACHE_EMBEDDINGS = True
CACHE_DIR = MODEL_DIR / ".cache"
CACHE_DIR.mkdir(exist_ok=True, parents=True)
