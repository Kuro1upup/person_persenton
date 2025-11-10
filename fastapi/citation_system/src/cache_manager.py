"""缓存管理器"""
import logging
import pickle
import hashlib
from pathlib import Path
from typing import Any, Optional, Dict
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class CacheManager:
    """缓存管理器"""
    
    def __init__(self, cache_dir: Path, ttl_hours: int = 24):
        """
        初始化缓存管理器
        
        Args:
            cache_dir: 缓存目录
            ttl_hours: 缓存过期时间（小时）
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(exist_ok=True, parents=True)
        self.ttl = timedelta(hours=ttl_hours)
    
    def _get_cache_key(self, query: str, params: Dict = None) -> str:
        """生成缓存键"""
        cache_str = query
        if params:
            import json
            cache_str += json.dumps(params, sort_keys=True)
        
        return hashlib.md5(cache_str.encode()).hexdigest()
    
    def get(self, query: str, params: Dict = None) -> Optional[Any]:
        """获取缓存"""
        cache_key = self._get_cache_key(query, params)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        if not cache_file.exists():
            return None
        
        # 检查过期时间
        file_time = datetime.fromtimestamp(cache_file.stat().st_mtime)
        if datetime.now() - file_time > self.ttl:
            logger.debug(f"Cache expired for key: {cache_key}")
            cache_file.unlink()
            return None
        
        try:
            with open(cache_file, 'rb') as f:
                return pickle.load(f)
        except Exception as e:
            logger.error(f"Error loading cache: {e}")
            return None
    
    def set(self, query: str, value: Any, params: Dict = None):
        """设置缓存"""
        cache_key = self._get_cache_key(query, params)
        cache_file = self.cache_dir / f"{cache_key}.pkl"
        
        try:
            with open(cache_file, 'wb') as f:
                pickle.dump(value, f)
            logger.debug(f"Cache saved for key: {cache_key}")
        except Exception as e:
            logger.error(f"Error saving cache: {e}")
    
    def clear(self):
        """清空所有缓存"""
        for cache_file in self.cache_dir.glob("*.pkl"):
            cache_file.unlink()
        logger.info("Cache cleared")
    
    def get_cache_size(self) -> int:
        """获取缓存大小（字节）"""
        total_size = 0
        for cache_file in self.cache_dir.glob("*.pkl"):
            total_size += cache_file.stat().st_size
        return total_size
