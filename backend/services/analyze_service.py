"""
舆情分析系统 - 数据分析服务
============================

该模块负责舆情数据的分析功能，包括：
1. TF-IDF关键词提取
2. 热点排行计算
3. 时间趋势分析
4. 来源分布统计

技术实现：
- TF-IDF算法：词频-逆文档频率
- 热度计算：基于融合分值聚合
- 趋势分析：时间序列数据提取
- 来源统计：数据源分类统计

主要函数：
- compute_tfidf_keywords: 计算TF-IDF关键词
- compute_hot_top: 计算热点排行
- compute_trend: 计算时间趋势
"""

import math
import re
from collections import Counter, defaultdict


def _tokenize(text: str):
    """
    文本分词（内部函数）
    
    功能说明：
    - 提取中文词汇（连续汉字）
    - 提取英文词汇（连续字母数字）
    - 过滤停用词
    
    参数：
    - text: 待分词文本
    
    返回值：
    - 词汇列表
    """
    tokens = re.findall(r"[\u4e00-\u9fff]{1,}|[a-z0-9_]{2,}", (text or "").lower())
    stop = {"的", "了", "和", "是", "在", "与", "就", "都", "及", "the", "and", "for"}
    return [t for t in tokens if t not in stop]


def compute_tfidf_keywords(docs, top_k=20):
    """
    计算TF-IDF关键词
    
    功能说明：
    - 对文档集合进行TF-IDF计算
    - 提取权重最高的关键词
    - 返回关键词及其统计信息
    
    算法说明：
    - TF（词频）：词汇在文档中出现的次数
    - IDF（逆文档频率）：log((文档总数+1)/(包含该词的文档数+1))
    - TF-IDF = TF × IDF
    
    参数：
    - docs: 文档列表
    - top_k: 返回前K个关键词
    
    返回值：
    - 关键词列表，包含term、score、tf、df字段
    """
    docs_tokens = [_tokenize(x) for x in docs if (x or "").strip()]
    n_docs = len(docs_tokens)
    if n_docs == 0:
        return []
    df = Counter()
    tf_total = Counter()
    for tokens in docs_tokens:
        tf_total.update(tokens)
        for t in set(tokens):
            df[t] += 1
    scores = []
    for term, tf in tf_total.items():
        idf = math.log((1 + n_docs) / (1 + df[term])) + 1.0
        scores.append((term, tf * idf, tf, df[term]))
    scores.sort(key=lambda x: x[1], reverse=True)
    return [{"term": t, "score": round(s, 6), "tf": tf, "df": d} for t, s, tf, d in scores[:top_k]]


def compute_hot_top(fused_rows, top_n=20):
    """
    计算热点排行
    
    功能说明：
    - 对融合数据按关键词聚合
    - 计算每个关键词的总热度值
    - 返回热度最高的关键词排行
    
    参数：
    - fused_rows: 融合数据列表
    - top_n: 返回前N个关键词
    
    返回值：
    - 热点排行列表，包含keyword和hot_score字段
    """
    agg = defaultdict(float)
    for row in fused_rows:
        agg[row.keyword] += float(row.fused_score or 0.0)
    return [{"keyword": k, "hot_score": round(v, 4)} for k, v in sorted(agg.items(), key=lambda x: x[1], reverse=True)[:top_n]]


def compute_trend(fused_rows, keyword=None):
    """
    计算时间趋势
    
    功能说明：
    - 提取融合数据的时间序列
    - 可选按关键词过滤
    - 返回时间-热度数据点
    
    参数：
    - fused_rows: 融合数据列表
    - keyword: 可选的关键词过滤条件
    
    返回值：
    - 趋势数据列表，包含time、keyword、score字段
    """
    return [
        {"time": row.window_start.isoformat() if row.window_start else None, "keyword": row.keyword, "score": float(row.fused_score or 0.0)}
        for row in fused_rows
        if not keyword or row.keyword == keyword
    ]
