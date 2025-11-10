"""工具函数集"""
import logging
import json
import hashlib
from pathlib import Path
from typing import List, Dict, Any
import pickle
from datetime import datetime

logger = logging.getLogger(__name__)

class FileUtils:
    """文件操作工具"""
    
    @staticmethod
    def load_jsonl(file_path: str) -> List[Dict]:
        """加载 JSONL 文件"""
        documents = []
        
        if not Path(file_path).exists():
            logger.warning(f"File not found: {file_path}")
            return documents
        
        with open(file_path, 'r', encoding='utf-8') as f:
            for line_no, line in enumerate(f, 1):
                try:
                    if line.strip():
                        doc = json.loads(line)
                        documents.append(doc)
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error at line {line_no}: {e}")
        
        logger.info(f"Loaded {len(documents)} documents from {file_path}")
        return documents
    
    @staticmethod
    def save_jsonl(data: List[Dict], file_path: str):
        """保存为 JSONL 文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            for item in data:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        logger.info(f"Saved {len(data)} items to {file_path}")
    
    @staticmethod
    def load_json(file_path: str) -> Dict:
        """加载 JSON 文件"""
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    
    @staticmethod
    def save_json(data: Any, file_path: str):
        """保存为 JSON 文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

class CacheUtils:
    """缓存工具"""
    
    @staticmethod
    def get_cache_key(query: str, params: Dict = None) -> str:
        """生成缓存键"""
        cache_str = query
        if params:
            cache_str += json.dumps(params, sort_keys=True)
        
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    @staticmethod
    def save_cache(key: str, value: Any, cache_dir: Path):
        """保存缓存"""
        cache_file = cache_dir / f"{key}.pkl"
        with open(cache_file, 'wb') as f:
            pickle.dump(value, f)
    
    @staticmethod
    def load_cache(key: str, cache_dir: Path) -> Any:
        """加载缓存"""
        cache_file = cache_dir / f"{key}.pkl"
        if cache_file.exists():
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        return None

class TextUtils:
    """文本处理工具"""
    
    @staticmethod
    def clean_text(text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = ' '.join(text.split())
        # 移除特殊字符（保留基本标点）
        text = text.replace('\n', ' ').replace('\r', ' ')
        return text.strip()
    
    @staticmethod
    def truncate_text(text: str, max_length: int) -> str:
        """截断文本"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    @staticmethod
    def split_sentences(text: str) -> List[str]:
        """分句"""
        # 简单的中文分句
        sentences = text.replace('。', '。\n').replace('！', '！\n').replace('？', '？\n').split('\n')
        return [s.strip() for s in sentences if s.strip()]
    
    @staticmethod
    def tokenize(text: str) -> List[str]:
        """分词"""
        return text.split()

class MetricsUtils:
    """指标计算工具"""
    
    @staticmethod
    def calculate_precision_recall_f1(tp: int, fp: int, fn: int) -> Dict:
        """计算精度、召回、F1"""
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
        
        return {
            "precision": precision,
            "recall": recall,
            "f1": f1
        }
    
    @staticmethod
    def calculate_mrr(ranked_list: List[bool]) -> float:
        """计算 MRR (Mean Reciprocal Rank)"""
        for i, is_relevant in enumerate(ranked_list, 1):
            if is_relevant:
                return 1 / i
        return 0
    
    @staticmethod
    def calculate_ndcg(ranked_list: List[float], k: int = 10) -> float:
        """计算 NDCG"""
        dcg = 0
        for i, relevance in enumerate(ranked_list[:k], 1):
            dcg += relevance / (i + 1)  # log2(i+1)
        
        # IDCG (理想 DCG)
        ideal_list = sorted(ranked_list, reverse=True)[:k]
        idcg = 0
        for i, relevance in enumerate(ideal_list, 1):
            idcg += relevance / (i + 1)
        
        return dcg / idcg if idcg > 0 else 0
    
    @staticmethod
    def calculate_map(ranked_list: List[bool], k: int = 10) -> float:
        """计算 MAP (Mean Average Precision)"""
        ap = 0
        num_relevant = 0
        
        for i, is_relevant in enumerate(ranked_list[:k], 1):
            if is_relevant:
                num_relevant += 1
                ap += num_relevant / i
        
        total_relevant = sum(ranked_list)
        return ap / total_relevant if total_relevant > 0 else 0

class LoggerUtils:
    """日志工具"""
    
    @staticmethod
    def setup_logger(name: str, log_file: Path = None, level=logging.INFO):
        """设置日志"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # 控制台处理器
        console_handler = logging.StreamHandler()
        console_handler.setLevel(level)
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # 文件处理器
        if log_file:
            log_file.parent.mkdir(exist_ok=True, parents=True)
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(level)
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger

class PerformanceUtils:
    """性能工具"""
    
    @staticmethod
    def measure_time(func):
        """测量函数执行时间的装饰器"""
        import time
        from functools import wraps
        
        @wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            result = func(*args, **kwargs)
            elapsed_time = time.time() - start_time
            logger.info(f"{func.__name__} took {elapsed_time:.2f} seconds")
            return result
        
        return wrapper
