"""
舆情分析系统 - 数据模型包
==========================

该模块负责导入和导出所有数据模型类，包括：
1. 用户模型（User, LoginLog）
2. 内容模型（CollectRule, CollectRunLog, RawData, FusionConfig, FusedData）
3. 预警模型（AlertRule, AlertLog）
4. NLP模型（SentimentResult）

数据模型关系：
- User: 用户账户信息
- LoginLog: 用户登录日志
- CollectRule: 采集规则配置
- CollectRunLog: 采集执行日志
- RawData: 原始采集数据
- FusionConfig: 融合配置参数
- FusedData: 融合后的数据
- AlertRule: 预警规则配置
- AlertLog: 预警触发日志
- SentimentResult: 情感分析结果
"""

from models.user import User, LoginLog
from models.content import (
    CollectRule,
    CollectRunLog,
    RawData,
    FusionConfig,
    FusedData,
)
from models.alert import AlertRule, AlertLog
from models.nlp import SentimentResult

__all__ = [
    "User",
    "LoginLog",
    "CollectRule",
    "CollectRunLog",
    "RawData",
    "FusionConfig",
    "FusedData",
    "AlertRule",
    "AlertLog",
    "SentimentResult",
]
