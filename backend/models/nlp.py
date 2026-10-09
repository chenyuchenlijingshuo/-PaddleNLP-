"""
舆情分析系统 - NLP数据模型
===========================

该模块定义NLP（自然语言处理）相关的数据模型，包括：
1. SentimentResult: 情感分析结果模型

功能说明：
- 存储PaddleNLP情感分析的结果
- 与原始数据（RawData）一对一关联
- 支持情感标签（正面/负面/中性）和置信度分数

关联关系：
- SentimentResult.raw: 关联的原始数据
- RawData.sentiment_result: 原始数据的情感分析结果
"""

from datetime import datetime

from extensions import db


class SentimentResult(db.Model):
    """
    情感分析结果模型
    
    字段说明：
    - id: 结果ID（主键）
    - raw_id: 原始数据ID（外键，唯一，索引）
    - label: 情感标签（positive/negative/neutral/unknown，索引）
    - score: 置信度分数
    - created_at: 创建时间（索引）
    - updated_at: 更新时间（索引）
    
    关联关系：
    - raw: 关联的原始数据（一对一）
    
    说明：
    - 每条原始数据最多对应一条情感分析结果
    - 支持更新情感分析结果
    """
    __tablename__ = "sentiment_results"

    id = db.Column(db.Integer, primary_key=True)
    raw_id = db.Column(db.Integer, db.ForeignKey("raw_data.id"), nullable=False, index=True, unique=True)
    label = db.Column(db.String(64), nullable=False, default="unknown", index=True)
    score = db.Column(db.Float)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, index=True)

    # 一对一关联：每条原始数据对应一条情感分析结果
    raw = db.relationship("RawData", backref=db.backref("sentiment_result", uselist=False))

