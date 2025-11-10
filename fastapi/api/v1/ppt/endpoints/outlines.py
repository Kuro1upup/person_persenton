import asyncio
import json
import math
import traceback
from typing import Any, Dict, Optional
import uuid
import dirtyjson
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from models.presentation_outline_model import PresentationOutlineModel
from models.sql.presentation import PresentationModel
from models.sse_response import (
    SSECompleteResponse,
    SSEErrorResponse,
    SSEResponse,
    SSEStatusResponse,
)
from services.temp_file_service import TEMP_FILE_SERVICE
from services.database import get_async_session
from services.documents_loader import DocumentsLoader
from utils.llm_calls.generate_presentation_outlines import generate_ppt_outline, generate_ppt_outline_with_web_search,get_search_results_map
from utils.ppt_utils import get_presentation_title_from_outlines
from api.v1.auth.router import get_current_user, get_current_api_key
from utils.web_search import TavilySearchService
from citation_system.src.citation import build_index_from_search_content

tavily_search_service = TavilySearchService()

# 创建演示文稿大纲相关的路由器
OUTLINES_ROUTER = APIRouter(prefix="/outlines", tags=["Outlines"])


@OUTLINES_ROUTER.get("/stream/{id}", responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}})
async def stream_outlines(
    id: uuid.UUID,  # 演示文稿唯一标识符
    sql_session: AsyncSession = Depends(get_async_session),  # 数据库会话
    current_user: Optional[str] = Depends(get_current_user),  # 当前登录用户
    api_key: str = Depends(get_current_api_key)  # API密钥
):
    """
    流式生成演示文稿大纲的端点
    通过 SSE (Server-Sent Events) 实时返回大纲生成进度和结果
    """
    # 从数据库获取演示文稿信息
    presentation = await sql_session.get(PresentationModel, id)

    # 检查演示文稿是否存在
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # 检查用户是否有权限访问此演示文稿
    if presentation.user_id != current_user:
        raise HTTPException(status_code=403, detail="Not authorized to access this presentation")

    # 创建临时目录用于处理文件
    temp_dir = TEMP_FILE_SERVICE.create_temp_dir()

    # 内部异步生成器函数，用于流式返回结果
    async def inner():
        # 发送初始状态消息
        yield SSEStatusResponse(
            status="Generating presentation outlines..."
        ).to_string()

        # 加载额外文档作为上下文（如果有）
        additional_context = ""
        if presentation.file_paths:
            documents_loader = DocumentsLoader(file_paths=presentation.file_paths)
            await documents_loader.load_documents(temp_dir)
            documents = documents_loader.documents
            if documents:
                additional_context = "\n\n".join(documents)

        presentation_outlines_text = ""

        # 计算需要生成的幻灯片数量
        n_slides_to_generate = presentation.n_slides
        if presentation.include_table_of_contents:
            # 计算需要的目录页数量（每10页内容需要1页目录）
            needed_toc_count = math.ceil((presentation.n_slides - 1) / 10)
            n_slides_to_generate -= math.ceil(
                (presentation.n_slides - needed_toc_count) / 10
            )

        tavily_search_results = await tavily_search_service.search(presentation.content)
        search_content = get_search_results_map(tavily_search_results.get('results', []))

        # 调用LLM生成演示文稿大纲，并流式处理返回结果
        async for chunk in generate_ppt_outline_with_web_search(
            presentation.content,  # 演示文稿主题/内容
            n_slides_to_generate,  # 需要生成的幻灯片数量
            api_key,  # API密钥
            presentation.language,  # 语言
            additional_context,  # 额外上下文
            presentation.tone,  # 语调
            presentation.verbosity,  # 详细程度
            presentation.instructions,  # 额外指令
            presentation.include_title_slide,  # 是否包含标题幻灯片
            tavily_search_results,  # 是否启用网络搜索
            presentation.outline_model,  # 使用的模型
        ):
            # 让出控制权给事件循环，确保其他任务可以执行
            await asyncio.sleep(0)

            # 处理可能的错误
            if isinstance(chunk, HTTPException):
                yield SSEErrorResponse(detail=chunk.detail).to_string()
                return

            # 发送当前生成的内容块
            yield SSEResponse(
                event="response",
                data=json.dumps({"type": "chunk", "chunk": chunk}),
            ).to_string()

            # 积累生成的大纲文本
            presentation_outlines_text += chunk

        try:
            # 尝试将生成的文本解析为JSON格式
            presentation_outlines_json = dict(
                dirtyjson.loads(presentation_outlines_text)
            )
        except Exception as e:
            # 处理JSON解析错误
            traceback.print_exc()
            yield SSEErrorResponse(
                detail=f"Failed to generate presentation outlines. Please try again. {str(e)}",
            ).to_string()
            return

        # 将JSON数据转换为PresentationOutlineModel对象
        presentation_outlines = PresentationOutlineModel(**presentation_outlines_json)

        # 确保幻灯片数量不超过需要生成的数量
        presentation_outlines.slides = presentation_outlines.slides[
            :n_slides_to_generate
        ]

        # 更新演示文稿的大纲和标题
        presentation.outlines = presentation_outlines.model_dump()
        presentation.title = get_presentation_title_from_outlines(presentation_outlines)
        presentation.tavily_search_results_json = search_content
        # 保存更新后的演示文稿到数据库
        sql_session.add(presentation)
        await sql_session.commit()

        # 发送完成消息，包含完整的演示文稿数据
        yield SSECompleteResponse(
            key="presentation", value=presentation.model_dump(mode="json")
        ).to_string()

        # await build_index_from_search_content(search_content)

    # 返回流式响应，使用text/event-stream媒体类型
    return StreamingResponse(inner(), media_type="text/event-stream")
