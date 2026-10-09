"""
舆情分析系统 - 内容数据模型
============================

该模块定义内容相关的数据模型，包括：
1. CollectRule: 采集规则模型
2. CollectRunLog: 采集执行日志模型
3. RawData: 原始数据模型
4. FusionConfig: 融合配置模型
5. FusedData: 融合数据模型

数据流程：
1. 用户创建采集规则（CollectRule）
2. 执行采集任务，生成执行日志（CollectRunLog）
3. 采集的原始数据存储（RawData）
4. 根据融合配置（FusionConfig）执行融合
5. 生成融合数据（FusedData）

关联关系：
- CollectRule.run_logs: 规则的所有执行日志
- CollectRule.raw_items: 规则的所有原始数据
- CollectRunLog.rule: 日志所属规则
- RawData.rule: 数据所属规则
"""

from datetime import datetime

from extensions import db


class CollectRule(db.Model):
    """
    采集规则模型
    
    字段说明：
    - id: 规则ID（主键）
    - name: 规则名称
    - keywords: 关键词列表（逗号分隔）
    - time_start: 采集开始时间
    - time_end: 采集结束时间
    - max_count: 最大采集数量
    - source_type: 数据源类型（news/weibo）
    - enabled: 是否启用
    - created_by: 创建者ID
    - created_at: 创建时间
    
    关联关系：
    - run_logs: 规则的所有执行日志
    - raw_items: 规则的所有原始数据
    """
    __tablename__ = "collect_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    keywords = db.Column(db.Text, nullable=False)  # 逗号分隔
    time_start = db.Column(db.DateTime)
    time_end = db.Column(db.DateTime)
    max_count = db.Column(db.Integer, default=100)
    source_type = db.Column(db.String(32), nullable=False)  # news | weibo
    enabled = db.Column(db.Boolean, default=True)
    created_by = db.Column(db.Integer, db.ForeignKey("users.id"))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class CollectRunLog(db.Model):
    """
    采集执行日志模型
    
    字段说明：
    - id: 日志ID（主键）
    - rule_id: 规则ID（外键）
    - status: 执行状态（running/success/failed）
    - message: 日志消息
    - items_fetched: 采集到的数据数量
    - started_at: 开始时间
    - ended_at: 结束时间
    
    关联关系：
    - rule: 日志所属规则
    """
    __tablename__ = "collect_run_logs"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("collect_rules.id"))
    status = db.Column(db.String(32))  # running | success | failed
    message = db.Column(db.Text)
    items_fetched = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime)

    rule = db.relationship("CollectRule", backref="run_logs")


class RawData(db.Model):
    """
    原始数据模型
    
    字段说明：
    - id: 数据ID（主键）
    - rule_id: 规则ID（外键）
    - title: 标题
    - content: 内容
    - published_at: 发布时间（索引）
    - source_name: 来源名称
    - url: 原文链接
    - keyword_hit: 命中的关键词
    - source_type: 数据源类型
    - dedup_hash: 去重哈希值（索引）
    - created_at: 创建时间
    
    关联关系：
    - rule: 数据所属规则
    """
    __tablename__ = "raw_data"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("collect_rules.id"))
    title = db.Column(db.String(512))
    content = db.Column(db.Text)
    published_at = db.Column(db.DateTime, index=True)
    source_name = db.Column(db.String(128))
    url = db.Column(db.String(1024))
    keyword_hit = db.Column(db.String(256))
    source_type = db.Column(db.String(32))
    dedup_hash = db.Column(db.String(64), index=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    rule = db.relationship("CollectRule", backref="raw_items")


class FusionConfig(db.Model):
    """
    融合配置模型
    
    字段说明：
    - id: 配置ID（主键）
    - time_window_minutes: 时间窗口（分钟）
    - weight_news: 新闻权重
    - weight_weibo: 微博权重
    - updated_at: 更新时间
    
    说明：
    - 系统只维护一条配置记录
    - 用于控制数据融合的参数
    """
    __tablename__ = "fusion_config"

    id = db.Column(db.Integer, primary_key=True)
    time_window_minutes = db.Column(db.Integer, default=60)
    weight_news = db.Column(db.Float, default=1.0)
    weight_weibo = db.Column(db.Float, default=0.8)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class FusedData(db.Model):
    __tablename__ = "fused_data"

    id = db.Column(db.Integer, primary_key=True)
    keyword = db.Column(db.String(256), nullable=False, index=True)
    window_start = db.Column(db.DateTime, nullable=False, index=True)
    window_end = db.Column(db.DateTime, nullable=False)
    fused_score = db.Column(db.Float, default=0.0)
    summary_text = db.Column(db.Text)
    source_counts_json = db.Column(db.Text)  # JSON string
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
