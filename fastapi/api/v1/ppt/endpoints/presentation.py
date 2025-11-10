import asyncio
from datetime import datetime
import json
import math
import os
import random
import traceback
from typing import Annotated, Any, Dict, List, Literal, Optional, Tuple, Callable, Union
import dirtyjson
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Path, Request, Query, Form, UploadFile, File, status, Response
from fastapi.responses import StreamingResponse, JSONResponse
from sqlalchemy import delete, insert, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlmodel import Session, select
from constants.presentation import DEFAULT_TEMPLATES
from enums.webhook_event import WebhookEvent
from models.api_error_model import APIErrorModel
from models.generate_presentation_request import GeneratePresentationRequest
from models.presentation_and_path import PresentationPathAndEditPath
from models.presentation_from_template import EditPresentationRequest
from models.presentation_outline_model import (
    PresentationOutlineModel,
    SlideOutlineModel,
)
from enums.tone import Tone
from enums.verbosity import Verbosity
from models.pptx_models import PptxPresentationModel
from models.presentation_layout import PresentationLayoutModel
from models.presentation_structure_model import PresentationStructureModel
from models.presentation_with_slides import (
    PresentationWithSlides,
)
from models.sql.template import TemplateModel

from services.documents_loader import DocumentsLoader
from services.webhook_service import WebhookService
from utils.get_layout_by_name import get_layout_by_name
from services.image_generation_service import ImageGenerationService
from utils.dict_utils import deep_update
from utils.export_utils import export_presentation
from utils.llm_calls.generate_presentation_outlines import generate_ppt_outline, get_search_results_map
from models.sql.slide import SlideModel
from models.sse_response import SSECompleteResponse, SSEErrorResponse, SSEResponse

from services.database import get_async_session
from services.temp_file_service import TEMP_FILE_SERVICE
from services.concurrent_service import CONCURRENT_SERVICE
from models.sql.presentation import PresentationModel
from services.pptx_presentation_creator import PptxPresentationCreator
from models.sql.async_presentation_generation_status import (
    AsyncPresentationGenerationTaskModel,
)
from api.v1.auth.router import get_current_user, get_user_with_model_access, get_current_api_key
from utils.asset_directory_utils import get_exports_directory, get_images_directory
from utils.llm_calls.generate_presentation_structure import (
    generate_presentation_structure,
)
from utils.llm_calls.generate_slide_content import (
    get_slide_content_from_type_and_outline,
)
from utils.ppt_utils import (
    get_presentation_title_from_outlines,
    select_toc_or_list_slide_layout_index,
)
from utils.process_slides import (
    process_slide_add_placeholder_assets,
    process_slide_and_fetch_assets,
)
import uuid
from utils.citations import citations_instance
import logging
logging.basicConfig(level=logging.DEBUG)

# 创建演示文稿相关的API路由器，前缀为/presentation，标签为Presentation
PRESENTATION_ROUTER = APIRouter(prefix="/presentation", tags=["Presentation"])


