import voyager
import numpy as np

def semantic_sentence_search(article_text, query_sentence):
    """
    在文章中搜索与查询语句语义相似的句子
    """
    # 将文章分割成句子（这里简单按句号分割，实际应用可使用更复杂的分句方法）
    sentences = [sentence.strip() for sentence in article_text.split('。') if sentence.strip()]
    
    # 初始化 Voyager 索引，使用余弦相似度
    index = voyager.Index(space=voyager.Space.Cosine, num_dimensions=384)  # 假设使用384维向量
    
    # 模拟句子向量（实际应用中应使用文本嵌入模型如BERT、Voyage AI等）
    # 这里用随机向量模拟，真实场景需要替换为真实的文本嵌入
    sentence_vectors = []
    for i, sentence in enumerate(sentences):
        # 模拟生成句子向量（实际应使用嵌入模型）
        vector = np.random.rand(384).astype(np.float32)
        sentence_vectors.append(vector)
        index.add_item(vector, i)  # 将句子索引和向量添加到Voyager
    
    # 构建索引 (Voyager 索引通常不需要显式构建)
    
    # 生成查询语句的向量（同样需要嵌入模型）
    query_vector = np.random.rand(384).astype(np.float32)
    
    # 执行搜索，返回最相似的3个句子
    k = 3
    nearest_ids, distances = index.query(query_vector, k=k)
    
    print(f"查询语句: '{query_sentence}'")
    print(f"在文章中找到的最相似的 {k} 个句子:")
    print("-" * 50)
    
    for i, (sentence_id, distance) in enumerate(zip(nearest_ids, distances)):
        similarity = 1 - distance  # 余弦距离转换为相似度
        print(f"{i+1}. 相似度: {similarity:.4f}")
        print(f"   内容: {sentences[sentence_id]}")
        print()
    
    return [(sentences[sentence_id], similarity) for sentence_id, similarity in zip(nearest_ids, distances)]

# 测试示例
article_text = """
自然语言处理技术近年来取得了显著进展。深度学习模型在文本理解方面表现出色。
2023年的大型语言模型参数量已超过千亿级别，这些模型能够理解和生成人类语言。
人工智能在医疗领域的应用也越来越广泛，特别是在疾病诊断和药物研发方面。
机器学习算法需要大量的训练数据，数据的质量直接影响模型性能。
未来的研究方向包括多模态学习和小样本学习，以提高模型的泛化能力。
"""

query = "人工智能在医疗领域的应用"
results = semantic_sentence_search(article_text, query)