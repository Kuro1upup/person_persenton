import voyager
import numpy as np
from sentence_transformers import SentenceTransformer  # 需要安装: pip install sentence-transformers

class AdvancedSemanticSearcher:
    def __init__(self, model_name='all-MiniLM-L6-v2'):
        """初始化语义搜索器"""
        self.model = SentenceTransformer(model_name)
        self.index = None
        self.sentences = []
        
    def build_index(self, article_text):
        """构建文章句子的语义索引"""
        # 分割句子
        self.sentences = [s.strip() for s in article_text.split('。') if s.strip()]
        
        if not self.sentences:
            raise ValueError("文章中没有找到有效的句子")
        
        # 生成句子嵌入向量
        sentence_embeddings = self.model.encode(self.sentences)
        
        # 初始化 Voyager 索引
        dimension = sentence_embeddings.shape[1]
        self.index = voyager.Index(space=voyager.Space.Cosine, num_dimensions=dimension)
        
        # 添加向量到索引
        for i, embedding in enumerate(sentence_embeddings):
            self.index.add_item(embedding.astype(np.float32), i)
        
        print(f"索引构建完成，共处理 {len(self.sentences)} 个句子")
        
    def search(self, query, top_k=3):
        """语义搜索"""
        if self.index is None:
            raise ValueError("请先调用 build_index() 方法构建索引")
        
        # 生成查询嵌入
        query_embedding = self.model.encode([query])[0].astype(np.float32)
        
        # 执行搜索
        nearest_ids, distances = self.index.query(query_embedding, k=top_k)
        
        results = []
        for i, (sentence_id, distance) in enumerate(zip(nearest_ids, distances)):
            similarity = 1 - distance
            results.append({
                'rank': i + 1,
                'sentence': self.sentences[sentence_id],
                'similarity': similarity,
                'sentence_id': sentence_id
            })
        
        return results

# 使用示例
if __name__ == "__main__":
    # 初始化搜索器
    searcher = AdvancedSemanticSearcher()
    
    # 示例文章
    article = """
人工智能技术在2023年取得了突破性进展。大型语言模型如GPT-4在自然语言处理任务中表现出色。
机器学习算法在图像识别领域的准确率达到了95%以上。深度学习模型需要大量的计算资源。
未来的研究方向包括可解释AI和联邦学习。预计2024年AI市场规模将增长30%。
"""
    
    # 构建索引
    searcher.build_index(article)
    
    # 执行搜索
    query1 = "机器学习算法在图像识别领域的准确率达到了95%以上"
    results1 = searcher.search(query1)
    
    print(f"查询: '{query1}'")
    for result in results1:
        print(f"{result['rank']}. 相似度: {result['similarity']:.4f}")
        print(f"   句子: {result['sentence']}")
        print()