@PRESENTATION_ROUTER.get("/all", response_model=List[PresentationWithSlides])
async def get_all_presentations(
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """
    获取所有演示文稿（每个演示文稿只返回第一张幻灯片）
    
    参数:
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID（可选）
    
    返回:
        演示文稿列表，每个包含基本信息和第一张幻灯片
    """
    presentations_with_slides = []

    # 构建查询，获取当前用户名下所有演示文稿及其第一张幻灯片
    query = (
        select(PresentationModel, SlideModel)
        .join(
            SlideModel,
            (SlideModel.presentation == PresentationModel.id) & (SlideModel.index == 0),
        )
        .where(PresentationModel.user_id == current_user)
        .order_by(PresentationModel.created_at.desc())
    )

    results = await sql_session.execute(query)
    rows = results.all()
    presentations_with_slides = [
        PresentationWithSlides(
            **presentation.model_dump(),
            slides=[first_slide],
        )
        for presentation, first_slide in rows
    ]
    return presentations_with_slides


@PRESENTATION_ROUTER.get("/{id}", response_model=PresentationWithSlides)
async def get_presentation(
    id: uuid.UUID,
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """
    获取单个演示文稿及其所有幻灯片
    
    参数:
        id: 演示文稿唯一标识符
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID
    
    返回:
        包含所有幻灯片的完整演示文稿对象
    
    异常:
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限访问该演示文稿
    """
    # 检查演示文稿是否存在
    presentation = await sql_session.get(PresentationModel, id)
    if not presentation:
        raise HTTPException(404, "Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to access this presentation")
    
    # 获取所有幻灯片
    slides = await sql_session.scalars(
        select(SlideModel)
        .where(SlideModel.presentation == id)
        .order_by(SlideModel.index)
    )
    return PresentationWithSlides(
        **presentation.model_dump(),
        slides=slides,
    )


@PRESENTATION_ROUTER.delete("/{id}", status_code=204)
async def delete_presentation(
    id: uuid.UUID,
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user)
):
    """
    删除指定的演示文稿
    
    参数:
        id: 演示文稿唯一标识符
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID
    
    返回:
        204状态码表示成功删除
    
    异常:
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限删除该演示文稿
    """
    presentation = await sql_session.get(PresentationModel, id)

    # 检查演示文稿是否存在
    if not presentation:
        raise HTTPException(404, "Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to delete this presentation")

    await sql_session.delete(presentation)
    await sql_session.commit()


@PRESENTATION_ROUTER.post("/create", response_model=PresentationModel)
async def create_presentation(
    content: Annotated[str, Body()],
    n_slides: Annotated[int, Body()],
    language: Annotated[str, Body()],
    file_paths: Annotated[Optional[List[str]], Body()] = None,
    tone: Annotated[Tone, Body()] = Tone.DEFAULT,
    verbosity: Annotated[Verbosity, Body()] = Verbosity.STANDARD,
    instructions: Annotated[Optional[str], Body()] = None,
    include_table_of_contents: Annotated[bool, Body()] = False,
    include_title_slide: Annotated[bool, Body()] = True,
    web_search: Annotated[bool, Body()] = False,
    model: Annotated[Optional[dict], Body()] = {"name": "gpt-4.1"},
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    创建新的演示文稿
    
    参数:
        content: 演示文稿内容
        n_slides: 幻灯片数量
        language: 演示文稿语言
        file_paths: 相关文件路径列表（可选）
        tone: 语调风格（默认：DEFAULT）
        verbosity: 详细程度（默认：STANDARD）
        instructions: 额外指示（可选）
        include_table_of_contents: 是否包含目录（默认：False）
        include_title_slide: 是否包含标题幻灯片（默认：True）
        web_search: 是否启用网络搜索（默认：False）
        model: 生成PPT大纲的模型配置（默认：{"name": "gpt-4.1"}）
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID（可选）
    
    返回:
        创建的演示文稿对象
    
    异常:
        HTTPException 400: 如果包含目录但幻灯片数量少于3
    """
    if include_table_of_contents and n_slides < 3:
        raise HTTPException(
            status_code=400,
            detail="Number of slides cannot be less than 3 if table of contents is included",
        )

    presentation_id = uuid.uuid4()

    # 关联演示文稿与用户
    presentation = PresentationModel(
        id=presentation_id,
        user_id=current_user,
        content=content,
        n_slides=n_slides,
        language=language,
        file_paths=file_paths,
        tone=tone.value,
        verbosity=verbosity.value,
        instructions=instructions,
        include_table_of_contents=include_table_of_contents,
        include_title_slide=include_title_slide,
        web_search=web_search,
        outline_model=model,
    )

    sql_session.add(presentation)
    await sql_session.commit()

    return presentation


@PRESENTATION_ROUTER.post("/prepare", response_model=PresentationModel)
async def prepare_presentation(
    presentation_id: Annotated[uuid.UUID, Body()],
    outlines: Annotated[List[SlideOutlineModel], Body()],
    layout: Annotated[PresentationLayoutModel, Body()],
    model: Annotated[Optional[dict], Body()] = {"name": "gpt-4.1"},
    image_model: Annotated[Optional[dict], Body()] = {"name": "gemini-2.5-flash-image-preview"},
    title: Annotated[Optional[str], Body()] = None,
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
    api_key: Optional[str] = Depends(get_current_api_key),
):
    """
    准备演示文稿（设置大纲、布局等）
    
    参数: 
        presentation_id: 演示文稿唯一标识符
        outlines: 幻灯片大纲列表
        layout: 演示文稿布局
        model: 生成演示文稿的模型配置（默认：{"name": "gpt-4.1"}）
        image_model: 生成演示文稿图片的模型配置（默认：{"name": "gemini-2.5-flash-image-preview"}）
        title: 演示文稿标题（可选）
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID（可选）
    
    返回:
        更新后的演示文稿对象
    
    异常:
        HTTPException 400: 大纲为空
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限修改该演示文稿
    """
    # 检查大纲是否为空
    if not outlines:
        raise HTTPException(status_code=400, detail="Outlines are required")

    # 检查演示文稿是否存在
    presentation = await sql_session.get(PresentationModel, presentation_id)
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to modify this presentation")

    presentation_outline_model = PresentationOutlineModel(slides=outlines)

    total_slide_layouts = len(layout.slides)
    total_outlines = len(outlines)

    if layout.ordered:
        presentation_structure = layout.to_presentation_structure()
    else:
        presentation_structure: PresentationStructureModel = (
            await generate_presentation_structure(
                presentation_outline=presentation_outline_model,
                presentation_layout=layout,
                instructions=presentation.instructions,
                api_key=api_key,
                model=model,
            )
        )

    presentation_structure.slides = presentation_structure.slides[: len(outlines)]
    for index in range(total_outlines):
        random_slide_index = random.randint(0, total_slide_layouts - 1)
        if index >= total_outlines:
            presentation_structure.slides.append(random_slide_index)
            continue
        if presentation_structure.slides[index] >= total_slide_layouts:
            presentation_structure.slides[index] = random_slide_index

    if presentation.include_table_of_contents:
        n_toc_slides = presentation.n_slides - total_outlines
        toc_slide_layout_index = select_toc_or_list_slide_layout_index(layout)
        if toc_slide_layout_index != -1:
            outline_index = 1 if presentation.include_title_slide else 0
            for i in range(n_toc_slides):
                outlines_to = outline_index + 10
                if total_outlines == outlines_to:
                    outlines_to -= 1

                presentation_structure.slides.insert(
                    i + 1 if presentation.include_title_slide else i,
                    toc_slide_layout_index,
                )
                toc_outline = f"Table of Contents\n\n"

                for outline in presentation_outline_model.slides[
                    outline_index:outlines_to
                ]:
                    page_number = (
                        outline_index - i + n_toc_slides + 1
                        if presentation.include_title_slide
                        else outline_index - i + n_toc_slides
                    )
                    toc_outline += f"Slide page number: {page_number}\n Slide Content: {outline.content[:100]}\n\n"
                    outline_index += 1

                outline_index += 1

                presentation_outline_model.slides.insert(
                    i + 1 if presentation.include_title_slide else i,
                    SlideOutlineModel(
                        content=toc_outline,
                    ),
                )

    sql_session.add(presentation)
    presentation.presentation_model = model
    presentation.image_model = image_model
    presentation.outlines = presentation_outline_model.model_dump(mode="json")
    presentation.title = title or presentation.title
    presentation.set_layout(layout)
    presentation.set_structure(presentation_structure)
    await sql_session.commit()

    return presentation

async def add_reference_markers(presentation: PresentationModel, slides,api_key: str):
    tavily_search_results_json = presentation.get_tavily_search_results_json()
    search_content_map = tavily_search_results_json
    source_embeddings,source_ids,source_contents,source_map = await citations_instance.get_source_embeddings_map(search_content_map,api_key)
    # source_embeddings=[]  
    reference_markers = []
    slide_index=1
    for  slide in slides:
        slide_content = slide.content
        slide_title = slide_content.get("title", "")  
        reference_marker_index = await get_reference_marker(slide_title, source_embeddings,api_key)
        if reference_marker_index != 0:
            reference_markers.append({"slide_index":slide_index,"content":slide_title,"reference_marker_index":reference_marker_index})
        slide_description = slide_content.get("bulletPoints") if "bulletPoints" in slide_content else slide_content.get("description", "")
        if slide_description:
            reference_marker_index = await get_reference_marker(str(slide_description), source_embeddings,api_key)
            if reference_marker_index != 0:
                reference_markers.append({"slide_index":slide_index,"content":str(slide_description),"reference_marker_index":reference_marker_index})

        bulletPoints = slide_description if isinstance(slide_description, list) else slide_content.get("bulletPoints", [])
        for bulletPoint in bulletPoints:
            bulletPoint_title = bulletPoint.get("title", "")
            reference_marker_index = await get_reference_marker(bulletPoint_title, source_embeddings,api_key)
            if reference_marker_index!=0:
                reference_markers.append({"slide_index":slide_index,"content":bulletPoint_title,"reference_marker_index":reference_marker_index})
            bulletPoint_description = bulletPoint.get("description", "")
            reference_marker_index = await get_reference_marker(bulletPoint_description, source_embeddings,api_key)
            if reference_marker_index!=0:
                reference_markers.append({"slide_index":slide_index,"content":bulletPoint_description,"reference_marker_index":reference_marker_index})
        slide_index+=1
    return reference_markers

async def get_reference_marker(content: str,  source_embeddings:[],api_key: str):
    reference_marker_index =0
    if content:
        similar_indexes, cosine_similarities, distances = await citations_instance.calculate_sentence_similarity(content, source_embeddings,api_key)
        similarity_score = float(cosine_similarities[similar_indexes.index(similar_indexes[0])])
        if similarity_score > 0.0001:
                reference_marker_index=similar_indexes[0]
        # reference_marker_index=random.randint(1,5)
    return reference_marker_index

@PRESENTATION_ROUTER.get("/stream/{id}", response_model=PresentationWithSlides)
async def stream_presentation(
    id: uuid.UUID,
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user),
    api_key: str = Depends(get_current_api_key),
):
    """
    流式返回演示文稿生成过程
    
    参数:
        id: 演示文稿唯一标识符
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID
    
    返回:
        流式响应，包含演示文稿生成过程和最终结果
    
    异常:
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限访问该演示文稿
        HTTPException 400: 演示文稿未准备好或大纲为空
    """
    # 检查演示文稿是否存在
    presentation = await sql_session.get(PresentationModel, id)
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to access this presentation")
    # 检查演示文稿是否已准备好
    if not presentation.structure:
        raise HTTPException(
            status_code=400,
            detail="Presentation not prepared for stream",
        )
    # 检查大纲是否为空
    if not presentation.outlines:
        raise HTTPException(
            status_code=400,
            detail="Outlines can not be empty",
        )

    # 图片生成服务
    image_generation_service = ImageGenerationService(
        output_directory=get_images_directory(), 
        api_key=api_key, 
        model=presentation.image_model,
    )

    async def inner():
        structure = presentation.get_structure()
        layout = presentation.get_layout()
        outline = presentation.get_presentation_outline()

        async_assets_generation_tasks = []

        slides: List[SlideModel] = []
        yield SSEResponse(
            event="response",
            data=json.dumps({"type": "chunk", "chunk": '{ "slides": [ '}),
        ).to_string()
        for i, slide_layout_index in enumerate(structure.slides):
            slide_layout = layout.slides[slide_layout_index]

            try:
                slide_content = await get_slide_content_from_type_and_outline(
                    slide_layout=slide_layout,
                    outline=outline.slides[i],
                    language=presentation.language,
                    api_key=api_key,
                    model=presentation.presentation_model,
                    tone=presentation.tone,
                    verbosity=presentation.verbosity,
                    instructions=presentation.instructions,
                )
            except HTTPException as e:
                yield SSEErrorResponse(detail=e.detail).to_string()
                return

            slide = SlideModel(
                presentation=id,
                layout_group=layout.name,
                layout=slide_layout.id,
                index=i,
                speaker_note=slide_content.get("__speaker_note__", ""),
                content=slide_content,
            )
            slides.append(slide)

            # This will mutate slide and add placeholder assets
            process_slide_add_placeholder_assets(slide)

            # This will mutate slide
            async_assets_generation_tasks.append(
                process_slide_and_fetch_assets(image_generation_service, slide)
            )

            yield SSEResponse(
                event="response",
                data=json.dumps({"type": "chunk", "chunk": slide.model_dump_json()}),
            ).to_string()

        yield SSEResponse(
            event="response",
            data=json.dumps({"type": "chunk", "chunk": " ] }"}),
        ).to_string()

        # 等待所有资产生成任务完成
        generated_assets_lists = await asyncio.gather(*async_assets_generation_tasks)
        generated_assets = []
        for assets_list in generated_assets_lists:
            generated_assets.extend(assets_list)

        # 删除旧幻灯片，生成新的
        await sql_session.execute(
            delete(SlideModel).where(SlideModel.presentation == id)
        )
        await sql_session.commit()

        sql_session.add(presentation)
        sql_session.add_all(slides)
        sql_session.add_all(generated_assets)
        await sql_session.commit()
        
        reference_markers = await add_reference_markers(presentation, slides,api_key)
        presentation.set_reference_markers(reference_markers)
        await sql_session.commit()
        logging.info(f"Reference markers: {reference_markers}")
        tavily_search_results_json = presentation.get_tavily_search_results_json()
        response = PresentationWithSlides(
            **presentation.model_dump(exclude={"reference_markers"}),
            slides=slides,
            reference_markers=reference_markers,
            webSearchResources=tavily_search_results_json,
        )

        yield SSECompleteResponse(
            key="presentation",
            value=response.model_dump(mode="json"),
        ).to_string()

    return StreamingResponse(inner(), media_type="text/event-stream")


@PRESENTATION_ROUTER.patch("/update", response_model=PresentationWithSlides)
async def update_presentation(
    id: Annotated[uuid.UUID, Body()],
    n_slides: Annotated[Optional[int], Body()] = None,
    title: Annotated[Optional[str], Body()] = None,
    slides: Annotated[Optional[List[SlideModel]], Body()] = None,
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    更新演示文稿信息
    
    参数:
        id: 演示文稿唯一标识符
        n_slides: 新的幻灯片数量（可选）
        title: 新的标题（可选）
        slides: 新的幻灯片列表（可选）
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID
    
    返回:
        更新后的演示文稿对象
    
    异常:
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限修改该演示文稿
    """
    # 检查演示文稿是否存在
    presentation = await sql_session.get(PresentationModel, id)
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to modify this presentation")

    # 更新演示文稿信息
    presentation_update_dict = {}
    if n_slides:
        presentation_update_dict["n_slides"] = n_slides
    if title:
        presentation_update_dict["title"] = title

    if n_slides or title:
        presentation.sqlmodel_update(presentation_update_dict)

    if slides:
        # 验证并更新幻灯片关联的演示文稿ID
        for slide in slides:
            slide.presentation = uuid.UUID(slide.presentation)
            slide.id = uuid.UUID(slide.id)

        await sql_session.execute(
            delete(SlideModel).where(SlideModel.presentation == presentation.id)
        )
        sql_session.add_all(slides)

    await sql_session.commit()

    return PresentationWithSlides(
        **presentation.model_dump(),
        slides=slides or [],
    )


async def preprocess_ppt_model_data(ppt_data: dict) -> dict:
    """
    预处理PPT模型数据，修复常见的验证错误
    
    参数:
        ppt_data: 原始PPT数据字典
    
    返回:
        处理后的PPT数据字典
    """
    if "slides" in ppt_data:
        for slide in ppt_data["slides"]:
            if "shapes" in slide:
                # 处理可能嵌套的shapes列表
                flattened_shapes = []
                for shape in slide["shapes"]:
                    if isinstance(shape, list):
                        flattened_shapes.extend(shape)
                    else:
                        flattened_shapes.append(shape)
                slide["shapes"] = flattened_shapes
                
                # 预处理每个形状
                for shape in slide["shapes"]:
                    # 确保shape是字典
                    if not isinstance(shape, dict):
                        continue
                    
                    # 处理autoshape类型的形状
                    if shape.get("shape_type") == "autoshape":
                        # 修复border_radius类型问题
                        if "border_radius" in shape:
                            shape["border_radius"] = int(shape["border_radius"])
                        
                        # 确保type字段是有效的MSO_AUTO_SHAPE_TYPE值
                        if "type" in shape and shape["type"] not in [1, 2, 3, 4, 5]:
                            shape["type"] = 1  # 默认使用矩形
                        
                        # 如果没有paragraphs字段，添加一个空列表
                        if "paragraphs" not in shape:
                            shape["paragraphs"] = []
                    
                    # 确保position字段是有效的
                    if "position" in shape:
                        for key in ["left", "top", "width", "height"]:
                            if key in shape["position"]:
                                shape["position"][key] = float(shape["position"][key])
    
    return ppt_data

@PRESENTATION_ROUTER.post("/export/pptx", response_model=str)
async def export_presentation_as_pptx(
    request: Request,
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    将演示文稿导出为PPTX格式
    
    参数:
        request: HTTP请求对象
    
    返回:
        导出的PPTX文件路径
    """
    # 直接从请求体获取数据，以便在验证前进行预处理
    try:
        ppt_data = await request.json()
        
        # 预处理数据
        processed_ppt_data = await preprocess_ppt_model_data(ppt_data)
        
        # 创建PPTX模型
        pptx_model = PptxPresentationModel(**processed_ppt_data)
        
        # 继续原有逻辑
        temp_dir = TEMP_FILE_SERVICE.create_temp_dir()
        pptx_creator = PptxPresentationCreator(pptx_model, temp_dir)
        await pptx_creator.create_ppt()

        export_directory = get_exports_directory()
        pptx_path = os.path.join(
            export_directory, f"{pptx_model.name or uuid.uuid4()}.pptx"
        )
        pptx_creator.save(pptx_path)

        return pptx_path
    except Exception as e:
        # 提供更详细的错误信息
        error_detail = str(e)
        if "validation" in error_detail.lower():
            # 如果是验证错误，尝试提供更有用的信息
            raise HTTPException(status_code=422, detail=f"数据验证错误: {error_detail}")
        raise HTTPException(status_code=400, detail=f"处理PPT数据时出错: {error_detail}")


@PRESENTATION_ROUTER.post("/export", response_model=PresentationPathAndEditPath)
async def export_presentation_as_pptx_or_pdf(
    id: Annotated[uuid.UUID, Body(description="Presentation ID to export")],
    export_as: Annotated[
        Literal["pptx", "pdf"], Body(description="Format to export the presentation as")
    ] = "pptx",
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    将演示文稿导出为PPTX或PDF格式
    
    参数:
        id: 要导出的演示文稿ID
        export_as: 导出格式（pptx或pdf，默认pptx）
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID
    
    返回:
        包含导出路径和编辑路径的响应
    
    异常:
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限导出该演示文稿
    """
    presentation = await sql_session.get(PresentationModel, id)

    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to export this presentation")

    presentation_and_path = await export_presentation(
        id,
        presentation.title or str(uuid.uuid4()),
        export_as,
    )

    return PresentationPathAndEditPath(
        **presentation_and_path.model_dump(),
        edit_path=f"/presentation?id={id}",
    )


async def check_if_api_request_is_valid(
    request: GeneratePresentationRequest,
    sql_session: AsyncSession = Depends(get_async_session),
) -> Tuple[uuid.UUID,]:
    """
    验证生成演示文稿请求的有效性
    
    参数:
        request: 生成演示文稿请求对象
        sql_session: 异步数据库会话
    
    返回:
        包含生成的演示文稿ID的元组
    
    异常:
        HTTPException 400: 请求无效（内容为空、幻灯片数量小于等于0、模板不存在）
    """
    presentation_id = uuid.uuid4()
    print(f"Presentation ID: {presentation_id}")

    # Making sure either content, slides markdown or files is provided
    if not (request.content or request.slides_markdown or request.files):
        raise HTTPException(
            status_code=400,
            detail="Either content or slides markdown or files is required to generate presentation",
        )

    # Making sure number of slides is greater than 0
    if request.n_slides <= 0:
        raise HTTPException(
            status_code=400,
            detail="Number of slides must be greater than 0",
        )

    # Checking if template is valid
    if request.template not in DEFAULT_TEMPLATES:
        request.template = request.template.lower()
        if not request.template.startswith("custom-"):
            raise HTTPException(
                status_code=400,
                detail="Template not found. Please use a valid template.",
            )
        template_id = request.template.replace("custom-", "")
        try:
            template = await sql_session.get(TemplateModel, uuid.UUID(template_id))
            if not template:
                raise Exception()
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail="Template not found. Please use a valid template.",
            )

    return (presentation_id,)


async def generate_presentation_handler(
    request: GeneratePresentationRequest,
    presentation_id: uuid.UUID,
    async_status: Optional[AsyncPresentationGenerationTaskModel],
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: str = Depends(get_current_user),
    api_key: str = Depends(get_current_api_key),
):
    """
    生成演示文稿的处理函数
    
    参数:
        request: 生成演示文稿请求对象
        presentation_id: 演示文稿ID
        async_status: 异步任务状态对象（可选）
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID
    
    说明:
        此函数负责处理演示文稿的生成过程，包括加载文档、生成大纲、准备演示文稿等
    """
    try:
        using_slides_markdown = False

        if request.slides_markdown:
            using_slides_markdown = True
            request.n_slides = len(request.slides_markdown)

        if not using_slides_markdown:
            additional_context = ""

            # Updating async status
            if async_status:
                async_status.message = "Generating presentation outlines"
                async_status.updated_at = datetime.now()
                sql_session.add(async_status)
                await sql_session.commit()

            if request.files:
                documents_loader = DocumentsLoader(file_paths=request.files)
                await documents_loader.load_documents()
                documents = documents_loader.documents
                if documents:
                    additional_context = "\n\n".join(documents)

            # Finding number of slides to generate by considering table of contents
            n_slides_to_generate = request.n_slides
            if request.include_table_of_contents:
                needed_toc_count = math.ceil(
                    (
                        (request.n_slides - 1)
                        if request.include_title_slide
                        else request.n_slides
                    )
                    / 10
                )
                n_slides_to_generate -= math.ceil(
                    (request.n_slides - needed_toc_count) / 10
                )

            presentation_outlines_text = ""
            async for chunk in generate_ppt_outline(
                request.content,
                n_slides_to_generate,
                '', # api key
                request.language,
                additional_context,
                request.tone.value,
                request.verbosity.value,
                request.instructions,
                request.include_title_slide,
                request.web_search,
            ):

                if isinstance(chunk, HTTPException):
                    raise chunk

                presentation_outlines_text += chunk

            try:
                presentation_outlines_json = dict(
                    dirtyjson.loads(presentation_outlines_text)
                )
            except Exception as e:
                traceback.print_exc()
                raise HTTPException(
                    status_code=400,
                    detail="Failed to generate presentation outlines. Please try again.",
                )
            presentation_outlines = PresentationOutlineModel(
                **presentation_outlines_json
            )
            total_outlines = n_slides_to_generate

        else:
            # Setting outlines to slides markdown
            presentation_outlines = PresentationOutlineModel(
                slides=[
                    SlideOutlineModel(content=slide)
                    for slide in request.slides_markdown
                ]
            )
            total_outlines = len(request.slides_markdown)

        # Updating async status
        if async_status:
            async_status.message = f"Selecting layout for each slide"
            async_status.updated_at = datetime.now()
            sql_session.add(async_status)
            await sql_session.commit()

        print("-" * 40)
        print(f"Generated {total_outlines} outlines for the presentation")

        # Parse Layouts
        layout_model = await get_layout_by_name(request.template)
        total_slide_layouts = len(layout_model.slides)

        # Generate Structure
        if layout_model.ordered:
            presentation_structure = layout_model.to_presentation_structure()
        else:
            presentation_structure: PresentationStructureModel = (
                await generate_presentation_structure(
                    presentation_outlines=presentation_outlines,
                    presentation_layout=layout_model,
                    instructions=request.instructions,
                    api_key="",
                    model={"name": "gpt-4.1"},
                    using_slides_markdown=using_slides_markdown,
                )
            )

        presentation_structure.slides = presentation_structure.slides[:total_outlines]
        for index in range(total_outlines):
            random_slide_index = random.randint(0, total_slide_layouts - 1)
            if index >= total_outlines:
                presentation_structure.slides.append(random_slide_index)
                continue
            if presentation_structure.slides[index] >= total_slide_layouts:
                presentation_structure.slides[index] = random_slide_index

        # Injecting table of contents to the presentation structure and outlines
        if request.include_table_of_contents and not using_slides_markdown:
            n_toc_slides = request.n_slides - total_outlines
            toc_slide_layout_index = select_toc_or_list_slide_layout_index(layout_model)
            if toc_slide_layout_index != -1:
                outline_index = 1 if request.include_title_slide else 0
                for i in range(n_toc_slides):
                    outlines_to = outline_index + 10
                    if total_outlines == outlines_to:
                        outlines_to -= 1

                    presentation_structure.slides.insert(
                        i + 1 if request.include_title_slide else i,
                        toc_slide_layout_index,
                    )
                    toc_outline = f"Table of Contents\n\n"

                    for outline in presentation_outlines.slides[
                        outline_index:outlines_to
                    ]:
                        page_number = (
                            outline_index - i + n_toc_slides + 1
                            if request.include_title_slide
                            else outline_index - i + n_toc_slides
                        )
                        toc_outline += f"Slide page number: {page_number}\n Slide Content: {outline.content[:100]}\n\n"
                        outline_index += 1

                    outline_index += 1

                    presentation_outlines.slides.insert(
                        i + 1 if request.include_title_slide else i,
                        SlideOutlineModel(
                            content=toc_outline,
                        ),
                    )

        # Create PresentationModel
        presentation = PresentationModel(
            id=presentation_id,
            user_id=current_user,
            content=request.content,
            n_slides=request.n_slides,
            language=request.language,
            title=get_presentation_title_from_outlines(presentation_outlines),
            outlines=presentation_outlines.model_dump(),
            layout=layout_model.model_dump(),
            structure=presentation_structure.model_dump(),
            tone=request.tone.value,
            verbosity=request.verbosity.value,
            instructions=request.instructions,
        )

        # Updating async status
        if async_status:
            async_status.message = "Generating slides"
            async_status.updated_at = datetime.now()
            sql_session.add(async_status)
            await sql_session.commit()

        image_generation_service = ImageGenerationService(
            output_directory=get_images_directory(), 
            api_key=api_key,
            model=presentation.image_model,
        )
        async_assets_generation_tasks = []

        # 7. Generate slide content concurrently (batched), then build slides and fetch assets
        slides: List[SlideModel] = []

        slide_layout_indices = presentation_structure.slides
        slide_layouts = [layout_model.slides[idx] for idx in slide_layout_indices]

        # Schedule slide content generation and asset fetching in batches of 10
        batch_size = 10
        for start in range(0, len(slide_layouts), batch_size):
            end = min(start + batch_size, len(slide_layouts))

            print(f"Generating slides from {start} to {end}")

            # Generate contents for this batch concurrently
            content_tasks = [
                get_slide_content_from_type_and_outline(
                    slide_layouts[i],
                    presentation_outlines.slides[i],
                    request.language,
                    api_key="",
                    model={"name": "gpt-4.1"},
                    tone=request.tone.value,
                    verbosity=request.verbosity.value,
                    instructions=request.instructions,
                )
                for i in range(start, end)
            ]
            batch_contents: List[dict] = await asyncio.gather(*content_tasks)

            # Build slides for this batch
            batch_slides: List[SlideModel] = []
            for offset, slide_content in enumerate(batch_contents):
                i = start + offset
                slide_layout = slide_layouts[i]
                slide = SlideModel(
                    presentation=presentation_id,
                    user_id=current_user,
                    layout_group=layout_model.name,
                    layout=slide_layout.id,
                    index=i,
                    speaker_note=slide_content.get("__speaker_note__"),
                    content=slide_content,
                )
                slides.append(slide)
                batch_slides.append(slide)

            # Start asset fetch tasks for just-generated slides so they run while next batch is processed
            asset_tasks = [
                process_slide_and_fetch_assets(image_generation_service, slide)
                for slide in batch_slides
            ]
            async_assets_generation_tasks.extend(asset_tasks)

        if async_status:
            async_status.message = "Fetching assets for slides"
            async_status.updated_at = datetime.now()
            sql_session.add(async_status)
            await sql_session.commit()

        # Run all asset tasks concurrently while batches may still be generating content
        generated_assets_list = await asyncio.gather(*async_assets_generation_tasks)
        generated_assets = []
        for assets_list in generated_assets_list:
            generated_assets.extend(assets_list)

        # 8. Save PresentationModel and Slides
        sql_session.add(presentation)
        sql_session.add_all(slides)
        sql_session.add_all(generated_assets)
        await sql_session.commit()

        if async_status:
            async_status.message = "Exporting presentation"
            async_status.updated_at = datetime.now()
            sql_session.add(async_status)

        # 9. Export
        presentation_and_path = await export_presentation(
            presentation_id, presentation.title or str(uuid.uuid4()), request.export_as
        )

        response = PresentationPathAndEditPath(
            **presentation_and_path.model_dump(),
            edit_path=f"/presentation?id={presentation_id}",
        )

        if async_status:
            async_status.message = "Presentation generation completed"
            async_status.status = "completed"
            async_status.data = response.model_dump(mode="json")
            async_status.updated_at = datetime.now()
            sql_session.add(async_status)
            await sql_session.commit()

        # Triggering webhook on success
        CONCURRENT_SERVICE.run_task(
            None,
            WebhookService.send_webhook,
            WebhookEvent.PRESENTATION_GENERATION_COMPLETED,
            response.model_dump(mode="json"),
        )

        return response

    except Exception as e:
        if not isinstance(e, HTTPException):
            traceback.print_exc()
            e = HTTPException(status_code=500, detail="Presentation generation failed")

        api_error_model = APIErrorModel.from_exception(e)

        # Triggering webhook on failure
        CONCURRENT_SERVICE.run_task(
            None,
            WebhookService.send_webhook,
            WebhookEvent.PRESENTATION_GENERATION_FAILED,
            api_error_model.model_dump(mode="json"),
        )

        if async_status:
            async_status.status = "error"
            async_status.message = "Presentation generation failed"
            async_status.updated_at = datetime.now()
            async_status.error = api_error_model.model_dump(mode="json")
            sql_session.add(async_status)
            await sql_session.commit()

        else:
            raise e


@PRESENTATION_ROUTER.post("/generate", response_model=PresentationPathAndEditPath)
async def generate_presentation_sync(
    request: GeneratePresentationRequest,
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
    api_key: str = Depends(get_current_api_key),
):
    """
    同步生成演示文稿
    
    参数:
        request: 生成演示文稿请求对象，包含演示文稿内容、幻灯片数量等参数
        sql_session: 异步数据库会话，用于数据库操作
        current_user: 当前登录用户ID（可选）
    
    返回:
        PresentationPathAndEditPath: 包含演示文稿导出路径和编辑路径的对象
    
    异常:
        HTTPException 500: 演示文稿生成失败
    """
    try:
        (presentation_id,) = await check_if_api_request_is_valid(request, sql_session)
        return await generate_presentation_handler(
            request, presentation_id, current_user, sql_session, api_key
        )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="Presentation generation failed")


@PRESENTATION_ROUTER.post(
    "/generate/async", 
    response_model=AsyncPresentationGenerationTaskModel,
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)
async def generate_presentation_async(
    request: GeneratePresentationRequest,
    background_tasks: BackgroundTasks,
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    异步生成演示文稿
    
    参数:
        request: 生成演示文稿请求对象
        background_tasks: FastAPI后台任务管理器，用于异步执行生成任务
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID（可选）
    
    返回:
        AsyncPresentationGenerationTaskModel: 异步任务状态对象，包含任务ID和当前状态
    
    异常:
        HTTPException 500: 演示文稿生成任务创建失败
    """
    try:
        (presentation_id,) = await check_if_api_request_is_valid(request, sql_session)

        async_status = AsyncPresentationGenerationTaskModel(
            status="pending",
            message="Queued for generation",
            data=None,
            user_id=current_user,
        )
        sql_session.add(async_status)
        await sql_session.commit()

        background_tasks.add_task(
            generate_presentation_handler,
            request,
            presentation_id,
            async_status=async_status,
            sql_session=sql_session,
        )
        return async_status

    except Exception as e:
        if not isinstance(e, HTTPException):
            print(e)
            e = HTTPException(status_code=500, detail="Presentation generation failed")

        raise e


@PRESENTATION_ROUTER.get(
    "/status/{id}", 
    response_model=AsyncPresentationGenerationTaskModel,
    responses={401: {"description": "Unauthorized"}, 403: {"description": "Forbidden"}}
)
async def check_async_presentation_generation_status(
    id: str = Path(description="ID of the presentation generation task"),
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    查询异步演示文稿生成任务状态
    
    参数:
        id: 演示文稿生成任务ID
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID（可选）
    
    返回:
        AsyncPresentationGenerationTaskModel: 异步任务状态对象，包含任务ID和当前状态
    
    异常:
        HTTPException 404: 任务不存在
        HTTPException 403: 无权限访问该任务状态
    """
    status = await sql_session.get(AsyncPresentationGenerationTaskModel, id)
    if not status:
        raise HTTPException(
            status_code=404, detail="No presentation generation task found"
        )
    
    # 检查用户权限
    if current_user and status.user_id and status.user_id != current_user:
        raise HTTPException(403, "You don't have permission to access this task status")
    
    return status


@PRESENTATION_ROUTER.post("/edit", response_model=PresentationPathAndEditPath)
async def edit_presentation_with_new_content(
    data: Annotated[EditPresentationRequest, Body()],
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    编辑演示文稿内容
    
    参数:
        data: 编辑演示文稿请求对象，包含演示文稿ID、幻灯片索引和新内容
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID（可选）
    
    返回:
        PresentationPathAndEditPath: 包含演示文稿导出路径和编辑路径的对象
    
    异常:
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限编辑该演示文稿
    """
    presentation = await sql_session.get(PresentationModel, data.presentation_id)
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to edit this presentation")

    slides = await sql_session.scalars(
        select(SlideModel).where(SlideModel.presentation == data.presentation_id)
    )

    new_slides = []
    slides_to_delete = []
    for each_slide in slides:
        updated_content = None
        new_slide_data = list(
            filter(lambda x: x.index == each_slide.index, data.slides)
        )
        if new_slide_data:
            updated_content = deep_update(each_slide.content, new_slide_data[0].content)
            new_slides.append(
                each_slide.get_new_slide(presentation.id, updated_content)
            )
            slides_to_delete.append(each_slide.id)

    await sql_session.execute(
        delete(SlideModel).where(SlideModel.id.in_(slides_to_delete))
    )

    sql_session.add_all(new_slides)
    await sql_session.commit()

    presentation_and_path = await export_presentation(
        presentation.id, presentation.title or str(uuid.uuid4()), data.export_as
    )

    return PresentationPathAndEditPath(
        **presentation_and_path.model_dump(),
        edit_path=f"/presentation?id={presentation.id}",
    )


@PRESENTATION_ROUTER.post("/derive", response_model=PresentationPathAndEditPath)
async def derive_presentation_from_existing_one(
    data: Annotated[EditPresentationRequest, Body()],
    sql_session: AsyncSession = Depends(get_async_session),
    current_user: Optional[str] = Depends(get_current_user),
):
    """
    从现有演示文稿派生新演示文稿
    
    参数:
        data: 编辑演示文稿请求对象，包含演示文稿ID、幻灯片索引和新内容
        sql_session: 异步数据库会话
        current_user: 当前登录用户ID（可选）
    
    返回:
        PresentationPathAndEditPath: 包含新演示文稿导出路径和编辑路径的对象
    
    异常:
        HTTPException 404: 演示文稿不存在
        HTTPException 403: 无权限派生该演示文稿
    """
    presentation = await sql_session.get(PresentationModel, data.presentation_id)
    if not presentation:
        raise HTTPException(status_code=404, detail="Presentation not found")
    
    # 检查用户权限
    if current_user and presentation.user_id and presentation.user_id != current_user:
        raise HTTPException(403, "You don't have permission to derive from this presentation")

    slides = await sql_session.scalars(
        select(SlideModel).where(SlideModel.presentation == data.presentation_id)
    )

    new_presentation = presentation.get_new_presentation()
    new_slides = []
    for each_slide in slides:
        updated_content = None
        new_slide_data = list(
            filter(lambda x: x.index == each_slide.index, data.slides)
        )
        if new_slide_data:
            updated_content = deep_update(each_slide.content, new_slide_data[0].content)
        new_slides.append(
            each_slide.get_new_slide(new_presentation.id, updated_content)
        )

    sql_session.add(new_presentation)
    sql_session.add_all(new_slides)
    await sql_session.commit()

    presentation_and_path = await export_presentation(
        new_presentation.id, new_presentation.title or str(uuid.uuid4()), data.export_as
    )

    return PresentationPathAndEditPath(
        **presentation_and_path.model_dump(),
        edit_path=f"/presentation?id={new_presentation.id}",
    )
