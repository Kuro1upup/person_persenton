"""
ColBERT 索引构建脚本
支持从零开始构建索引、增量更新、索引验证等
"""

import logging
import json
import argparse
import sys
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np  # type: ignore
from datetime import datetime
from tqdm import tqdm  # type: ignore

# 添加项目根目录到路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

# 动态导入以支持直接运行和模块导入
try:
    from src.indexer import ColBERTIndexer, DocumentLoader
    from src.utils import FileUtils, LoggerUtils, PerformanceUtils
    from config import DATA_DIR, INDEX_DIR, MODEL_DIR
except ImportError:
    # 如果直接导入失败，尝试绝对导入
    from citation_system.src.indexer import ColBERTIndexer, DocumentLoader
    from citation_system.src.utils import FileUtils, LoggerUtils, PerformanceUtils
    from citation_system.config import DATA_DIR, INDEX_DIR, MODEL_DIR

# 设置日志
logger = LoggerUtils.setup_logger(
    __name__,
    log_file=Path("logs") / "build_index.log"
)

class IndexBuilder:
    """索引构建器"""
    
    def __init__(self, output_dir: Path = INDEX_DIR):
        """初始化索引构建器"""
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(exist_ok=True, parents=True)
        self.indexer = ColBERTIndexer()
        logger.info(f"IndexBuilder initialized with output_dir: {output_dir}")
    
    @PerformanceUtils.measure_time
    def build_from_jsonl(
        self,
        jsonl_file: str,
        index_name: str = "documents",
        force_rebuild: bool = False
    ) -> Dict:
        """
        从 JSONL 文件构建索引
        
        Args:
            jsonl_file: JSONL 文件路径
            index_name: 索引名称
            force_rebuild: 是否强制重建
        
        Returns:
            构建结果信息
        """
        logger.info(f"Building index from {jsonl_file}")
        
        # 检查索引是否已存在
        index_path = self.output_dir / index_name
        if index_path.exists() and not force_rebuild:
            logger.warning(f"Index already exists at {index_path}")
            return {
                "status": "exists",
                "message": f"Index already exists at {index_path}",
                "index_path": str(index_path)
            }
        
        # 加载文档
        logger.info("Loading documents...")
        loader = DocumentLoader()
        documents, _ = loader.load_jsonl(jsonl_file)
        
        if not documents:
            logger.error("No documents loaded")
            return {"status": "error", "message": "No documents loaded"}
        
        logger.info(f"Loaded {len(documents)} documents")
        
        # 验证文档格式
        logger.info("Validating document format...")
        valid_docs = self._validate_documents(documents)
        logger.info(f"Validated {len(valid_docs)}/{len(documents)} documents")
        
        # 检查文档数量
        if len(valid_docs) < 2:
            error_msg = f"ColBERT requires at least 2 documents, but only {len(valid_docs)} document(s) provided"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        
        # 构建索引
        logger.info("Building index...")
        try:
            self.indexer.build_index(valid_docs, force_rebuild=force_rebuild)
            
            # 检查是否创建了 dummy index（表示构建失败）
            dummy_file = index_path / "dummy_index"
            if dummy_file.exists():
                error_msg = "Index build failed - dummy index created. Check logs for details."
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}
            
            # 生成元数据
            metadata = self._generate_metadata(valid_docs, index_name)
            
            # 保存元数据
            metadata_file = index_path / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Index built successfully at {index_path}")
            
            return {
                "status": "success",
                "index_path": str(index_path),
                "num_documents": len(valid_docs),
                "metadata": metadata
            }
        
        except Exception as e:
            logger.error(f"Error building index: {e}")
            return {"status": "error", "message": str(e)}
    
    @PerformanceUtils.measure_time
    def build_from_txt(
        self,
        txt_file: str,
        chunk_size: int = 512,
        index_name: str = "documents"
    ) -> Dict:
        """
        从文本文件构建索引
        
        Args:
            txt_file: 文本文件路径
            chunk_size: 分块大小
            index_name: 索引名称
        
        Returns:
            构建结果信息
        """
        logger.info(f"Building index from {txt_file}")
        
        # 加载文档
        loader = DocumentLoader()
        documents = loader.load_txt(txt_file, chunk_size=chunk_size)
        
        logger.info(f"Loaded {len(documents)} chunks from {txt_file}")
        
        # 验证文档格式
        logger.info("Validating document format...")
        valid_docs = self._validate_documents(documents)
        logger.info(f"Validated {len(valid_docs)}/{len(documents)} documents")

        # 检查文档数量
        if len(valid_docs) < 2:
            error_msg = f"ColBERT requires at least 2 documents, but only {len(valid_docs)} document(s) provided"
            logger.error(error_msg)
            return {"status": "error", "message": error_msg}
        
        # 构建索引
        logger.info("Building index...")
        try:
            self.indexer.build_index(valid_docs, force_rebuild=True)
            
            # 检查是否创建了 dummy index（表示构建失败）
            index_path = self.output_dir / index_name
            dummy_file = index_path / "dummy_index"
            if dummy_file.exists():
                error_msg = "Index build failed - dummy index created. Check logs for details."
                logger.error(error_msg)
                return {"status": "error", "message": error_msg}

            # 生成元数据
            metadata = self._generate_metadata(valid_docs, index_name)

            # 保存元数据
            metadata_file = index_path / "metadata.json"
            with open(metadata_file, 'w', encoding='utf-8') as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)

            logger.info(f"Index built successfully at {index_path}")

            return {
                "status": "success",
                "index_path": str(index_path),
                "num_documents": len(valid_docs),
                "metadata": metadata
            }

        except Exception as e:
            logger.error(f"Error building index: {e}")
            return {"status": "error", "message": str(e)}
    
    def _validate_documents(self, documents: List[Dict]) -> List[Dict]:
        """验证文档格式"""
        valid_docs = []
        
        for i, doc in enumerate(documents):
            # 检查必需字段
            if not all(k in doc for k in ['id', 'title', 'text']):
                logger.warning(f"Document {i} missing required fields")
                continue
            
            # 检查文本长度
            if len(doc['text'].strip()) == 0:
                logger.warning(f"Document {i} has empty text")
                continue
            
            valid_docs.append(doc)
        
        return valid_docs
    
    def _generate_metadata(self, documents: List[Dict], index_name: str) -> Dict:
        """生成索引元数据"""
        return {
            "index_name": index_name,
            "created_at": datetime.now().isoformat(),
            "num_documents": len(documents),
            "colbert_model": "colbert-ir/colbertv2.0",
            "chunk_size": 300,
            "documents": [
                {
                    "id": doc.get("id"),
                    "title": doc.get("title"),
                    "text_length": len(doc.get("text", ""))
                }
                for doc in documents[:10]  # 只保存前 10 个样本
            ]
        }
    
    def verify_index(self, index_name: str = "documents") -> Dict:
        """验证索引完整性"""
        logger.info(f"Verifying index: {index_name}")
        
        index_path = self.output_dir / index_name
        
        if not index_path.exists():
            logger.error(f"Index not found: {index_path}")
            return {"status": "error", "message": "Index not found"}
        
        # 检查是否是 dummy index
        dummy_file = index_path / "dummy_index"
        if dummy_file.exists():
            logger.warning("Dummy index detected - index build failed")
            with open(dummy_file, 'r') as f:
                dummy_content = f.read()
            return {
                "status": "dummy",
                "message": "Dummy index detected - index build failed",
                "details": dummy_content.strip()
            }
        
        # 检查必需文件
        required_files = [
            "metadata.json",
            "docid_to_pid.npy",
            "doclens.npy",
            "embeddings.npy",
            "pid_to_docid.npy"
        ]
        
        missing_files = []
        for file in required_files:
            file_path = index_path / file
            if not file_path.exists():
                missing_files.append(file)
        
        if missing_files:
            logger.error(f"Missing files: {missing_files}")
            return {
                "status": "incomplete",
                "missing_files": missing_files,
                "message": f"Index is incomplete - missing {len(missing_files)} required file(s)"
            }
        
        # 检查文件大小
        total_size = sum(f.stat().st_size for f in index_path.glob("*"))
        
        # 加载元数据
        with open(index_path / "metadata.json", 'r') as f:
            metadata = json.load(f)
        
        logger.info("Index verification passed")
        
        return {
            "status": "valid",
            "index_path": str(index_path),
            "total_size_gb": total_size / (1024**3),
            "num_documents": metadata.get("num_documents"),
            "created_at": metadata.get("created_at")
        }
    
    def get_index_info(self, index_name: str = "documents") -> Dict:
        """获取索引信息"""
        index_path = self.output_dir / index_name
        
        if not index_path.exists():
            return {"status": "not_found"}
        
        # 加载元数据
        metadata_file = index_path / "metadata.json"
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        else:
            metadata = {}
        
        # 获取文件信息
        files_info = []
        for file_path in index_path.glob("*"):
            files_info.append({
                "name": file_path.name,
                "size_mb": file_path.stat().st_size / (1024**2)
            })
        
        total_size = sum(f["size_mb"] for f in files_info)
        
        return {
            "index_path": str(index_path),
            "metadata": metadata,
            "files": files_info,
            "total_size_mb": total_size,
            "total_size_gb": total_size / 1024
        }

