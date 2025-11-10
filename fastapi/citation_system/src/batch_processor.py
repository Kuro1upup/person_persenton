"""批处理器"""
import logging
from typing import List, Dict, Callable
from tqdm import tqdm
import concurrent.futures
from datetime import datetime

logger = logging.getLogger(__name__)

class BatchProcessor:
    """批处理器"""
    
    @staticmethod
    def process_queries(
        queries: List[str],
        process_func: Callable,
        batch_size: int = 32,
        max_workers: int = 4,
        use_parallel: bool = False
    ) -> List[Dict]:
        """
        批量处理查询
        
        Args:
            queries: 查询列表
            process_func: 处理函数
            batch_size: 批大小
            max_workers: 最大工作线程数
            use_parallel: 是否使用并行处理
        
        Returns:
            处理结果列表
        """
        logger.info(f"Processing {len(queries)} queries with batch_size={batch_size}")
        
        results = []
        start_time = datetime.now()
        
        if use_parallel:
            results = BatchProcessor._process_parallel(
                queries, process_func, max_workers
            )
        else:
            results = BatchProcessor._process_sequential(
                queries, process_func, batch_size
            )
        
        elapsed_time = (datetime.now() - start_time).total_seconds()
        logger.info(f"Processing completed in {elapsed_time:.2f}s")
        logger.info(f"Average time per query: {elapsed_time/len(queries):.4f}s")
        
        return results
    
    @staticmethod
    def _process_sequential(
        queries: List[str],
        process_func: Callable,
        batch_size: int
    ) -> List[Dict]:
        """顺序处理"""
        results = []
        
        for i in tqdm(range(0, len(queries), batch_size), desc="Processing batches"):
            batch = queries[i:i+batch_size]
            batch_results = [process_func(q) for q in batch]
            results.extend(batch_results)
        
        return results
    
    @staticmethod
    def _process_parallel(
        queries: List[str],
        process_func: Callable,
        max_workers: int
    ) -> List[Dict]:
        """并行处理"""
        results = []
        
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = [executor.submit(process_func, q) for q in queries]
            
            for future in tqdm(
                concurrent.futures.as_completed(futures),
                total=len(futures),
                desc="Processing queries"
            ):
                try:
                    result = future.result()
                    results.append(result)
                except Exception as e:
                    logger.error(f"Error processing query: {e}")
        
        return results

class DatasetProcessor:
    """数据集处理器"""
    
    @staticmethod
    def process_dataset(
        input_file: str,
        output_file: str,
        process_func: Callable,
        batch_size: int = 32
    ):
        """
        处理数据集文件
        
        Args:
            input_file: 输入文件
            output_file: 输出文件
            process_func: 处理函数
            batch_size: 批大小
        """
        import json
        from pathlib import Path
        
        logger.info(f"Processing dataset: {input_file}")
        
        # 读取输入
        items = []
        with open(input_file, 'r', encoding='utf-8') as f:
            for line in f:
                if line.strip():
                    items.append(json.loads(line))
        
        # 处理
        results = BatchProcessor.process_queries(
            [item.get("query", "") for item in items],
            process_func,
            batch_size=batch_size
        )
        
        # 合并结果
        for item, result in zip(items, results):
            item["citations"] = result.get("citations", [])
            item["processed_at"] = datetime.now().isoformat()
        
        # 保存输出
        with open(output_file, 'w', encoding='utf-8') as f:
            for item in items:
                f.write(json.dumps(item, ensure_ascii=False) + '\n')
        
        logger.info(f"Results saved to {output_file}")
