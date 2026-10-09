"""
舆情分析系统 - 预警数据模型
============================

该模块定义预警相关的数据模型，包括：
1. AlertRule: 预警规则模型
2. AlertLog: 预警日志模型

预警类型：
- threshold: 阈值预警（基于热度值）
- sensitive: 敏感词预警（基于关键词匹配）

两级预警：
- 一级预警：轻度预警（level=1）
- 二级预警：重度预警（level=2）

关联关系：
- AlertRule.logs: 规则的所有预警日志
- AlertLog.rule: 日志所属规则
"""

from datetime import datetime

from extensions import db


class AlertRule(db.Model):
    """
    预警规则模型
    
    字段说明：
    - id: 规则ID（主键）
    - name: 规则名称
    - metric_type: 预警类型（threshold/sensitive）
    - threshold_value: 阈值（热度/条数）
    - level1_threshold: 一级预警阈值
    - level2_threshold: 二级预警阈值
    - sensitive_words: 敏感词列表（逗号分隔）
    - enabled: 是否启用
    - scan_cron: 扫描周期（cron表达式）
    - created_at: 创建时间
    
    关联关系：
    - logs: 规则的所有预警日志
    """
    __tablename__ = "alert_rules"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    metric_type = db.Column(db.String(32), nullable=False)  # threshold | sensitive
    threshold_value = db.Column(db.Float)  # 热度/条数阈值
    level1_threshold = db.Column(db.Float)  # 一级预警阈值
    level2_threshold = db.Column(db.Float)  # 二级预警阈值
    sensitive_words = db.Column(db.Text)  # 逗号分隔
    enabled = db.Column(db.Boolean, default=True)
    scan_cron = db.Column(db.String(64))  # 可选 cron 表达式简化：如 */30 * * * *
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class AlertLog(db.Model):
    """
    预警日志模型
    
    字段说明：
    - id: 日志ID（主键）
    - rule_id: 规则ID（外键）
    - level: 预警级别（1或2）
    - message: 预警消息
    - data_snapshot: 数据快照（JSON格式）
    - triggered_at: 触发时间（索引）
    
    关联关系：
    - rule: 日志所属规则
    """
    __tablename__ = "alert_logs"

    id = db.Column(db.Integer, primary_key=True)
    rule_id = db.Column(db.Integer, db.ForeignKey("alert_rules.id"))
    level = db.Column(db.Integer)  # 1 or 2
    message = db.Column(db.Text)
    data_snapshot = db.Column(db.Text)
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow, index=True)

    rule = db.relationship("AlertRule", backref="logs")
