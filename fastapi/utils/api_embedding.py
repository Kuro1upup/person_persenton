import logging
import os
import re
from openai import AsyncOpenAI
import asyncio
from dotenv import load_dotenv
from utils.get_env import get_comparegpt_api_url_env
# 加载.env文件
load_dotenv()

logger = logging.getLogger(__name__)

class EmbeddingModel:
    def __init__(self):
        # 使用环境变量中的OpenAI API密钥
        # openai_api_key = os.getenv("OPENAI_API_KEY")
        # if not openai_api_key:
        #     logger.error("OPENAI_API_KEY environment variable not set")
        #     raise ValueError("OPENAI_API_KEY environment variable is required")
       
        self.model = "text-embedding-3-small"    
    
    async def get_embedding(self, text, api_key: str):
        # 处理文本，确保不为空，并转换为字符串
        if text is None:
            logger.warning("None text provided for embedding")
            return []

        # 转换为字符串
        if not isinstance(text, str):
            text = str(text)

        # 处理文本，确保不为空
        if not text or not text.strip():
            logger.warning("Empty text provided for embedding")
            return []

        client = AsyncOpenAI(
            base_url=get_comparegpt_api_url_env(),
            api_key=api_key
        )

        # 尝试使用原始文本
        try:
            response = await client.embeddings.create(
                model=self.model,
                input=text
            )

            # 提取embedding数据
            if hasattr(response, 'data') and response.data:
                return response.data[0].embedding
            else:
                logger.warning("No embedding data found in response for text")
                # 尝试清理文本后重试
                cleaned_text = self._clean_text_for_embedding(text)
                if cleaned_text != text:
                    logger.info("Retrying with cleaned text")
                    return await self._get_embedding_with_fallback(cleaned_text, client)
                return []

        except Exception as e:
            logger.warning(f"Embedding failed for original text: {str(e)}")
            # 尝试清理文本后重试
            cleaned_text = self._clean_text_for_embedding(text)
            if cleaned_text != text:
                logger.info("Retrying with cleaned text after error")
                try:
                    return await self._get_embedding_with_fallback(cleaned_text, client)
                except Exception as e2:
                    logger.error(f"Embedding failed even with cleaned text: {str(e2)}")
            return []

    def _clean_text_for_embedding(self, text: str) -> str:
        """清理文本以适应嵌入API的限制"""
        if not text:
            return text

        # 对于CompareGPT API，可能需要限制文本长度
        # 移除过长的文本（保留前500个字符）
        if len(text) > 500:
            text = text[:500] + "..."

        return text

    async def _get_embedding_with_fallback(self, text: str, client: AsyncOpenAI) -> list:
        """使用清理后的文本获取嵌入的辅助方法"""
        response = await client.embeddings.create(
            model=self.model,
            input=text
        )

        if hasattr(response, 'data') and response.data:
            return response.data[0].embedding

        logger.error("No embedding data found in fallback response")
        return []   

    
# if __name__ == "__main__":


#     print("\n尝试实际API调用 (需要设置OPENAI_API_KEY):")
#     async def test():
#         try:
#             model = EmbeddingModel()

#             # 获取embedding向量（只返回向量数据）
#             embeddings = await model.get_embedding("Hello, world!")
#             print(f"Embedding result: {embeddings}")

#         except Exception as e:
#             print(f"Test failed: {e}")
#             print("Note: Make sure OPENAI_API_KEY is set in your environment variables")

#     asyncio.run(test())


