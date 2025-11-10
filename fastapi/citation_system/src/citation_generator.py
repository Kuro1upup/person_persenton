"""引用生成核心模块"""
import logging
import json
from typing import List, Dict, Tuple
from datetime import datetime
from dataclasses import dataclass, asdict

from src.retriever import ColBERTRetriever
from src.highlighter import TokenHighlighter, ExplanationGenerator

logger = logging.getLogger(__name__)

@dataclass
class Citation:
    """引用信息"""
    document_id: str
    document_text: str
    query: str
    score: float
    highlighted_text: str
    matches: List[Dict]
    match_rate: float
    explanation: str
    context_windows: List[Dict]
    document_url: str = ""  # 添加 URL 字段
    original_document_id: str = ""  # 添加原始文档 ID 字段
    timestamp: str = None
    
    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
    
    def to_dict(self) -> Dict:
        return asdict(self)
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

class CitationGenerator:
    """引用生成器"""
    
    def __init__(self):
        """初始化"""
        self.retriever = ColBERTRetriever()
        logger.info("CitationGenerator initialized")
    
    def generate_citations(
        self,
        query: str,
        k: int = 3,
        include_explanation: bool = True
    ) -> List[Citation]:
        """
        为查询生成引用
        
        Args:
            query: 查询语句
            k: 返回引用数量
            include_explanation: 是否包含详细解释
        
        Returns:
            引用列表
        """
        logger.info(f"Generating citations for query: {query}")
        
        # 检索文档
        results = self.retriever.retrieve_with_explanations(query, k=k)
        
        citations = []
        for result in results:
            doc_id = result["doc_id"]
            original_doc_id = result.get("doc_id", "")  # 原始文档 ID
            document = result["text"]
            document_url = result.get("url", "")  # 获取 URL，如果没有则为空字符串
            score = result["score"]

            # 高亮
            highlight_info = TokenHighlighter.highlight_matches(query, document)

            # 生成解释
            if include_explanation:
                explanation_info = ExplanationGenerator.generate_explanation(
                    query, document, score
                )
            else:
                explanation_info = {
                    "summary": "",
                    "context_windows": []
                }

            # 创建引用对象
            citation = Citation(
                document_id=doc_id,
                document_text=document,
                document_url=document_url,  # 添加 URL
                original_document_id=original_doc_id,  # 添加原始文档 ID
                query=query,
                score=score,
                highlighted_text=highlight_info["highlighted"],
                matches=highlight_info["matches"],
                match_rate=highlight_info["match_rate"],
                explanation=explanation_info.get("summary", ""),
                context_windows=explanation_info.get("context_windows", [])
            )
            
            citations.append(citation)
        
        logger.info(f"Generated {len(citations)} citations")
        return citations
    
    def generate_citations_for_sentence(
        self,
        sentence: str,
        document_context: str = "",
        k: int = 1
    ) -> Citation:
        """
        为单个句子生成引用
        
        Args:
            sentence: 句子文本
            document_context: 文档上下文（可选）
            k: 返回最佳引用
        
        Returns:
            最佳引用
        """
        logger.debug(f"Generating citation for sentence: {sentence}")
        
        # 组合查询
        query = f"{document_context} {sentence}".strip()
        
        # 生成引用
        citations = self.generate_citations(query, k=k, include_explanation=True)
        
        if citations:
            return citations[0]
        else:
            return None
    
    def batch_generate_citations(
        self,
        queries: List[str],
        k: int = 3
    ) -> Dict[str, List[Citation]]:
        """
        批量生成引用
        
        Args:
            queries: 查询列表
            k: 每个查询的引用数量
        
        Returns:
            {query: [citations]}
        """
        logger.info(f"Batch generating citations for {len(queries)} queries")
        
        results = {}
        for query in queries:
            results[query] = self.generate_citations(query, k=k)
        
        return results

class CitationFormatter:
    """引用格式化器"""
    
    @staticmethod
    def format_as_markdown(citation: Citation) -> str:
        """格式化为 Markdown"""
        # 使用原始文档 ID（如果有的话）
        display_id = citation.original_document_id if citation.original_document_id else citation.document_id

        md = f"""
## 引用

**文档 ID:** {display_id}

**文档 URL:** {citation.document_url if citation.document_url else "N/A"}

**相关性分数:** {citation.score:.4f}

**匹配率:** {citation.match_rate:.1%}

### 文档内容

> {citation.document_text}

### 高亮匹配

{citation.highlighted_text}

### 解释

{citation.explanation}

### 匹配详情

| 匹配 Token | 相似度 |
|-----------|--------|
"""
        for match in citation.matches:
            md += f"| {match['text']} | {match['score']:.2%} |\n"

        if citation.context_windows:
            md += "\n### 上下文窗口\n\n"
            for i, window in enumerate(citation.context_windows, 1):
                md += f"{i}. {window['highlighted']}\n"

        return md
    
    @staticmethod
    def format_as_html(citation: Citation) -> str:
        """格式化为 HTML"""
        # 使用原始文档 ID（如果有的话）
        display_id = citation.original_document_id if citation.original_document_id else citation.document_id

        html = f"""
<div class="citation">
    <div class="citation-header">
        <span class="doc-id">文档 {display_id}</span>
        <span class="doc-url">URL: {citation.document_url if citation.document_url else "N/A"}</span>
        <span class="score">相关性: {citation.score:.4f}</span>
    </div>

    <div class="citation-content">
        <p>{citation.highlighted_text}</p>
    </div>

    <div class="citation-explanation">
        <p>{citation.explanation}</p>
    </div>

    <div class="citation-matches">
        <h4>匹配详情</h4>
        <ul>
"""
        for match in citation.matches:
            html += f'<li>{match["text"]} ({match["score"]:.1%})</li>\n'

        html += """
        </ul>
    </div>
</div>
"""
        return html
    
    @staticmethod
    def format_as_json(citations: List[Citation]) -> str:
        """格式化为 JSON"""
        return json.dumps(
            [c.to_dict() for c in citations],
            ensure_ascii=False,
            indent=2
        )

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    generator = CitationGenerator()
    
    # 测试查询
    query = "如何重置密码"
    citations = generator.generate_citations(query, k=3)
    
    print(f"\n查询：{query}\n")
    for i, citation in enumerate(citations, 1):
        print(f"引用 {i}:")
        print(CitationFormatter.format_as_markdown(citation))
        print("\n" + "="*50 + "\n")
