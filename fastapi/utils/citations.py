from annoy import AnnoyIndex
import numpy as np
import logging
import numpy as np
from typing import  Dict, List, Tuple
import logging
from utils.api_embedding import EmbeddingModel
import re

logger = logging.getLogger(__name__)
class citations:
    def __init__(self):
        self.embedding_model = EmbeddingModel()
   

    async def calculate_sentence_similarity(self, query_sentence,  sentences_list_v, api_key: str = None, num_trees=20,top_k=5):
        """
        计算查询语句在句子数组中的余弦相似度和距离

        参数:
        query_sentence (str): 查询语句
        sentences_list (list): 被查询的句子数组
        top_k (int): 返回最相似的句子数量，默认为5

        返回:
        tuple: (similar_indexes, cosine_similarities, distances)
            - similar_indexes: 相似句子的索引列表
            - cosine_similarities: 余弦相似度列表
            - distances: 距离列表
        """
        if not sentences_list_v:
            raise ValueError("句子数组不能为空")

        # 1. 将所有句子转换为向量
        # all_sentences = [query_sentence] + sentences_list
        query_sentence_vectors = await self.embedding_model.get_embedding(query_sentence, api_key)

        # 过滤掉空向量，并构建句子向量列表
        sentence_vectors = []
        valid_indices = []  # 记录有效向量的原始索引

        # 添加查询句子向量（如果有效）
        if query_sentence_vectors and len(query_sentence_vectors) > 0:
            sentence_vectors.append(query_sentence_vectors)
            valid_indices.append(-1)  # 查询句子用 -1 表示

        # 添加源句子向量（过滤空向量）
        for i, vector in enumerate(sentences_list_v):
            if vector and len(vector) > 0:
                sentence_vectors.append(vector)
                valid_indices.append(i)

        # 如果没有有效的向量，返回空结果
        if not sentence_vectors:
            logger.warning("No valid vectors found for similarity calculation")
            return [], [], []

        # 2. 获取向量维度 - 将列表转换为numpy数组
        sentence_vectors = np.array(sentence_vectors)
        vector_dim = sentence_vectors.shape[1]

        # 3. 初始化Annoy索引
        annoy_index = AnnoyIndex(vector_dim, 'angular')  # 使用angular距离（适合余弦相似度）

        # 4. 将向量添加到索引中
        for i, vector in enumerate(sentence_vectors):
            annoy_index.add_item(i, vector)

        # 5. 构建索引树
        annoy_index.build(num_trees)

        # 6. 保存索引以供将来使用
        annoy_index.save('sentence_similarity.ann')

        # 7. 查找最相似的句子
        query_vector = query_sentence_vectors  # 查询句子的向量

        # 如果查询向量无效，无法进行相似度计算
        if not query_vector or len(query_vector) == 0:
            logger.warning("Query vector is empty, cannot calculate similarity")
            return [], [], []

        # 查找查询向量在索引中的位置（如果存在）
        query_index_in_annoy = None
        for i, idx in enumerate(valid_indices):
            if idx == -1:  # 这是查询向量
                query_index_in_annoy = i
                break

        # 使用Annoy查找最相似的句子
        if query_index_in_annoy is not None:
            # 查询向量在索引中，查找 top_k+1 个结果（包括自己）
            similar_indexes, distances = annoy_index.get_nns_by_vector(
                query_vector, top_k + 1, include_distances=True
            )
            # 过滤掉查询句子本身
            similar_indexes = [idx for idx in similar_indexes if idx != query_index_in_annoy][:top_k]
            distances = distances[1:top_k+1][:top_k]  # 对应的距离
        else:
            # 查询向量不在索引中，直接查找 top_k 个最相似的结果
            similar_indexes, distances = annoy_index.get_nns_by_vector(
                query_vector, top_k, include_distances=True
            )

        # 将angular距离转换为余弦相似度
        cosine_similarities = [np.cos(distance * np.pi / 2) for distance in distances]

        # 将Annoy索引映射回原始句子索引
        original_similar_indexes = []
        for idx in similar_indexes:
            if idx < len(valid_indices):
                original_idx = valid_indices[idx]
                if original_idx >= 0:  # 只返回源句子的索引（排除查询句子）
                    original_similar_indexes.append(original_idx)

        return original_similar_indexes, cosine_similarities[:len(original_similar_indexes)], distances[:len(original_similar_indexes)]


    async def calculate_sentence_similarity_with_existing_index(self, query_sentence, sentences_list, api_key: str = None, index_file='sentence_similarity.ann', top_k=5):
        """
        使用现有索引文件计算查询语句在句子数组中的余弦相似度和距离

        参数:
        query_sentence (str): 查询语句
        sentences_list (list): 被查询的句子数组
        index_file (str): 索引文件名
        top_k (int): 返回最相似的句子数量，默认为5

        返回:
        tuple: (similar_indexes, cosine_similarities, distances)
            - similar_indexes: 相似句子的索引列表
            - cosine_similarities: 余弦相似度列表
            - distances: 距离列表
        """
        if not sentences_list:
            raise ValueError("句子数组不能为空")

        # 1. 将查询句子转换为向量
        query_vector = await self.embedding_model.get_embedding(query_sentence, api_key)

        # 2. 获取向量维度 - 需要从现有索引推断或重新计算
        # 这里我们重新计算所有向量的维度
        sentence_vectors = []
        for sentence in sentences_list:
            vector = await self.embedding_model.get_embedding(sentence, api_key)
            sentence_vectors.append(vector)
        sentence_vectors = np.array(sentence_vectors)
        vector_dim = sentence_vectors.shape[1]

        # 3. 加载现有索引
        try:
            annoy_index = AnnoyIndex(vector_dim, 'angular')
            annoy_index.load(index_file)

            # 4. 查找最相似的句子
            # 注意：这里我们需要将查询向量添加到索引中进行搜索
            # 创建一个临时索引来包含查询向量
            temp_index = AnnoyIndex(vector_dim, 'angular')
            temp_index.load(index_file)

            # 添加查询向量到临时索引
            temp_index.add_item(len(sentences_list), query_vector)

            # 查找最相似的句子
            similar_indexes, distances = temp_index.get_nns_by_vector(
                query_vector, top_k + 1, include_distances=True
            )

            # 过滤掉第一个结果（查询句子本身）
            similar_indexes = similar_indexes[1:]
            distances = distances[1:]

            # 将angular距离转换为余弦相似度
            cosine_similarities = [np.cos(distance * np.pi / 2) for distance in distances]

            return similar_indexes, cosine_similarities, distances

        except Exception as e:
            print(f"加载索引失败: {e}，将使用标准方法...")
            return self.calculate_sentence_similarity(query_sentence, sentences_list, top_k)


    def find_similar_sentences(self, query_sentence, sentences_list=None, top_k=5):
        """
        查找与查询句子最相似的句子（兼容旧接口）

        参数:
        query_sentence (str): 查询句子
        sentences_list (list): 可选的句子列表，如果为None则使用默认列表
        top_k (int): 返回最相似的句子数量

        返回:
        tuple: 相似句子索引和余弦相似度
        """
    
        similar_indexes, cosine_similarities, distances = self.calculate_sentence_similarity(
            query_sentence, sentences_list, top_k
        )

        print(f"\n查询句子: '{query_sentence}'")
        print(f"前{top_k}个最相似的句子:")
        for i, (idx, similarity, distance) in enumerate(zip(similar_indexes, cosine_similarities, distances)):
            print(f"{i+1}. '{sentences_list[idx]}' (相似度: {similarity:.4f}, 距离: {distance:.4f})")

        return similar_indexes, cosine_similarities


    def _is_table_separator(self, text: str) -> bool:
        """
        检查文本是否为表格分隔线等不需要引用的内容

        参数:
        - text: 要检查的文本

        返回:
        - 如果是表格分隔线等返回True，否则返回False
        """
        import re

        # 检查是否主要由分隔符组成（包含大量 - 和 | 字符）
        # 计算 - 和 | 字符的比例
        separator_chars = text.count('-') + text.count('|')
        total_chars = len(text.strip())

        # 如果分隔符字符占比超过60%，认为是表格分隔线
        if total_chars > 0 and separator_chars / total_chars > 0.6:
            return True

        # 同时检查一些常见的表格分隔符模式
        table_separator_patterns = [
            r'\|[-\s]*\|',  # 包含 |---| 或 |   | 的行
            r'\+[-\+]*\+',  # +---+ 或 +++++
        ]

        for pattern in table_separator_patterns:
            if re.search(pattern, text):
                return True

        return False

    def _clean_table_separator(self, text: str) -> str:
        """
        清理表格分隔线，去掉末尾的引用数字

        参数:
        - text: 原始文本

        返回:
        - 清理后的文本
        """
        import re

        # 移除末尾的引用数字和空格，如 "1 |" -> "|"
        # 匹配末尾的数字后面跟着 | 和可选的空格
        cleaned = re.sub(r'\s+\d+\s*\|\s*$', ' |', text)
        return cleaned
 
        
    def advanced_sentence_splitter(self, text):
        """
        高级句子分割器，处理各种特殊情况
        """
        text = text.strip()

        # 处理Markdown格式和特殊符号
        pattern = r'''
            (?<=[。！？!?])          # 基本句子结束符
            \s*                     # 任意空白
            (?![）\]】」』)）])      # 排除右括号和特殊符号
            (?!\*|\*\*)            # 排除Markdown符号
            (?!\d+\.)              # 排除数字加点（如"1."）
        '''

        sentences = re.split(pattern, text, flags=re.VERBOSE)
        sentences = [s.strip() for s in sentences if s.strip()]

        # 进一步处理包含列表项的情况
        final_sentences = []
        for sentence in sentences:
            # 如果句子以列表项开头，进一步分割
            if re.match(r'^\*+\s*\*{0,2}', sentence):
                # 处理Markdown列表项
                list_items = re.split(r'(?<=\])\s*', sentence)
                final_sentences.extend([item.strip() for item in list_items if item.strip()])
            else:
                final_sentences.append(sentence)        
        return final_sentences

    async def get_source_embeddings(self, search_results: List[Dict], api_key: str = None) -> Tuple[List[List[float]], List[int], List[str], Dict[int, Dict]]:
        # 创建来源映射字典
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
        # 预处理所有来源的内容，确保UTF-8编码
        source_contents = []
        source_ids = []
        source_embeddings = []
        for source_id, source_info in source_map.items():
            content = source_info.get('content', '').strip()
            if content:                
                source_contents.append(content)
                source_ids.append(source_id)

        # 预计算所有来源的向量表示（批量处理，提高效率）
        source_embeddings = []
        for content in source_contents:        
            try:
                embedding = await self.embedding_model.get_embedding(content, api_key)
                source_embeddings.append(embedding)
            except Exception as e:
                logger.warning(f"Failed to get embedding for source content: {str(e)[:200]}")
                # 使用零向量作为fallback
                source_embeddings.append([0.0] * 1024)  # 与正常embedding向量维度一致            
        return source_embeddings,source_ids,source_contents,source_map


    async def get_source_embeddings_map(self, source_map:{}, api_key: str = None) -> Tuple[List[List[float]], List[int], List[str], Dict[int, Dict]]:
        # 检查source_map是否为None
        if source_map is None:
            logger.warning("source_map is None, returning empty results")
            return [], [], [], {}

        # 创建来源映射字典
        source_map = source_map

        # 预处理所有来源的内容，确保UTF-8编码
        source_contents = []
        source_ids = []
        source_embeddings = []
        for source_id, source_info in source_map.items():
            content = source_info.get('content', '').strip()
            if content:                
                source_contents.append(content)
                source_ids.append(source_id)

        # 预计算所有来源的向量表示（批量处理，提高效率）
        source_embeddings = []
        for content in source_contents:        
            try:
                embedding = await self.embedding_model.get_embedding(content, api_key)
                source_embeddings.append(embedding)
            except Exception as e:
                logger.warning(f"Failed to get embedding for source content: {str(e)[:200]}")
                # 使用零向量作为fallback
                source_embeddings.append([0.0] * 1024)  # 与正常embedding向量维度一致            
        return source_embeddings,source_ids,source_contents,source_map    
    def _contains_symbol_patterns(self, text: str) -> bool:
        """
        检查文本是否包含需要跳过的符号组合

        参数:
        - text: 要检查的文本

        返回:
        - 如果包含符号组合返回True，否则返回False
        """
        # 检查表格分隔符等符号组合
        symbol_patterns = [
            r'\|[-\s]*\|',  # |---| 或 |   |
            r'\|[-]+\|',    # |----|
            r'\|[-\s]*\|[-\s]*\|',  # |---|---|
            r'\+[-\+]*\+',  # +---+ 或 +++++
            r'\|[\s\-\|]*\|',  # | - | 或 | | 等
            r'—+',  # 全角破折号
        ]

        import re
        for pattern in symbol_patterns:
            if re.search(pattern, text):
                return True
        return False


    def _add_reference_marker(self, sentence: str, source_id: int) -> str:
        """
        为句子添加引用标记

        参数:
        - sentence: 原始句子
        - source_id: 来源ID

        返回:
        - 带有引用标记的句子
        """
        return sentence + f" [{source_id}]()"

    def _add_knowledge_reference_marker(self, sentence: str, source_id: int) -> str:
        """
        为句子添加引用标记

        参数:
        - sentence: 原始句子
        - source_id: 来源ID

        返回:
        - 带有引用标记的句子
        """
        source_ids ='100'+str(source_id)
        return sentence + f" [{source_ids}]()"        

    def formate_map(self, source_map):
        new_source_map={}
        if source_map:
            for source_id, source_info in source_map.items():
                title = source_info.get('title', '')[:100] + "..." if len(source_info.get('title', '')) > 100 else source_info.get('title', '')
                content = source_info.get('content', '')[:500] + "..." if len(source_info.get('content', '')) > 500 else source_info.get('content', '')
                new_source_map[source_id] = {
                    'title': title,
                    'url': source_info.get('url', ''),
                    'content': content
                }
        return new_source_map

    def formate_map_knowledge_chunks(self, knowledge_chunks):
        new_source_map={}
        if knowledge_chunks:
            for chunk in knowledge_chunks:
                # 使用 chunk_id 作为 key，如果没有则使用 doc_id + chunk_id 的组合
                source_id =  f"{chunk.get('doc_id', '')}_{chunk.get('chunk_id', '')}"

                title = chunk.get('doc_name', '')[:100] + "..." if len(chunk.get('doc_name', '')) > 100 else chunk.get('doc_name', '')
                content = chunk.get('content', '')[:500] + "..." if len(chunk.get('content', '')) > 500 else chunk.get('content', '')
                new_source_map[source_id] = {
                    "doc_id": chunk.get('doc_id', ''),
                    "doc_name": title,
                    "chunk_id": chunk.get('chunk_id', ''),
                    "content": content,
                    "pos_info": chunk.get('pos_info', ''),
                    "seq_no": chunk.get('seq_no', '')
                }
        return new_source_map


    def get_knowledge_chunks(self, documents):
        knowledge_chunks = []
        for doc in documents:
            sources_raw = doc.get("sources", []) 
            sources = self.parse_sources_raw(sources_raw)
            knowledge_chunks.extend(sources)
        return knowledge_chunks

    def parse_sources_raw(self, sources_raw):
        """
        解析 sources_raw 内容，支持 JSON 字符串格式

        Args:
            sources_raw: JSON 字符串格式的 sources_raw 数据

        Returns:
            list: 解析后的知识块列表
        """
        import json
        import ast

        knowledge_chunks = []

        # 如果是字符串，先尝试 JSON 解析
        if isinstance(sources_raw, str):
            try:
                # 尝试作为 JSON 解析
                parsed_data = json.loads(sources_raw)
            except json.JSONDecodeError:
                try:
                    # 如果 JSON 解析失败，尝试作为 Python 字面量解析
                    parsed_data = ast.literal_eval(sources_raw)
                except (ValueError, SyntaxError):
                    logger.error(f"无法解析 sources_raw 字符串: {sources_raw}")
                    return knowledge_chunks

            # 如果解析结果是字典，则包装成列表
            if isinstance(parsed_data, dict):
                sources_raw = [parsed_data]
            elif isinstance(parsed_data, list):
                sources_raw = parsed_data
            else:
                logger.warning(f"解析后的数据格式不支持: {type(parsed_data)}")
                return knowledge_chunks

        # 确保 sources_raw 是列表格式
        if not isinstance(sources_raw, list):
            logger.warning(f"sources_raw 应该是列表格式，当前类型: {type(sources_raw)}")
            return knowledge_chunks

        for source in sources_raw:
            # 确保 source 是字典格式
            if not isinstance(source, dict):
                logger.warning(f"source 不是字典格式: {type(source)} = {source}, 跳过")
                continue

            doc_id = source.get("doc_id")
            doc_name = source.get("doc_name")
            chunk_id = source.get("chunk_id")
            content = source.get("content")
            pos_info = source.get("pos_info")
            seq_no = source.get("seq_no")

            knowledge_chunks.append({
                "doc_id": doc_id,
                "doc_name": doc_name,
                "chunk_id": chunk_id,
                "content": content,
                "pos_info": pos_info,
                "seq_no": seq_no
            })

        return knowledge_chunks

