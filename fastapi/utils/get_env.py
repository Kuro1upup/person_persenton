import os


import os
import sys
from pathlib import Path

def get_can_change_keys_env():
    return os.getenv("CAN_CHANGE_KEYS")


def get_database_url_env():
    # 优先使用环境变量中的DATABASE_URL
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        return database_url
    
    # 如果没有设置环境变量，回退到SQLite
    app_data_dir = get_app_data_directory_env()
    if app_data_dir:
        return f"sqlite:///{os.path.join(app_data_dir, 'fastapi.db')}"
    # 默认使用当前目录下的app_data
    return "sqlite:///app_data/fastapi.db"


def get_app_data_directory_env():
    # 尝试从环境变量获取
    app_data_dir = os.getenv("APP_DATA_DIRECTORY")
    if app_data_dir:
        return app_data_dir
    
    # 如果没有设置环境变量，使用相对路径
    # 获取当前脚本所在目录
    current_dir = os.path.dirname(os.path.abspath(__file__))
    # 上两级目录（servers/fastapi/utils -> servers）
    servers_dir = os.path.dirname(os.path.dirname(current_dir))
    # 在servers目录下创建app_data目录
    default_app_data = os.path.join(servers_dir, "app_data")
    
    # 确保目录存在
    os.makedirs(default_app_data, exist_ok=True)
    return default_app_data


def get_temp_directory_env():
    return os.getenv("TEMP_DIRECTORY")


def get_user_config_path_env():
    return os.getenv("USER_CONFIG_PATH")


def get_llm_provider_env():
    return "openai"


def get_anthropic_api_key_env():
    return os.getenv("ANTHROPIC_API_KEY")


def get_anthropic_model_env():
    return os.getenv("ANTHROPIC_MODEL")


def get_ollama_url_env():
    return os.getenv("OLLAMA_URL")


def get_custom_llm_url_env():
    return os.getenv("CUSTOM_LLM_URL")


def get_comparegpt_api_url_env():
    return os.getenv("COMPAREGPT_API_URL")

def get_comparegpt_api_model_env():
    """
    获取Compare GPT API模型环境变量
    """
    compare_gpt_api_model = os.getenv("COMPAREGPT_API_MODEL")
    if not compare_gpt_api_model:
        return "gpt-4.1"
    return compare_gpt_api_model

def get_comparegpt_image_api_model_env():
    """
    获取Compare GPT图像生成API模型环境变量
    """
    compare_gpt_image_api_model = os.getenv("COMPAREGPT_IMAGE_API_MODEL")
    if not compare_gpt_image_api_model:
        return "gemini-2.5-flash-image-preview"
    return compare_gpt_image_api_model

def get_responses_model_env():
    """
    获取Compare GPT responses接口模型
    """
    responses_model = os.getenv("COMPAREGPT_RESPONSES_MODEL")
    if not responses_model:
        return "gpt-5-mini"
    return responses_model

def get_jwt_token_secret_key_env():
    return os.getenv("JWT_TOKEN_SECRET_KEY")

def get_openai_api_key_env():
    return os.getenv("OPENAI_API_KEY")


def get_openai_model_env():
    return os.getenv("OPENAI_MODEL")


def get_google_api_key_env():
    return os.getenv("GOOGLE_API_KEY")


def get_google_model_env():
    return os.getenv("GOOGLE_MODEL")


def get_custom_llm_api_key_env():
    return os.getenv("CUSTOM_LLM_API_KEY")


def get_ollama_model_env():
    return os.getenv("OLLAMA_MODEL")


def get_custom_model_env():
    return os.getenv("CUSTOM_MODEL")


def get_pexels_api_key_env():
    return os.getenv("PEXELS_API_KEY")


def get_image_provider_env():
    return os.getenv("IMAGE_PROVIDER")


def get_pixabay_api_key_env():
    return os.getenv("PIXABAY_API_KEY")


def get_tool_calls_env():
    return os.getenv("TOOL_CALLS")


def get_disable_thinking_env():
    return os.getenv("DISABLE_THINKING")


def get_extended_reasoning_env():
    return os.getenv("EXTENDED_REASONING")


def get_web_grounding_env():
    return os.getenv("WEB_GROUNDING")


def get_tavily_api_key_env():
    return os.getenv("TAVILY_API_KEY")


