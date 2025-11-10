import logging
from typing import List, Optional, Dict, Any
from tavily import AsyncTavilyClient
from utils.get_env import get_tavily_api_key_env


logger = logging.getLogger(__name__)

class TavilySearchService:
    def __init__(self, api_key: Optional[str] = None):
        self.client = AsyncTavilyClient(api_key="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")

    async def search(
        self,
        query: str,
        include_domains: Optional[List[str]] = None,
        max_results: int = 5,
    ) -> Dict[str, Any]:
        
        if include_domains is None:
            include_domains = []

        # reference to https://docs.tavily.com/sdk/python/reference
        if max_results < 1:
            max_results = 1
        elif max_results > 20:
            max_results = 20

        web_response = await self.client.search(
            query=query,
            include_domains=include_domains,
            max_results=max_results
        )       

        return web_response

    
# 👇 全局共享实例（并发安全）
tavily_service = TavilySearchService()