class SentenceDetector:
    def __init__(self):
        pass
    """句子检测器，支持流式句子级处理"""

    # 中英文句子结束符号
    SENTENCE_ENDINGS = {
        'zh': ['。', '！', '？', '；'],
        'en': ['.', '!', '?'],
        'universal': ['\n', '\r\n']  # 通用换行符
    }

    # 不应作为句子结束的缩写
    ABBREVIATIONS = {
        'en': ['Mr.', 'Mrs.', 'Dr.', 'Prof.', 'Sr.', 'Jr.', 'Ms.', 'etc.', 'vs.', 'i.e.', 'e.g.'],
        'zh': []  # 中文通常没有这种缩写问题
    }

    def __init__(self, language: str = 'zh'):
        self.language = language
        self.buffer = ""
        self.in_quotes = False
        self.quote_char = None
        self.pending_chunks = []

    def _is_sentence_ending(self, text: str) -> bool:
        """检测文本是否以句子结束符号结尾"""
        if not text:
            return False

        # 检查通用换行符
        for ending in self.SENTENCE_ENDINGS['universal']:
            if text.endswith(ending):
                return True

        # 检查语言特定的结束符号
        for ending in self.SENTENCE_ENDINGS.get(self.language, self.SENTENCE_ENDINGS['zh']):
            if text.endswith(ending):
                # 检查是否是缩写（仅对英文）
                if self.language == 'en':
                    for abbr in self.ABBREVIATIONS['en']:
                        if text.endswith(abbr):
                            return False
                return True

        return False

    def _handle_quotes(self, chunk: str):
        """处理引号状态"""
        quote_chars = ['"', "'"]  # 双引号，单引号

        for char in chunk:
            if char in quote_chars:
                if not self.in_quotes:
                    self.in_quotes = True
                    self.quote_char = char
                elif char == self.quote_char:
                    self.in_quotes = False
                    self.quote_char = None

    def add_chunk(self, chunk: str) -> List[str]:
        """
        添加chunk到缓冲区，返回完整的句子列表
        """
        if not chunk:
            return []

        # 处理引号状态
        self._handle_quotes(chunk)

        # 添加到缓冲区
        self.buffer += chunk
        self.pending_chunks.append(chunk)

        # 如果在引号内，不检查句子结束
        if self.in_quotes:
            return []

        # 检查是否形成完整句子
        if self._is_sentence_ending(self.buffer):
            complete_sentence = self.buffer
            # 重置缓冲区
            self.buffer = ""
            self.pending_chunks = []
            return [complete_sentence]

        return []

    def get_remaining(self) -> str:
        """获取缓冲区中剩余的未完成句子"""
        return self.buffer

    def flush(self) -> str:
        """强制输出当前缓冲区的内容"""
        if self.buffer:
            result = self.buffer
            self.buffer = ""
            self.pending_chunks = []
            return result
        return ""
    

# 全局实例
citations_instance = citations()
