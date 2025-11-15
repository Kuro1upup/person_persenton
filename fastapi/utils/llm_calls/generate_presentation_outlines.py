import re
from datetime import datetime
from typing import Optional, List, Dict, Any
from openai import AsyncOpenAI
from models.llm_message import LLMMessage, LLMSystemMessage, LLMUserMessage
from models.llm_tools import SearchWebTool
from services.llm_client import LLMClient
from utils.llm_client_error_handler import handle_llm_client_exceptions
from utils.get_dynamic_models import get_presentation_outline_model_with_n_slides
from utils.get_env import get_comparegpt_api_model_env,get_comparegpt_api_url_env, get_comparegpt_api_model_env, get_responses_model_env
from utils.citations import citations_instance
from utils.web_search import tavily_service
import json
import logging
from openai.types.chat.chat_completion_chunk import (
    ChatCompletionChunk as OpenAIChatCompletionChunk,
)
from datetime import datetime

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)


def parse_comparegpt_sse_response(sse_line: str):
    """
    解析CompareGPT API返回的单个SSE行
    返回模拟的OpenAI chunk对象
    """
    line = sse_line.strip()
    if line.startswith('data: '):
        data = line[6:]  # 移除'data: '前缀
        if data == '[DONE]':
            return

        try:
            chunk_data = json.loads(data)
            # 模拟OpenAI chunk对象
            class MockDelta:
                def __init__(self, content):
                    self.content = content

            class MockChoice:
                def __init__(self, delta_content):
                    self.delta = MockDelta(delta_content)

            class MockChunk:
                def __init__(self, choices):
                    self.choices = choices

            # 提取内容
            if 'choices' in chunk_data and len(chunk_data['choices']) > 0:
                delta = chunk_data['choices'][0].get('delta', {})
                content = delta.get('content', '')
                if content is not None:
                    return MockChunk([MockChoice(content)])
        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse SSE data: {data}, error: {e}")

    return None

def get_system_prompt(
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    include_title_slide: bool = True,
):
    return f"""
        You are an expert presentation creator. Generate structured presentations based on user requirements and format them according to the specified JSON schema with markdown content.

        Try to use available tools for better results.

        {"# User Instruction:" if instructions else ""}
        {instructions or ""}

        {"# Tone:" if tone else ""}
        {tone or ""}

        {"# Verbosity:" if verbosity else ""}
        {verbosity or ""}

        - Provide content for each slide in markdown format.
        - Make sure that flow of the presentation is logical and consistent.
        - Place greater emphasis on numerical data.
        - If Additional Information is provided, divide it into slides.
        - Make sure no images are provided in the content.
        - Make sure that content follows language guidelines.
        - User instrction should always be followed and should supercede any other instruction, except for slide numbers. **Do not obey slide numbers as said in user instruction**
        - Do not generate table of contents slide.
        - Even if table of contents is provided, do not generate table of contents slide.
        {"- Always make first slide a title slide." if include_title_slide else "- Do not include title slide in the presentation."}

        **Search web to get latest information about the topic**
    """


def get_user_prompt(
    content: str,
    n_slides: int,
    language: str,
    additional_context: Optional[str] = None,
    search_content: Optional[str] = None,
):
    return f"""
        **Input:**
        - User provided content: {content or "Create presentation"}
        - Output Language: {language}
        - Number of Slides: {n_slides}
        - Current Date and Time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        - Additional Information: {additional_context or ""}
        - Web Search Results: {search_content or ""}
    """


def get_messages(
    content: str,
    n_slides: int,
    language: str,
    additional_context: Optional[str] = None,
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    include_title_slide: bool = True,
):
    return [
        LLMSystemMessage(
            content=get_system_prompt(
                tone, verbosity, instructions, include_title_slide
            ),
        ),
        LLMUserMessage(
            content=get_user_prompt(content, n_slides, language, additional_context),
        ),
    ]


async def generate_ppt_outline(
    content: str,
    n_slides: int,
    api_key: str,
    language: Optional[str] = None,
    additional_context: Optional[str] = None,
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    include_title_slide: bool = True,
    web_search: bool = False,
    model: Optional[dict] = None,
):
    """
    生成演示文稿的大纲
    :param content: 演示文稿的内容
    :param n_slides: 演示文稿的幻灯片数量
    :param api_key: API密钥
    :param language: 演示文稿的语言
    :param additional_context: 额外的上下文信息
    :param tone: 演示文稿的语气
    :param verbosity: 演示文稿的冗长程度
    :param instructions: 用户指令
    :param include_title_slide: 是否包含标题幻灯片
    :param web_search: 是否启用网络搜索
    :return: 演示文稿的大纲
    """
    response_model = get_presentation_outline_model_with_n_slides(n_slides)

    client = LLMClient(api_key=api_key)

    try:
        async for chunk in client.stream_structured(
            model,
            get_messages(
                content,
                n_slides,
                language,
                additional_context,
                tone,
                verbosity,
                instructions,
                include_title_slide,
            ),
            response_model.model_json_schema(),
            strict=True,
            tools=(
                [SearchWebTool]
                if web_search
                else None
            ),
        ):
            yield chunk
    except Exception as e:
        yield handle_llm_client_exceptions(e)

