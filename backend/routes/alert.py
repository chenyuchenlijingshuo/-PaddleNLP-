"""
舆情分析系统 - 预警管理路由
============================

该模块负责预警管理相关的API接口，包括：
1. 预警规则管理（创建、查询、更新、删除）
2. 执行预警扫描
3. 查询预警日志

权限控制：
- admin: 可创建/编辑/删除预警规则，可执行扫描
- user: 可创建/编辑/删除预警规则，可执行扫描
- viewer: 只能查看预警规则和日志

预警类型：
- 阈值预警：基于热度值的预警
- 敏感词预警：基于关键词匹配的预警

两级预警：
- 一级预警：轻度预警
- 二级预警：重度预警

API接口：
- GET /api/alert/rules: 查询预警规则列表
- POST /api/alert/rules: 创建预警规则
- PUT /api/alert/rules/<id>: 更新预警规则
- DELETE /api/alert/rules/<id>: 删除预警规则
- POST /api/alert/scan: 执行预警扫描
- GET /api/alert/logs: 查询预警日志
"""

from flask import Blueprint, request

from decorators import jwt_required_custom, role_required
from extensions import db
from models import AlertLog, AlertRule
from services.alert_service import run_alert_scan
from utils.response import err, ok

alert_bp = Blueprint("alert", __name__)


@alert_bp.get("/rules")
@jwt_required_custom
@role_required("admin", "user", "viewer")
def list_alert_rules():
    rows = AlertRule.query.order_by(AlertRule.id.desc()).all()
    return ok([
        {
            "id": x.id, 
            "name": x.name, 
            "metric_type": x.metric_type, 
            "threshold_value": x.threshold_value,
            "level1_threshold": x.level1_threshold,
            "level2_threshold": x.level2_threshold,
            "sensitive_words": x.sensitive_words,
            "enabled": x.enabled
        } 
        for x in rows
    ])


@alert_bp.post("/rules")
@jwt_required_custom
@role_required("admin")
def create_alert_rule():
    data = request.get_json(silent=True) or {}
    metric_type = (data.get("metric_type") or "").strip()
    if metric_type not in {"threshold", "sensitive"}:
        return err("metric_type 仅支持 threshold/sensitive")
    
    level1_threshold = float(data.get("level1_threshold") or 0)
    level2_threshold = float(data.get("level2_threshold") or 0)
    
    row = AlertRule(
        name=(data.get("name") or "").strip(),
        metric_type=metric_type,
        threshold_value=level1_threshold,
        level1_threshold=level1_threshold,
        level2_threshold=level2_threshold,
        sensitive_words=(data.get("sensitive_words") or "").strip(),
        enabled=bool(data.get("enabled", True)),
    )
    if not row.name:
        return err("name 不能为空")
    db.session.add(row)
    db.session.commit()
    return ok({"id": row.id}, "预警规则创建成功")


@alert_bp.put("/rules/<int:rule_id>")
@jwt_required_custom
@role_required("admin")
def update_alert_rule(rule_id: int):
    row = db.session.get(AlertRule, rule_id)
    if not row:
        return err("规则不存在", code=404, http_status=404)
    data = request.get_json(silent=True) or {}
    for k in ["name", "metric_type", "sensitive_words"]:
        if k in data:
            setattr(row, k, (data.get(k) or "").strip())
    if "enabled" in data:
        row.enabled = bool(data.get("enabled"))
    db.session.commit()
    return ok(message="规则更新成功")


@alert_bp.delete("/rules/<int:rule_id>")
@jwt_required_custom
@role_required("admin")
def delete_alert_rule(rule_id: int):
    row = db.session.get(AlertRule, rule_id)
    if not row:
        return err("规则不存在", code=404, http_status=404)
    db.session.delete(row)
    db.session.commit()
    return ok(message="规则删除成功")


@alert_bp.post("/scan")
@jwt_required_custom
@role_required("admin", "user")
def manual_scan():
    return ok(run_alert_scan(), "扫描完成")


@alert_bp.get("/logs")
@jwt_required_custom
@role_required("admin", "user", "viewer")
def alert_logs():
    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 20)), 1), 200)
    q = AlertLog.query.order_by(AlertLog.triggered_at.desc())
    p = q.paginate(page=page, per_page=size, error_out=False)
    items = [
        {
            "id": x.id,
            "rule_id": x.rule_id,
            "level": x.level,
            "message": x.message,
            "triggered_at": x.triggered_at.isoformat() if x.triggered_at else None,
        }
        for x in p.items
    ]
    return ok({"items": items, "total": p.total, "page": page, "size": size})
