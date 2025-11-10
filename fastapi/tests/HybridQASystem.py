import numpy as np
import voyageai
from sentence_transformers import SentenceTransformer
from typing import List, Tuple, Dict, Any
import re
import json
import warnings

# 抑制fuzzywuzzy的性能警告
warnings.filterwarnings("ignore", message="Using slow pure-python SequenceMatcher")

# 在导入fuzzywuzzy时抑制警告
with warnings.catch_warnings():
    warnings.simplefilter("ignore", UserWarning)
    from fuzzywuzzy import fuzz, process

class HybridQASystem:
    def __init__(self, voyage_api_key: str, semantic_threshold: float = 0.7, fuzzy_threshold: int = 80):
        """
        混合智能问答系统
        :param voyage_api_key: Voyage AI API密钥
        :param semantic_threshold: 语义相似度阈值
        :param fuzzy_threshold: 模糊匹配阈值
        """
        self.voyage_api_key = voyage_api_key
        self.semantic_threshold = semantic_threshold
        self.fuzzy_threshold = fuzzy_threshold
        
        # 初始化Voyage AI客户端（用于语义匹配）
        self.vo_client = voyageai.Client(api_key=voyage_api_key)
        
        # 初始化本地嵌入模型（备用方案）
        try:
            self.local_model = SentenceTransformer('all-MiniLM-L6-v2')
        except:
            self.local_model = None
            
        # 存储文档和向量
        self.documents = []
        self.document_vectors = []
        self.document_metadata = []
        
        # Voyager索引（用于快速近似最近邻搜索）
        # 注意：这里需要安装voyager库，实际使用时请根据Voyager文档正确初始化
        self.voyager_index = None
        
    def preprocess_text(self, text: str) -> str:
        """文本预处理"""
        # 去除多余空格和特殊字符
        text = re.sub(r'\s+', ' ', text.strip())
        # 其他预处理步骤可以根据需要添加
        return text
    
    def add_documents(self, documents: List[Dict[str, Any]]):
        """
        添加文档到系统
        :param documents: 文档列表，每个文档包含text和metadata
        """
        print("正在处理文档并生成向量...")
        
        for i, doc in enumerate(documents):
            processed_text = self.preprocess_text(doc['text'])
            self.documents.append({
                'id': i,
                'text': processed_text,
                'metadata': doc.get('metadata', {})
            })
            
            # 生成文档向量（优先使用本地模型，确保维度一致性）
            if self.local_model:
                # 使用本地sentence-transformers模型
                embedding = self.local_model.encode([processed_text])[0]
            else:
                # 本地模型不可用，尝试使用Voyage AI
                try:
                    embedding = self.vo_client.embed(
                        [processed_text],
                        model="voyage-3",
                        input_type="document"
                    ).embeddings[0]
                except Exception as e:
                    print(f"Voyage AI API调用失败，使用随机向量: {e}")
                    # 备用：使用随机向量（仅用于演示）
                    embedding = np.random.rand(384).astype(np.float32)
            
            self.document_vectors.append(embedding)
            self.document_metadata.append(doc.get('metadata', {}))
            
            if (i + 1) % 10 == 0:
                print(f"已处理 {i + 1}/{len(documents)} 个文档")
        
        # 构建Voyager索引
        self._build_voyager_index()
        
    def _build_voyager_index(self):
        """构建Voyager向量索引"""
        try:
            import voyager
            
            # 获取向量维度
            dimension = len(self.document_vectors[0])
            
            # 初始化Voyager索引
            self.voyager_index = voyager.Index(
                space=voyager.Space.Cosine,  # 使用余弦相似度
                num_dimensions=dimension
            )
            
            # 添加向量到索引
            for i, vector in enumerate(self.document_vectors):
                self.voyager_index.add_item(vector, i)

            # Voyager索引通常不需要显式构建
            print("Voyager索引构建完成")
            
        except ImportError:
            print("警告：未找到voyager库，使用基础向量搜索")
            self.voyager_index = None
    
    def semantic_search(self, query: str, top_k: int = 5) -> List[Tuple[int, float, str]]:
        """基于语义向量的搜索"""
        # 生成查询向量（优先使用本地模型，确保与索引维度一致）
        if self.local_model:
            # 使用本地sentence-transformers模型
            query_embedding = self.local_model.encode([query])[0]
        else:
            # 本地模型不可用，尝试使用Voyage AI
            try:
                query_embedding = self.vo_client.embed(
                    [query],
                    model="voyage-3",
                    input_type="query"
                ).embeddings[0]
            except Exception as e:
                print(f"Voyage AI查询失败: {e}")
                return []
        
        # 使用Voyager进行近似最近邻搜索
        if self.voyager_index:
            nearest_ids, distances = self.voyager_index.query(
                query_embedding,
                k=min(top_k * 2, len(self.documents))
            )
            
            results = []
            for doc_id, distance in zip(nearest_ids, distances):
                similarity = 1 - distance  # 将距离转换为相似度
                if similarity >= self.semantic_threshold:
                    results.append((
                        doc_id, 
                        similarity, 
                        self.documents[doc_id]['text']
                    ))
            
            # 按相似度排序并返回top_k
            results.sort(key=lambda x: x[1], reverse=True)
            return results[:top_k]
        
        else:
            # 备用：使用余弦相似度进行线性搜索
            query_vector = np.array(query_embedding)
            similarities = []
            
            for i, doc_vector in enumerate(self.document_vectors):
                similarity = np.dot(query_vector, doc_vector) / (
                    np.linalg.norm(query_vector) * np.linalg.norm(doc_vector)
                )
                if similarity >= self.semantic_threshold:
                    similarities.append((i, similarity, self.documents[i]['text']))
            
            similarities.sort(key=lambda x: x[1], reverse=True)
            return similarities[:top_k]
    
    def fuzzy_search(self, query: str, top_k: int = 5) -> List[Tuple[int, int, str]]:
        """基于模糊匹配的搜索"""
        # 提取所有文档文本用于模糊匹配
        doc_texts = [doc['text'] for doc in self.documents]
        
        # 使用fuzzywuzzy进行模糊匹配
        matches = process.extract(
            query, 
            doc_texts, 
            scorer=fuzz.token_set_ratio,  # 使用token_set_ratio处理词序变化
            limit=top_k * 2
        )
        
        results = []
        for text, score in matches:
            if score >= self.fuzzy_threshold:
                # 找到原始文档ID
                original_doc_id = next(i for i, doc in enumerate(self.documents)
                                     if doc['text'] == text)
                results.append((original_doc_id, score, text))
        
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]
    
    def hybrid_search(self, query: str, top_k: int = 5) -> Dict[str, Any]:
        """混合搜索：结合语义搜索和模糊匹配"""
        print(f"执行混合搜索: '{query}'")
        
        # 并行执行两种搜索
        semantic_results = self.semantic_search(query, top_k)
        fuzzy_results = self.fuzzy_search(query, top_k)
        
        # 合并和去重结果
        all_results = {}
        
        # 添加语义搜索结果
        for doc_id, score, text in semantic_results:
            if doc_id not in all_results:
                all_results[doc_id] = {
                    'doc_id': doc_id,
                    'text': text,
                    'semantic_score': score,
                    'fuzzy_score': 0,
                    'combined_score': score,
                    'metadata': self.document_metadata[doc_id]
                }
        
        # 添加模糊匹配结果
        for doc_id, score, text in fuzzy_results:
            if doc_id in all_results:
                # 更新现有结果
                all_results[doc_id]['fuzzy_score'] = score
                all_results[doc_id]['combined_score'] = (
                    all_results[doc_id]['semantic_score'] * 0.7 + 
                    score * 0.3
                )  # 语义搜索权重更高
            else:
                all_results[doc_id] = {
                    'doc_id': doc_id,
                    'text': text,
                    'semantic_score': 0,
                    'fuzzy_score': score,
                    'combined_score': score * 0.3,  # 纯模糊匹配权重较低
                    'metadata': self.document_metadata[doc_id]
                }
        
        # 按综合分数排序
        sorted_results = sorted(
            all_results.values(), 
            key=lambda x: x['combined_score'], 
            reverse=True
        )
        
        return {
            'query': query,
            'results': sorted_results[:top_k],
            'search_type': 'hybrid'
        }
    
    def generate_answer_with_citations(self, query: str, top_k: int = 3) -> Dict[str, Any]:
        """生成答案并提供引用来源"""
        search_results = self.hybrid_search(query, top_k)
        
        if not search_results['results']:
            return {
                'answer': "抱歉，我没有找到相关的信息来回答这个问题。",
                'citations': [],
                'confidence': 0.0
            }
        
        # 简单答案生成：使用最相关的结果
        best_result = search_results['results'][0]
        answer_text = self._generate_answer_from_document(query, best_result)
        
        # 生成引用信息
        citations = []
        for i, result in enumerate(search_results['results']):
            citations.append({
                'rank': i + 1,
                'text': self._truncate_text(result['text']),
                'semantic_similarity': round(result['semantic_score'], 4),
                'fuzzy_similarity': result['fuzzy_score'],
                'combined_score': round(result['combined_score'], 4),
                'metadata': result['metadata']
            })
        
        return {
            'answer': answer_text,
            'citations': citations,
            'confidence': best_result['combined_score'],
            'search_summary': {
                'total_results': len(search_results['results']),
                'best_score': round(best_result['combined_score'], 4)
            }
        }
    
    def _generate_answer_from_document(self, query: str, document_result: Dict) -> str:
        """从文档生成答案（简化版）"""
        doc_text = document_result['text']
        
        # 简单的答案生成逻辑
        # 在实际应用中，可以使用LLM来生成更自然的答案
        if len(doc_text) <= 200:
            return f"根据相关信息：{doc_text}"
        else:
            # 如果文档较长，提取与查询相关的部分
            sentences = re.split(r'[。.!?]', doc_text)
            relevant_sentences = []
            
            for sentence in sentences:
                if sentence and len(sentence) > 10:
                    # 简单的关键词匹配
                    if any(keyword in sentence for keyword in query.split()[:3]):
                        relevant_sentences.append(sentence.strip())
            
            if relevant_sentences:
                return "根据相关资料：" + "。".join(relevant_sentences[:2]) + "。"
            else:
                return f"找到相关内容：{doc_text[:150]}..."
    
    def _truncate_text(self, text: str, max_length: int = 200) -> str:
        """截断文本"""
        if len(text) <= max_length:
            return text
        return text[:max_length] + "..."
    
    def save_index(self, filepath: str):
        """保存索引和文档数据"""
        import pickle
        
        data = {
            'documents': self.documents,
            'document_vectors': [vec.tolist() for vec in self.document_vectors],
            'document_metadata': self.document_metadata
        }
        
        with open(filepath, 'wb') as f:
            pickle.dump(data, f)
        
        print(f"索引已保存到: {filepath}")
    
    def load_index(self, filepath: str):
        """加载索引和文档数据"""
        import pickle
        
        with open(filepath, 'rb') as f:
            data = pickle.load(f)
        
        self.documents = data['documents']
        self.document_vectors = [np.array(vec) for vec in data['document_vectors']]
        self.document_metadata = data['document_metadata']
        
        # 重新构建Voyager索引
        self._build_voyager_index()
        
        print(f"已加载 {len(self.documents)} 个文档")

