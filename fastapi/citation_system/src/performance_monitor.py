"""性能监控"""
import logging
import time
from typing import Dict, List
from datetime import datetime
from collections import defaultdict
import json

logger = logging.getLogger(__name__)

class PerformanceMonitor:
    """性能监控器"""
    
    def __init__(self):
        self.metrics = defaultdict(list)
        self.start_time = datetime.now()
    
    def record_retrieval(self, query: str, num_results: int, elapsed_time: float):
        """记录检索性能"""
        self.metrics["retrieval_times"].append(elapsed_time)
        self.metrics["retrieval_counts"].append(num_results)
        logger.debug(f"Retrieval: {num_results} results in {elapsed_time:.4f}s")
    
    def record_citation_generation(self, num_citations: int, elapsed_time: float):
        """记录引用生成性能"""
        self.metrics["citation_times"].append(elapsed_time)
        self.metrics["citation_counts"].append(num_citations)
        logger.debug(f"Citation generation: {num_citations} citations in {elapsed_time:.4f}s")
    
    def record_highlighting(self, num_matches: int, elapsed_time: float):
        """记录高亮性能"""
        self.metrics["highlight_times"].append(elapsed_time)
        self.metrics["highlight_matches"].append(num_matches)
        logger.debug(f"Highlighting: {num_matches} matches in {elapsed_time:.4f}s")
    
    def get_summary(self) -> Dict:
        """获取性能摘要"""
        summary = {
            "timestamp": datetime.now().isoformat(),
            "uptime_seconds": (datetime.now() - self.start_time).total_seconds()
        }
        
        # 计算平均值
        for metric_name, values in self.metrics.items():
            if values and isinstance(values[0], (int, float)):
                summary[f"{metric_name}_avg"] = sum(values) / len(values)
                summary[f"{metric_name}_min"] = min(values)
                summary[f"{metric_name}_max"] = max(values)
                summary[f"{metric_name}_count"] = len(values)
        
        return summary
    
    def log_summary(self):
        """打印性能摘要"""
        summary = self.get_summary()
        logger.info(f"Performance Summary: {json.dumps(summary, indent=2)}")

class TimingContext:
    """计时上下文管理器"""
    
    def __init__(self, name: str, monitor: PerformanceMonitor = None):
        self.name = name
        self.monitor = monitor
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = time.time() - self.start_time
        logger.debug(f"{self.name} took {elapsed:.4f}s")
        return False
