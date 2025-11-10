import voyager
import numpy as np
import re
import statistics
from typing import List, Tuple, Dict, Any
from sentence_transformers import SentenceTransformer  # 用于文本嵌入

class NumericFeatureExtractor:
    """高级数字特征提取器"""

    def __init__(self, embedding_model='all-MiniLM-L6-v2'):
        """初始化特征提取器"""
        self.embedding_model = SentenceTransformer(embedding_model)
        self.embedding_dim = 384  # all-MiniLM-L6-v2的维度

    def classify_number_type(self, number: float, context: str) -> str:
        """
        根据数字值和上下文分类数字类型
        """
        # 年份特征
        if 1900 <= number <= 2100 and ('年' in context or 'Year' in context):
            return 'year'

        # 百分比特征
        if 0 <= number <= 100 and ('%' in context or '百分比' in context or 'percent' in context):
            return 'percentage'

        # 金额特征（通常是较大的数字，可能带有货币单位）
        if number > 1000 and any(unit in context for unit in ['元', '美元', '人民币', '万元', '亿元', '万', '亿', '$', '¥']):
            return 'currency'

        # 数量特征
        if 1 <= number <= 10000 and any(word in context for word in ['个', '人', '台', '件', '辆', '套', '项']):
            return 'quantity'

        # 比率/倍数
        if 0 < number < 10 and any(word in context for word in ['倍', '率', '比']):
            return 'ratio'

        return 'general'

    def extract_statistical_features(self, numbers: List[float]) -> Dict[str, float]:
        """
        提取数字的统计特征
        """
        if not numbers:
            return {
                'count': 0, 'mean': 0, 'median': 0, 'std': 0, 'min': 0, 'max': 0,
                'q25': 0, 'q75': 0, 'range': 0, 'cv': 0, 'skewness': 0
            }

        sorted_nums = sorted(numbers)
        mean_val = statistics.mean(numbers)
        median_val = statistics.median(numbers)

        # 基本统计
        features = {
            'count': len(numbers),
            'mean': mean_val,
            'median': median_val,
            'min': min(numbers),
            'max': max(numbers),
            'range': max(numbers) - min(numbers),
        }

        # 标准差
        if len(numbers) > 1:
            features['std'] = statistics.stdev(numbers)
            features['cv'] = features['std'] / mean_val if mean_val != 0 else 0
        else:
            features['std'] = 0
            features['cv'] = 0

        # 四分位数
        if len(sorted_nums) >= 4:
            features['q25'] = np.percentile(sorted_nums, 25)
            features['q75'] = np.percentile(sorted_nums, 75)
        else:
            features['q25'] = sorted_nums[0] if sorted_nums else 0
            features['q75'] = sorted_nums[-1] if sorted_nums else 0

        # 偏度（简化计算）
        if features['std'] > 0:
            features['skewness'] = 3 * (mean_val - median_val) / features['std']
        else:
            features['skewness'] = 0

        return features

    def extract_contextual_features(self, sentence: str, numbers: List[float]) -> Dict[str, Any]:
        """
        提取数字的上下文特征
        """
        features = {}

        # 数字类型分布
        type_counts = {}
        for num in numbers:
            num_type = self.classify_number_type(num, sentence)
            type_counts[num_type] = type_counts.get(num_type, 0) + 1

        # 转换为one-hot编码
        number_types = ['year', 'percentage', 'currency', 'quantity', 'ratio', 'general']
        for num_type in number_types:
            features[f'type_{num_type}'] = type_counts.get(num_type, 0)

        # 位置特征
        sentence_length = len(sentence)
        if numbers:
            # 第一个数字的位置（归一化）
            first_num_pos = sentence.find(str(int(numbers[0])))
            features['first_num_pos_ratio'] = first_num_pos / sentence_length if sentence_length > 0 else 0

            # 数字密度
            features['num_density'] = len(numbers) / sentence_length

        return features

    def create_feature_vector(self, sentence: str, numbers: List[float]) -> np.ndarray:
        """
        创建完整的特征向量（统计特征 + 上下文特征 + 文本嵌入）
        """
        # 统计特征
        stat_features = self.extract_statistical_features(numbers)

        # 上下文特征
        context_features = self.extract_contextual_features(sentence, numbers)

        # 文本嵌入（使用句子变换器）
        text_embedding = self.embedding_model.encode([sentence])[0]

        # 合并所有特征
        feature_vector = []

        # 添加统计特征 (11个)
        stat_keys = ['count', 'mean', 'median', 'std', 'min', 'max', 'range', 'cv', 'q25', 'q75', 'skewness']
        for key in stat_keys:
            feature_vector.append(stat_features[key])

        # 添加上下文特征 (8个：6个类型 + 2个位置)
        context_keys = [f'type_{t}' for t in ['year', 'percentage', 'currency', 'quantity', 'ratio', 'general']]
        context_keys.extend(['first_num_pos_ratio', 'num_density'])
        for key in context_keys:
            feature_vector.append(context_features[key])

        # 添加文本嵌入 (384维)
        feature_vector.extend(text_embedding)

        # 验证总维度 (11统计 + 8上下文 + 384文本 = 403维)
        expected_dim = 11 + 8 + self.embedding_dim
        actual_dim = len(feature_vector)

        if actual_dim != expected_dim:
            print(f"警告: 特征向量维度不匹配，期望{expected_dim}维，实际{actual_dim}维")

        return np.array(feature_vector, dtype=np.float32)