# 示例用法
if __name__ == "__main__":
    # 初始化系统（需要Voyage AI API密钥）
    voyage_api_key = "pa-KuX30bwSwpPo65QeU20ewgkqU4qDzCG4pq0I2QNPTTQ"  # 请替换为您的API密钥
    qa_system = HybridQASystem(voyage_api_key)
    
    # 示例文档数据
    sample_documents = [
        {
            'text': "2023年公司营业收入达到15.8亿元，同比增长25.3%。第四季度净利润为2.1亿元。",
            'metadata': {'source': '2023财务报告', 'category': '财务'}
        },
        {
            'text': "人工智能技术在自然语言处理领域取得重大突破，大型语言模型的参数量已超过千亿级别。",
            'metadata': {'source': '科技白皮书', 'category': '技术'}
        },
        {
            'text': "员工总数从2022年的1200人增加到2023年的1500人，研发投入占比达到营业收入的18.5%。",
            'metadata': {'source': '人力资源报告', 'category': '人事'}
        }
    ]
    
    # 添加文档到系统
    qa_system.add_documents(sample_documents)
    
    # 测试查询
    test_queries = [
        "2023年公司营收15.8亿元",
        "人工智能的最新发展，大型语言模型的参数量已超过千亿级别",
        "公司员工数量1500人和研发投入占比18.5%"
    ]
    
    for query in test_queries:
        print(f"\n=== 查询: {query} ===")
        
        result = qa_system.generate_answer_with_citations(query)
        
        print(f"答案: {result['answer']}")
        print(f"置信度: {result['confidence']:.4f}")
        print("引用来源:")
        
        for i, citation in enumerate(result['citations']):
            print(f"{i+1}. 相似度: {citation['combined_score']:.4f}")
            print(f"   文本: {citation['text']}")
            print(f"   来源: {citation['metadata']}")
            print()
    
    # 保存索引（可选）
    # qa_system.save_index('qa_system_index.pkl')