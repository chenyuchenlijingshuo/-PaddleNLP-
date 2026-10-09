"""
舆情分析系统 - 数据处理服务
============================

该模块负责舆情数据的预处理和融合功能，包括：
1. 数据清洗和标准化
2. 文本分词
3. 多源数据融合
4. 热度计算

技术实现：
- 数据清洗：去除HTML标签、特殊字符
- 分词算法：正则表达式提取中英文词汇
- 融合算法：基于时间窗口的加权融合
- 热度计算：新闻权重 × 新闻数量 + 微博权重 × 微博数量

主要函数：
- clean_and_normalize: 文本清洗和标准化
- tokenize_text: 文本分词
- run_fusion: 执行数据融合
"""

import json
import re
from collections import defaultdict
from datetime import datetime, timedelta

from extensions import db
from models import FusedData, FusionConfig, RawData


def clean_and_normalize(text: str) -> str:
    """
    文本清洗和标准化
    
    功能说明：
    - 替换特殊空白字符（全角空格、不间断空格）
    - 去除HTML标签
    - 合并多余空白字符
    
    参数：
    - text: 原始文本
    
    返回值：
    - 清洗后的文本
    """
    text = (text or "").replace("\u3000", " ").replace("\xa0", " ")
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def tokenize_text(text: str):
    """
    文本分词
    
    功能说明：
    - 提取中文词汇（连续汉字）
    - 提取英文词汇（连续字母数字）
    - 过滤停用词
    
    参数：
    - text: 待分词文本
    
    返回值：
    - 词汇列表
    """
    tokens = re.findall(r"[\u4e00-\u9fff]{1,}|[a-z0-9_]{2,}", clean_and_normalize(text).lower())
    stop = {"的", "了", "和", "是", "在", "与", "就", "都", "及", "the", "and", "for"}
    return [t for t in tokens if t not in stop]


def run_fusion():
    """
    执行数据融合
    
    功能说明：
    - 读取融合配置参数
    - 根据时间窗口筛选原始数据
    - 按关键词聚合数据
    - 计算融合热度值
    - 生成摘要文本
    - 存储融合结果
    
    融合算法：
    - 时间窗口：最近N分钟的数据
    - 热度计算：新闻数量 × 新闻权重 + 微博数量 × 微博权重
    - 摘要生成：取前3条数据标题拼接
    
    返回值：
    - 融合统计信息（时间窗口、原始数据数、融合结果数）
    """
    cfg = FusionConfig.query.first() or FusionConfig()
    if not cfg.id:
        db.session.add(cfg)
        db.session.commit()
    end = datetime.utcnow()
    start = end - timedelta(minutes=cfg.time_window_minutes)
    # 方案B：优先使用发布时间；若发布时间不在窗口内，回退到入库时间(created_at)判断
    rows = RawData.query.filter(
        db.or_(
            db.and_(RawData.published_at >= start, RawData.published_at <= end),
            db.and_(RawData.created_at >= start, RawData.created_at <= end),
        )
    ).all()
    bucket = defaultdict(lambda: {"news": 0, "weibo": 0, "samples": []})
    for row in rows:
        keys = [x.strip() for x in (row.keyword_hit or "").split(",") if x.strip()] or tokenize_text(f"{row.title or ''} {row.content or ''}")[:3] or ["未知主题"]
        for kw in keys:
            src = row.source_type if row.source_type in {"news", "weibo"} else "news"
            bucket[kw][src] += 1
            if len(bucket[kw]["samples"]) < 3:
                bucket[kw]["samples"].append(row.title or row.content or "")
    created = 0
    for kw, val in bucket.items():
        score = val["news"] * cfg.weight_news + val["weibo"] * cfg.weight_weibo
        db.session.add(
            FusedData(
                keyword=kw,
                window_start=start,
                window_end=end,
                fused_score=float(score),
                summary_text="；".join([x for x in val["samples"] if x])[:500],
                source_counts_json=json.dumps({"news": val["news"], "weibo": val["weibo"]}, ensure_ascii=False),
            )
        )
        created += 1
    db.session.commit()
    return {"window_start": start.isoformat(), "window_end": end.isoformat(), "raw_count": len(rows), "fused_count": created}
