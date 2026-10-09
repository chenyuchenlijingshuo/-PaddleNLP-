"""
舆情分析系统 - 预警服务
========================

该模块负责舆情预警功能，包括：
1. 阈值预警（基于热度值）
2. 敏感词预警（基于关键词匹配）
3. 两级预警机制（一级轻度、二级重度）
4. 预警日志记录

技术实现：
- 阈值预警：统计近1小时热度值
- 敏感词预警：统计近24小时命中次数
- 两级预警：根据阈值自动分级
- 日志记录：记录预警详情和数据快照

主要函数：
- run_alert_scan: 执行预警扫描
- _level_by_threshold: 根据阈值判断预警级别
"""

import json
from datetime import datetime, timedelta

from extensions import db
from models import AlertLog, AlertRule, FusedData, RawData


def _split_words(words: str):
    """
    分割敏感词列表
    
    功能说明：
    - 按逗号分割敏感词字符串
    - 去除空白项
    
    参数：
    - words: 敏感词字符串（逗号分隔）
    
    返回值：
    - 敏感词列表
    """
    return [x.strip() for x in (words or "").split(",") if x.strip()]


def _level_by_threshold(value: float, lv1: float, lv2: float):
    """
    根据阈值判断预警级别
    
    功能说明：
    - 数值达到二级阈值返回2（重度预警）
    - 数值达到一级阈值返回1（轻度预警）
    - 数值未达阈值返回0（无预警）
    
    参数：
    - value: 当前数值
    - lv1: 一级阈值
    - lv2: 二级阈值
    
    返回值：
    - 预警级别（0/1/2）
    """
    if lv2 and value >= lv2:
        return 2
    if lv1 and value >= lv1:
        return 1
    return 0


def run_alert_scan():
    """
    执行预警扫描
    
    功能说明：
    - 查询所有启用的预警规则
    - 执行阈值预警检查（统计近1小时热度）
    - 执行敏感词预警检查（统计近24小时命中次数）
    - 根据阈值判断预警级别
    - 记录预警日志
    
    预警类型：
    1. 阈值预警：
       - 统计近1小时融合数据热度值
       - 热度值超过阈值触发预警
       - 支持两级预警（一级轻度、二级重度）
    
    2. 敏感词预警：
       - 统计近24小时原始数据敏感词命中次数
       - 命中次数超过阈值触发预警
       - 支持两级预警（一级轻度、二级重度）
    
    返回值：
    - 触发的预警数量和详细日志
    """
    rules = AlertRule.query.filter_by(enabled=True).all()
    triggered = 0
    logs = []
    for rule in rules:
        result = None
        if rule.metric_type == "threshold":
            # 阈值预警：统计近1小时热度值
            one_hour_ago = datetime.utcnow() - timedelta(hours=1)
            rows = FusedData.query.filter(FusedData.window_start >= one_hour_ago).all()
            total_score = sum(float(x.fused_score or 0.0) for x in rows)
            threshold = float(rule.threshold_value or 0.0)
            if threshold <= 0 or total_score >= threshold:
                level = _level_by_threshold(total_score, float(rule.level1_threshold or threshold or 0), float(rule.level2_threshold or threshold or 0)) or 1
                result = (level, f"[阈值预警] 近1小时热度={total_score:.2f}", {"total_score_1h": total_score, "count": len(rows)})
        elif rule.metric_type == "sensitive":
            # 敏感词预警：统计近24小时命中次数
            words = _split_words(rule.sensitive_words)
            if words:
                one_day_ago = datetime.utcnow() - timedelta(hours=24)
                rows = RawData.query.filter(RawData.created_at >= one_day_ago).all()
                hit_count = 0
                hits = []
                for x in rows:
                    text = f"{x.title or ''} {x.content or ''}"
                    hit_words = [w for w in words if w in text]
                    if hit_words:
                        hit_count += len(hit_words)
                        hits.append({"id": x.id, "words": hit_words, "title": x.title or ""})
                if hit_count > 0:
                    level = _level_by_threshold(float(hit_count), float(rule.level1_threshold or 1), float(rule.level2_threshold or 5)) or 1
                    result = (level, f"[敏感词预警] 24小时命中次数={hit_count}", {"hit_count": hit_count, "hits": hits[:20]})
        if result:
            level, message, snapshot = result
            db.session.add(AlertLog(rule_id=rule.id, level=level, message=message, data_snapshot=json.dumps(snapshot, ensure_ascii=False)))
            triggered += 1
            logs.append({"rule_id": rule.id, "rule_name": rule.name, "level": level, "message": message})
    db.session.commit()
    return {"triggered": triggered, "logs": logs}