def numeric_sentence_search(article_text, query_with_numbers):
    """
    在文章中搜索包含数字的相似语句（优化版）
    """
    # 初始化高级特征提取器
    feature_extractor = NumericFeatureExtractor()

    # 分割文章为句子
    sentences = [sentence.strip() for sentence in article_text.split('。') if sentence.strip()]

    # 提取每个句子中的数字特征
    sentence_features = []
    numeric_sentences = []  # 保存包含数字的句子

    for i, sentence in enumerate(sentences):
        # 提取句子中的所有数字
        numbers = [float(num) for num in re.findall(r'\d+\.?\d*', sentence)]

        if numbers:  # 只处理包含数字的句子
            numeric_sentences.append((i, sentence, numbers))

            # 使用高级特征提取器创建完整的特征向量
            # 包含：统计特征 + 上下文特征 + 文本语义嵌入
            feature_vector = feature_extractor.create_feature_vector(sentence, numbers)
            sentence_features.append(feature_vector)
    
    if not numeric_sentences:
        print("文章中未找到包含数字的句子")
        return []
    
    # 初始化 Voyager 索引 (403维：11统计 + 8上下文 + 384文本嵌入)
    feature_dimension = len(sentence_features[0]) if sentence_features else 403
    index = voyager.Index(space=voyager.Space.Cosine, num_dimensions=feature_dimension)
    
    # 添加特征向量到索引
    for j, features in enumerate(sentence_features):
        index.add_item(features, j)
    
    # Voyager 索引通常不需要显式构建
    
    # 处理查询语句的数字特征
    query_numbers = [float(num) for num in re.findall(r'\d+\.?\d*', query_with_numbers)]

    if not query_numbers:
        print("查询语句中未找到数字")
        return []

    # 使用高级特征提取器创建查询特征向量
    query_vector = feature_extractor.create_feature_vector(query_with_numbers, query_numbers)
    
    # 执行搜索
    k = min(3, len(numeric_sentences))
    nearest_ids, distances = index.query(query_vector, k=k)
    
    print(f"数字查询: '{query_with_numbers}'")
    print(f"找到 {len(query_numbers)} 个数字: {query_numbers}")
    print(f"使用高级特征向量（{feature_dimension}维）进行语义搜索")
    print(f"在文章中找到的包含数字的相关句子:")
    print("-" * 60)

    # 显示查询的数字特征分析
    query_stats = feature_extractor.extract_statistical_features(query_numbers)
    print(f"查询数字统计: 数量={query_stats['count']}, 均值={query_stats['mean']:.2f}, "
          f"范围=[{query_stats['min']}, {query_stats['max']}]")

    results = []
    for i, (result_id, distance) in enumerate(zip(nearest_ids, distances)):
        original_id, sentence, numbers = numeric_sentences[result_id]
        similarity_score = 1 - distance  # 余弦相似度

        print(f"{i+1}. 相似度: {similarity_score:.4f}")
        print(f"   包含数字: {numbers}")

        # 显示数字类型分析
        type_counts = {}
        for num in numbers:
            num_type = feature_extractor.classify_number_type(num, sentence)
            type_counts[num_type] = type_counts.get(num_type, 0) + 1
        type_info = ", ".join([f"{t}:{c}" for t, c in type_counts.items()])
        print(f"   数字类型: {type_info}")
        print(f"   内容: {sentence}")
        print()

        results.append((sentence, numbers, similarity_score))
    
    return results

# 测试示例
article_with_numbers = """
公司2023年营业收入达到15.8亿元，同比增长25.3%。第四季度净利润为2.1亿元。
员工总数从2022年的1200人增加到2023年的1500人。研发投入占比达到营业收入的18.5%。
预计2024年第一季度营收将突破20亿元大关。过去三年复合增长率为30.2%。
市场份额从15.8%提升到18.3%，行业排名上升至第5位。
"""

numeric_query = "2023年营收15亿元"
results = numeric_sentence_search(article_with_numbers, numeric_query)