class IndexManager:
    """索引管理器"""
    
    def __init__(self, index_dir: Path = INDEX_DIR):
        self.index_dir = Path(index_dir)
    
    def list_indices(self) -> List[str]:
        """列出所有索引"""
        indices = []
        for item in self.index_dir.iterdir():
            if item.is_dir() and (item / "metadata.json").exists():
                indices.append(item.name)
        return sorted(indices)
    
    def delete_index(self, index_name: str):
        """删除索引"""
        import shutil
        index_path = self.index_dir / index_name
        
        if index_path.exists():
            shutil.rmtree(index_path)
            logger.info(f"Index deleted: {index_name}")
        else:
            logger.warning(f"Index not found: {index_name}")
    
    def copy_index(self, source_name: str, target_name: str):
        """复制索引"""
        import shutil
        source_path = self.index_dir / source_name
        target_path = self.index_dir / target_name
        
        if not source_path.exists():
            logger.error(f"Source index not found: {source_name}")
            return False
        
        if target_path.exists():
            logger.error(f"Target index already exists: {target_name}")
            return False
        
        shutil.copytree(source_path, target_path)
        logger.info(f"Index copied: {source_name} -> {target_name}")
        return True
    
    def get_total_size(self) -> float:
        """获取所有索引总大小（GB）"""
        total_size = 0
        for index_dir in self.index_dir.iterdir():
            if index_dir.is_dir():
                for file in index_dir.rglob("*"):
                    if file.is_file():
                        total_size += file.stat().st_size
        return total_size / (1024**3)

