import asyncio
import os
import aiohttp
from openai import api_key
from models.image_prompt import ImagePrompt
from models.sql.image_asset import ImageAsset
from utils.download_helpers import download_file
from utils.get_env import get_comparegpt_api_url_env, get_comparegpt_image_api_model_env
import uuid
import base64

class ImageGenerationService:
    
    def __init__(self, output_directory: str, api_key: str, model: dict):
        """初始化图像生成服务
        
        Args:
            output_directory (str): 生成图像的输出目录
            api_key (str): API密钥
            model (dict): 模型配置，包含模型名称
        """
        self.output_directory = output_directory
        self.api_key = api_key
        if model is None or "name" not in model or not model["name"]:
            model = {"name": get_comparegpt_image_api_model_env()}
        self.model = model
        self.api_url = get_comparegpt_api_url_env()

    # TODO:适配Compare GPT生成图片
    async def generate_image(self, prompt: ImagePrompt) -> str | ImageAsset:
        """根据提供的提示词生成图像
        
        - 如果没有可用的图像生成函数，则返回占位符图像
        - 如果选择了库存提供商，则直接使用提示词，否则使用包含主题的完整图像提示词
        - 输出目录用于保存生成的图像，不用于库存提供商
        
        Args:
            prompt (ImagePrompt): 图像提示词对象
        
        Returns:
            str | ImageAsset: 图像路径或ImageAsset对象，如果发生错误则返回占位符图像路径
        """

        # TODO:暂时使用默认不包含主题的提示词
        image_prompt = prompt.get_image_prompt(
            with_theme=False
        )
        print(f"Request - Generating Image for {image_prompt}")

        try:
            # image_path = await self._generate_image_google(image_prompt, self.output_directory)
            image_path = "/static/images/placeholder.jpg"
            print(f"Generated Image Path: {image_path}")
            if image_path:
                if image_path.startswith("http"):
                    return image_path
                elif os.path.exists(image_path):
                    return ImageAsset(
                        path=image_path,
                        is_uploaded=False,
                        extras={
                            "prompt": prompt.prompt,
                            "theme_prompt": prompt.theme_prompt,
                        },
                    )
            raise Exception(f"Image not found at {image_path}")

        except Exception as e:
            print(f"Error generating image: {e}")
            return "/static/images/placeholder.jpg"

    async def _generate_image_google(self, prompt: str, output_directory: str) -> str:
        """使用Google的Gemini模型生成图像
        
        Args:
            prompt (str): 图像生成提示词
            output_directory (str): 保存生成图像的目录
        
        Returns:
            str: 生成的图像文件路径
        """
        async with aiohttp.ClientSession() as session:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
            }
            payload = {
                "model": self.model["name"],
                "prompt": prompt,
            }
            try:
                async with session.post(
                    f"{self.api_url}/images/generations",
                    json=payload,
                    headers=headers,
                ) as response:
                    print(f"Response Status: {response.status}")
                    if response.status != 200:
                        return "/static/images/placeholder.jpg"
                    result = await response.json()
                    for idx, choice in enumerate(result["choices"]):
                        contents = choice["message"]["content"]
                        if not contents:
                            continue
                        for part in contents:
                            if part["type"] == "text":
                                print(part["text"])
                            elif part["type"] == "image_url":
                                image_data = part["image_url"]["url"]
                                if image_data.startswith("data:") and "," in image_data:
                                    header, encoded = image_data.split(",", 1)
                                    image_path = os.path.join(output_directory, f"{uuid.uuid4()}.jpg")
                                    with open(image_path, "wb") as f:
                                        f.write(base64.b64decode(encoded))
                                else:
                                    image_path = await download_file(image_data, output_directory)
                    return image_path
            except Exception as e:
                print(f"Error generating image: {e}")
                return "/static/images/placeholder.jpg"