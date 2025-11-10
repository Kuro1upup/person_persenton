"""Token 级高亮与匹配解释"""
import json
import logging
from typing import List, Dict, Tuple
import difflib
import warnings

# 抑制 jieba 的 pkg_resources 弃用警告
warnings.filterwarnings('ignore', message='pkg_resources is deprecated', category=UserWarning, module='jieba')

import jieba

logger = logging.getLogger(__name__)

class TokenHighlighter:
    """Token 级高亮器"""

    @staticmethod
    def _tokenize_text(text: str) -> List[str]:
        """智能分词：对中文使用jieba，对英文使用空格分割"""
        # 检查是否包含中文字符
        if any('\u4e00' <= char <= '\u9fff' for char in text):
            # 中文文本，使用jieba分词
            return list(jieba.cut(text))
        else:
            # 英文文本，使用空格分割
            return text.split()

    @staticmethod
    def highlight_matches(query: str, document: str, min_length: int = 3) -> Dict:
        """
        高亮查询与文档中的匹配 token
        
        Args:
            query: 查询语句
            document: 文档文本
            min_length: 最小匹配长度
        
        Returns:
            高亮信息 {
                "original": str,
                "highlighted": str,
                "matches": [{"text": str, "position": int, "score": float}, ...]
            }
        """
        query_tokens = TokenHighlighter._tokenize_text(query)
        doc_tokens = TokenHighlighter._tokenize_text(document)
        
        matches = []
        highlighted_positions = set()
        
        # 找所有匹配
        for q_token in query_tokens:
            q_token_lower = q_token.lower()

            for i, d_token in enumerate(doc_tokens):
                d_token_lower = d_token.lower()

                # 精确匹配
                if q_token_lower == d_token_lower:
                    similarity = 1.0
                # 部分匹配
                elif q_token_lower in d_token_lower:
                    similarity = len(q_token_lower) / len(d_token_lower)
                # 编辑距离
                else:
                    similarity = TokenHighlighter._calculate_similarity(q_token_lower, d_token_lower)

                if similarity >= 0.7:  # 相似度阈值
                    matches.append({
                        "text": d_token,
                        "position": i,
                        "score": similarity,
                        "query_token": q_token
                    })
                    highlighted_positions.add(i)
        
        # 构建高亮文本
        highlighted_text = TokenHighlighter._build_highlighted_text(
            doc_tokens, highlighted_positions
        )
        
        return {
            "original": document,
            "highlighted": highlighted_text,
            "matches": matches,
            "match_count": len(set(m["position"] for m in matches)),
            "match_rate": len(set(m["position"] for m in matches)) / len(doc_tokens) if doc_tokens else 0
        }
    
    @staticmethod
    def _calculate_similarity(s1: str, s2: str) -> float:
        """计算两个字符串的相似度"""
        matcher = difflib.SequenceMatcher(None, s1, s2)
        return matcher.ratio()
    
    @staticmethod
    def _build_highlighted_text(tokens: List[str], positions: set) -> str:
        """构建高亮文本"""
        highlighted = []
        for i, token in enumerate(tokens):
            if i in positions:
                highlighted.append(f"**{token}**")
            else:
                highlighted.append(token)
        return " ".join(highlighted)
    
    @staticmethod
    def get_context_windows(
        query: str,
        document: str,
        window_size: int = 3
    ) -> List[Dict]:
        """
        获取匹配周围的上下文窗口
        
        Args:
            query: 查询语句
            document: 文档文本
            window_size: 窗口大小（前后各 N 个 token）
        
        Returns:
            上下文窗口列表
        """
        highlight_info = TokenHighlighter.highlight_matches(query, document)
        doc_tokens = TokenHighlighter._tokenize_text(document)
        
        windows = []
        processed_positions = set()
        
        for match in highlight_info["matches"]:
            pos = match["position"]
            
            if pos in processed_positions:
                continue
            
            # 获取窗口范围
            start = max(0, pos - window_size)
            end = min(len(doc_tokens), pos + window_size + 1)
            
            window_tokens = doc_tokens[start:end]
            window_text = " ".join(window_tokens)
            
            # 高亮匹配 token
            highlighted_window = window_tokens.copy()
            highlighted_window[pos - start] = f"**{highlighted_window[pos - start]}**"
            highlighted_window_text = " ".join(highlighted_window)
            
            windows.append({
                "text": window_text,
                "highlighted": highlighted_window_text,
                "position": pos,
                "match_token": match["text"],
                "match_score": match["score"]
            })
            
            processed_positions.add(pos)
        
        return windows

class ExplanationGenerator:
    """解释生成器"""
    
    @staticmethod
    def generate_explanation(
        query: str,
        document: str,
        score: float
    ) -> Dict:
        """
        生成详细的匹配解释
        
        Args:
            query: 查询语句
            document: 文档文本
            score: 相关性分数
        
        Returns:
            解释信息
        """
        highlight_info = TokenHighlighter.highlight_matches(query, document)
        context_windows = TokenHighlighter.get_context_windows(query, document)
        
        explanation = {
            "score": score,
            "summary": ExplanationGenerator._generate_summary(
                query, document, highlight_info
            ),
            "matches": highlight_info["matches"],
            "match_statistics": {
                "total_matches": highlight_info["match_count"],
                "match_rate": highlight_info["match_rate"],
                "avg_match_score": sum(m["score"] for m in highlight_info["matches"]) / max(1, len(highlight_info["matches"]))
            },
            "context_windows": context_windows,
            "highlighted_document": highlight_info["highlighted"]
        }
        
        return explanation
    
    @staticmethod
    def _generate_summary(query: str, document: str, highlight_info: Dict) -> str:
        """生成摘要"""
        match_count = highlight_info["match_count"]
        match_rate = highlight_info["match_rate"]
        
        if match_rate >= 0.8:
            return "非常匹配：文档中大部分查询 token 都被找到"
        elif match_rate >= 0.5:
            return "良好匹配：文档中超过一半的查询 token 被找到"
        elif match_rate >= 0.2:
            return "部分匹配：文档中部分查询 token 被找到"
        else:
            return "弱匹配：文档中很少查询 token 被找到"

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    query = "如何重置密码"
    document = "如果您忘记了登录密码，可以通过以下步骤重置密码：访问登录页面，点击忘记密码链接，输入注册邮箱，检查邮件中的重置链接。"
    
    # 高亮
    highlight_info = TokenHighlighter.highlight_matches(query, document)
    print("高亮信息：")
    print(json.dumps(highlight_info, ensure_ascii=False, indent=2))
    
    # 上下文窗口
    windows = TokenHighlighter.get_context_windows(query, document)
    print("\n上下文窗口：")
    for window in windows:
        print(f"  {window['highlighted']}")
    
    # 解释
    explanation = ExplanationGenerator.generate_explanation(query, document, 0.95)
    print("\n解释：")
    print(json.dumps(explanation, ensure_ascii=False, indent=2))