def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="ColBERT 索引构建工具",
        epilog="示例:\n  %(prog)s build --input data/documents.jsonl\n  %(prog)s verify --index-name documents\n  %(prog)s list",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        choices=["build", "verify", "info", "list", "delete"],
        help="命令: build (构建索引), verify (验证索引), info (索引信息), list (列出索引), delete (删除索引)"
    )
    
    parser.add_argument(
        "--input",
        type=str,
        help="输入文件路径（JSONL 或 TXT）"
    )
    
    parser.add_argument(
        "--index-name",
        type=str,
        default="documents",
        help="索引名称"
    )
    
    parser.add_argument(
        "--force",
        action="store_true",
        help="强制重建索引"
    )
    
    parser.add_argument(
        "--chunk-size",
        type=int,
        default=512,
        help="文本文件分块大小"
    )
    
    args = parser.parse_args()
    
    # 如果没有提供命令，但有 --input 参数，默认使用 build 命令
    if args.command is None:
        if args.input:
            args.command = "build"
        else:
            parser.print_help()
            print("\n错误: 请指定一个命令 (build, verify, info, list, delete)")
            print("提示: 如果提供了 --input 参数，可以省略 'build' 命令")
            sys.exit(1)
    
    builder = IndexBuilder()
    manager = IndexManager()
    
    # 执行命令
    if args.command == "build":
        if not args.input:
            print("Error: --input 参数是必需的")
            return
        
        if args.input.endswith(".jsonl"):
            result = builder.build_from_jsonl(
                args.input,
                index_name=args.index_name,
                force_rebuild=args.force
            )
        elif args.input.endswith(".txt"):
            result = builder.build_from_txt(
                args.input,
                chunk_size=args.chunk_size,
                index_name=args.index_name
            )
        else:
            print("Error: 不支持的文件格式")
            return
        
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "verify":
        result = builder.verify_index(args.index_name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "info":
        result = builder.get_index_info(args.index_name)
        print(json.dumps(result, indent=2, ensure_ascii=False))
    
    elif args.command == "list":
        indices = manager.list_indices()
        print(f"已有索引 ({len(indices)}):")
        for idx in indices:
            info = builder.get_index_info(idx)
            print(f"  • {idx} ({info['total_size_mb']:.2f} MB)")
        print(f"\n总大小: {manager.get_total_size():.2f} GB")
    
    elif args.command == "delete":
        if not args.index_name:
            print("Error: --index-name 参数是必需的")
            return
        
        confirm = input(f"确认删除索引 '{args.index_name}'? (y/n): ")
        if confirm.lower() == 'y':
            manager.delete_index(args.index_name)
            print(f"索引已删除: {args.index_name}")

if __name__ == "__main__":
    main()