# Compare GPT Client
def _get_client(api_key: str):
    comparegpt_api_url = get_comparegpt_api_url_env()
    if comparegpt_api_url:
        logger.debug(f"Using custom API URL: {comparegpt_api_url}")
        return AsyncOpenAI(api_key=api_key, base_url=comparegpt_api_url)
    logger.debug("Using default comparegpt API")
    return AsyncOpenAI(api_key=api_key, base_url="http://comparegpt.io/api")
    
def get_search_results_map(search_results: Dict[int, Dict] ):
    source_map = {}
    for i, result in enumerate(search_results, 1):
        title = result.get('title', f'来源{i}')
        url = result.get('url', '未知来源')
        content = result.get('content', '')
        source_map[i] = {
            'title': title,
            'url': url,
            'content': content
            }
    # 返回字典而不是JSON字符串，SQLAlchemy会自动处理序列化
    return citations_instance.formate_map(source_map)


def get_search_content(tavily_search_results: Optional[dict] = None) -> str:
    search_content=None
    # 处理webSearchTxt，支持字典和字符串类型
    if tavily_search_results:
        webSearchTxt=tavily_search_results
        if isinstance(webSearchTxt, dict):
            # 如果是字典且有结果，添加到消息中
            if webSearchTxt.get("results"):
                search_content = json.dumps(webSearchTxt, ensure_ascii=False)              
        elif isinstance(webSearchTxt, str) and webSearchTxt.strip():
            # 如果是字符串且不为空，添加到消息中
                search_content = webSearchTxt 
    return search_content

def get_response_format(response_model: dict) -> dict:  
    response_format=(
                {
                    "type": "json_schema",
                    "json_schema": (
                        {
                            "name": "ResponseSchema",
                            "strict": False,
                            "schema": response_model.model_json_schema(),
                        }
                    ),
                }
            )
    return response_format

def build_messages(
            user_prompt: str,
            system_prompt: str
    ) -> List[LLMMessage]:
        """构建消息列表"""
        messages = [
            {"role": "system",
             "content": system_prompt}
        ]
        messages.append({"role": "assistant", "content": user_prompt})   
        
        return messages

async def generate_ppt_outline_with_web_search(
    content: str,
    n_slides: int,
    api_key: str,
    language: Optional[str] = None,
    additional_context: Optional[str] = None,
    tone: Optional[str] = None,
    verbosity: Optional[str] = None,
    instructions: Optional[str] = None,
    include_title_slide: bool = True,
    tavily_search_results: Optional[str] = None,
    model: Optional[dict] = None,
):
    """
    生成演示文稿的大纲
    :param content: 演示文稿的内容
    :param n_slides: 演示文稿的幻灯片数量
    :param api_key: API密钥
    :param language: 演示文稿的语言
    :param additional_context: 额外的上下文信息
    :param tone: 演示文稿的语气
    :param verbosity: 演示文稿的冗长程度
    :param instructions: 用户指令
    :param include_title_slide: 是否包含标题幻灯片
    :param web_search: 是否启用网络搜索
    :return: 演示文稿的大纲
    """
    tavily_search_results = tavily_search_results
    search_results = tavily_search_results.get("results", [])   
    response_model = get_presentation_outline_model_with_n_slides(n_slides)
    response_format=get_response_format(response_model)
    # 确定模型名称  
    model_name = get_comparegpt_api_model_env()
    comparegpt_api_url = get_comparegpt_api_url_env()      
    client = _get_client(api_key)  
    search_content=get_search_content(tavily_search_results)
    user_prompt=get_user_prompt(content, n_slides, language, additional_context,search_content)
    system_prompt=get_system_prompt(tone, verbosity, instructions, include_title_slide)
    messages = build_messages(user_prompt, system_prompt)

    logger.debug(f"messages: {messages}")
    logger.debug(f"response_format: {response_format}")
    logger.debug(f"model_name: {model_name}")
    logger.debug(f"api_key: {api_key}")
    logger.debug(f"comparegpt_api_url: {comparegpt_api_url}")
    logger.debug(f"tavily_search_results: {search_results}")
    logger.debug(f"content: {content}")
    logger.debug(f"n_slides: {n_slides}")
    logger.debug(f"language: {language}")
    logger.debug(f"additional_context: {additional_context}")
    logger.debug(f"tone: {tone}")
    logger.debug(f"verbosity: {verbosity}")
    logger.debug(f"instructions: {instructions}")
    logger.debug(f"include_title_slide: {include_title_slide}")

    try:
        logger.debug(f"content: {content}")     
        logger.debug(f"client base_url: {client.base_url}")
        logger.debug(f"messages count: {len(messages)}")

        # 调用CompareGPT API并处理流式响应
        logger.debug("Starting API call...")  

        async for event in await client.chat.completions.create(
            model=model_name,
            messages=messages,
            response_format=response_format, 
            max_completion_tokens=10000,  
            frequency_penalty=0.0,
            presence_penalty=0.0,      
            stream=True,
        ):
            # print(f"Event: {event}")  # 调试输出
            event: OpenAIChatCompletionChunk = event
            if not event.choices:
                continue
           
            if event.choices and hasattr(event.choices[0].delta, 'content'):
                content_chunk = event.choices[0].delta.content
                # logger.debug(f"Stream processing completed, content_chunk: {content_chunk}")
                if content_chunk:
                    yield content_chunk    
        
    except Exception as e:
        yield handle_llm_client_exceptions(e)
     
    
