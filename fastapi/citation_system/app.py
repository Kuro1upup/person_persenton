"""FastAPI 服务 - 完整版"""
import logging
from typing import List, Optional
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse, FileResponse
from pydantic import BaseModel
import uvicorn
from datetime import datetime
import json

from src.citation_generator import CitationGenerator, CitationFormatter, Citation
from src.highlighter import TokenHighlighter
from src.evaluator import CitationEvaluator
from src.utils import FileUtils, LoggerUtils
from config import LOG_DIR, LOG_LEVEL

# 设置日志
logger = LoggerUtils.setup_logger(
    __name__,
    log_file=LOG_DIR / "app.log",
    level=LOG_LEVEL
)

app = FastAPI(
    title="ColBERT 引用生成系统",
    description="基于 ColBERT 的高精度引用生成服务",
    version="1.0.0"
)

# ==================== 数据模型 ====================

class CitationRequest(BaseModel):
    """引用请求"""
    query: str
    k: int = 3
    include_explanation: bool = True

class CitationResponse(BaseModel):
    """引用响应"""
    query: str
    citations: List[dict]
    total_count: int
    timestamp: str

class BatchCitationRequest(BaseModel):
    """批量引用请求"""
    queries: List[str]
    k: int = 3

class HighlightRequest(BaseModel):
    """高亮请求"""
    query: str
    document: str

class HighlightResponse(BaseModel):
    """高亮响应"""
    original: str
    highlighted: str
    matches: List[dict]
    match_rate: float

class EvaluationRequest(BaseModel):
    """评测请求"""
    retrieved_docs: List[str]
    relevant_docs: List[str]

class EvaluationResponse(BaseModel):
    """评测响应"""
    precision: float
    recall: float
    f1: float

# ==================== 初始化 ====================

citation_generator = None

@app.on_event("startup")
async def startup_event():
    """启动事件"""
    global citation_generator
    logger.info("Starting up ColBERT Citation System...")
    
    try:
        citation_generator = CitationGenerator()
        logger.info("CitationGenerator initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize CitationGenerator: {e}")
        raise

@app.on_event("shutdown")
async def shutdown_event():
    """关闭事件"""
    logger.info("Shutting down ColBERT Citation System...")

# ==================== 路由 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "service": "ColBERT Citation System"
    }

@app.post("/cite", response_model=CitationResponse)
async def generate_citations(request: CitationRequest):
    """
    生成引用
    
    Args:
        request: 引用请求
    
    Returns:
        引用响应
    """
    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="Query cannot be empty")
        
        logger.info(f"Generating citations for: {request.query}")
        
        # 生成引用
        citations = citation_generator.generate_citations(
            query=request.query,
            k=request.k,
            include_explanation=request.include_explanation
        )
        
        # 转换为字典
        citations_data = [c.to_dict() for c in citations]
        
        return CitationResponse(
            query=request.query,
            citations=citations_data,
            total_count=len(citations_data),
            timestamp=datetime.now().isoformat()
        )
    
    except Exception as e:
        logger.error(f"Error generating citations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/cite/batch")
async def batch_citations(request: BatchCitationRequest):
    """
    批量生成引用
    
    Args:
        request: 批量请求
    
    Returns:
        批量结果
    """
    try:
        logger.info(f"Batch generating citations for {len(request.queries)} queries")
        
        results = {}
        for query in request.queries:
            citations = citation_generator.generate_citations(query, k=request.k)
            results[query] = [c.to_dict() for c in citations]
        
        return {
            "total_queries": len(request.queries),
            "results": results,
            "timestamp": datetime.now().isoformat()
        }
    
    except Exception as e:
        logger.error(f"Error in batch citations: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/highlight", response_model=HighlightResponse)
async def highlight_document(request: HighlightRequest):
    """
    高亮文档中的匹配
    
    Args:
        request: 高亮请求
    
    Returns:
        高亮响应
    """
    try:
        logger.debug(f"Highlighting for query: {request.query}")
        
        highlight_info = TokenHighlighter.highlight_matches(
            request.query,
            request.document
        )
        
        return HighlightResponse(
            original=highlight_info["original"],
            highlighted=highlight_info["highlighted"],
            matches=highlight_info["matches"],
            match_rate=highlight_info["match_rate"]
        )
    
    except Exception as e:
        logger.error(f"Error highlighting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/evaluate", response_model=EvaluationResponse)
async def evaluate_retrieval(request: EvaluationRequest):
    """
    评测检索性能
    
    Args:
        request: 评测请求
    
    Returns:
        评测指标
    """
    try:
        logger.debug("Evaluating retrieval performance")
        
        metrics = CitationEvaluator.evaluate_retrieval(
            request.retrieved_docs,
            request.relevant_docs
        )
        
        return EvaluationResponse(**metrics)
    
    except Exception as e:
        logger.error(f"Error in evaluation: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/format/markdown")
async def format_as_markdown(citations_data: List[dict]):
    """
    格式化为 Markdown
    
    Args:
        citations_data: 引用数据列表
    
    Returns:
        Markdown 文本
    """
    try:
        # 转换为 Citation 对象
        citations = [Citation(**c) for c in citations_data]
        
        markdown = ""
        for citation in citations:
            markdown += CitationFormatter.format_as_markdown(citation)
            markdown += "\n\n"
        
        return {"markdown": markdown}
    
    except Exception as e:
        logger.error(f"Error formatting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/format/html")
async def format_as_html(citations_data: List[dict]):
    """
    格式化为 HTML
    
    Args:
        citations_data: 引用数据列表
    
    Returns:
        HTML 文本
    """
    try:
        citations = [Citation(**c) for c in citations_data]
        
        html = "<html><body>\n"
        for citation in citations:
            html += CitationFormatter.format_as_html(citation)
            html += "\n"
        html += "</body></html>"
        
        return {"html": html}
    
    except Exception as e:
        logger.error(f"Error formatting: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/stats")
async def get_stats():
    """获取系统统计"""
    return {
        "service": "ColBERT Citation System",
        "version": "1.0.0",
        "status": "running",
        "timestamp": datetime.now().isoformat()
    }

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}")
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal Server Error"}
    )

# ==================== 主程序 ====================

if __name__ == "__main__":
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=9801,
        log_level=LOG_LEVEL.lower()
    )
