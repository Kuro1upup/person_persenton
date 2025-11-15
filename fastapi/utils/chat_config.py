from pydantic import BaseModel, ConfigDict, Field
from typing import List, Optional

class ChatConfig(BaseModel):
    """对话过程使用参数"""
    enable_debug_info: bool = Field(default=True, description="是否启用调试信息")
    enable_question_recommend: bool = Field(default=False, description="是否启用问题推荐")
    llm_name: str = Field(default=None, description="使用的语言模型名称")
    topic_prompt: str | None = Field(default="", description="主题提示词")
    knowledge_ids: list[str] = Field(default_factory=list, description="知识库id")
    enable_multi_round_qa: bool = Field(default=False, description="是否开启多轮问答")

    @property
    def effective_llm_names(self) -> List[str]:
        """获取实际使用的LLM名称列表"""
        return [name.strip() for name in self.llm_name.split(",")]