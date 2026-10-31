"""
微博平台下消费数码新品首发的舆情洞察与策略分析 —— 预警管理路由
================================================================

API 端点：
- GET    /api/alert/rules        查询规则列表
- POST   /api/alert/rules        创建规则
- PUT    /api/alert/rules/<id>   更新规则
- DELETE /api/alert/rules/<id>   删除规则
- POST   /api/alert/scan         手动触发扫描
- GET    /api/alert/logs         分页查询日志（带 category / chart_path）
- GET    /api/alert/chart/<path> 访问 Matplotlib 生成的 PNG（Ch16 产物）
- POST   /api/alert/seed-defaults 一键写入 iPhone Duo 首发默认规则组
"""

from flask import Blueprint, current_app, send_from_directory, request
from pathlib import Path

from decorators import jwt_required_custom, role_required
from extensions import db
from models import AlertLog, AlertRule
from models.alert import (
    CATEGORY_GENERAL,
    CATEGORY_LABELS,
    CATEGORY_LAUNCH_DAY,
    CATEGORY_POST_LAUNCH,
    CATEGORY_PRE_LAUNCH,
    DEFAULT_LAUNCH_NEGATIVE,
    DEFAULT_LAUNCH_POSITIVE,
    VALID_CATEGORIES,
)
from services.alert_service import run_alert_scan
from utils.response import err, ok

alert_bp = Blueprint("alert", __name__)

VALID_METRIC_TYPES = {"threshold", "sensitive", "anomaly", "launch_campaign"}  


# —— 序列化辅助——

def _rule_to_dict(r: AlertRule) -> dict:   
    return {
        "id": r.id,
        "name": r.name,
        "metric_type": r.metric_type,
        "rule_category": r.rule_category or CATEGORY_GENERAL,
        "category_label": CATEGORY_LABELS.get(r.rule_category or CATEGORY_GENERAL, "通用"), 
        "threshold_value": r.threshold_value,
        "level1_threshold": r.level1_threshold,
        "level2_threshold": r.level2_threshold,
        "sensitive_words": r.sensitive_words,
        "positive_words": r.positive_words,
        "negative_words": r.negative_words,
        "anomaly_window_minutes": r.anomaly_window_minutes,
        "zscore_threshold": r.zscore_threshold,
        "enabled": r.enabled,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


def _log_to_dict(x: AlertLog) -> dict:
    return {
        "id": x.id,
        "rule_id": x.rule_id,
        "category": x.category or CATEGORY_GENERAL,
        "metric_type": x.metric_type,
        "level": x.level,
        "message": x.message,
        "chart_path": x.chart_path,
        "triggered_at": x.triggered_at.isoformat() if x.triggered_at else None,
    }

@alert_bp.get("/rules")
@jwt_required_custom
@role_required("admin", "user", "viewer")
def list_alert_rules():
    rows = AlertRule.query.order_by(AlertRule.id.desc()).all()
    return ok([_rule_to_dict(r) for r in rows]) 


@alert_bp.post("/rules")
@jwt_required_custom
@role_required("admin")
def create_alert_rule():
    data = request.get_json(silent=True) or {}
    metric_type = (data.get("metric_type") or "").strip()  
    if metric_type not in VALID_METRIC_TYPES:
        return err(f"metric_type 仅支持 {sorted(VALID_METRIC_TYPES)}")  

    category = (data.get("rule_category") or CATEGORY_GENERAL).strip()
    if category not in VALID_CATEGORIES:  
        return err(f"rule_category 仅支持 {sorted(VALID_CATEGORIES)}")

    name = (data.get("name") or "").strip()
    if not name:   
        return err("name 不能为空")

    neg = (data.get("negative_words") or "").strip()
    pos = (data.get("positive_words") or "").strip()
    if metric_type == "launch_campaign":  
        neg = neg or DEFAULT_LAUNCH_NEGATIVE
        pos = pos or DEFAULT_LAUNCH_POSITIVE

    try:
        lv1 = float(data.get("level1_threshold") or 0)
        lv2 = float(data.get("level2_threshold") or 0)
    except (TypeError, ValueError):   
        return err("阈值必须是数字")

    
    row = AlertRule(
        name=name, metric_type=metric_type, rule_category=category,
        threshold_value=float(data.get("threshold_value") or lv1),
        level1_threshold=lv1, level2_threshold=lv2,
        sensitive_words=(data.get("sensitive_words") or "").strip(),
        positive_words=pos, negative_words=neg,
        anomaly_window_minutes=int(data.get("anomaly_window_minutes") or 60),
        zscore_threshold=float(data.get("zscore_threshold") or 2.5),
        enabled=bool(data.get("enabled", True)),
    )
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
    if "name" in data:
        row.name = (data.get("name") or "").strip() or row.name
    if "metric_type" in data and data["metric_type"] in VALID_METRIC_TYPES:
        row.metric_type = data["metric_type"]
    if "rule_category" in data and data["rule_category"] in VALID_CATEGORIES:
        row.rule_category = data["rule_category"]
    for k in ("sensitive_words", "positive_words", "negative_words"):
        if k in data:
            setattr(row, k, (data.get(k) or "").strip())
    for k, caster in (
        ("level1_threshold", float), ("level2_threshold", float),
        ("threshold_value", float), ("zscore_threshold", float),
    ):
        if k in data:
            try:
                setattr(row, k, caster(data[k]))
            except (TypeError, ValueError):
                return err(f"{k} 必须是数字")
    if "anomaly_window_minutes" in data:
        try:
            row.anomaly_window_minutes = int(data["anomaly_window_minutes"])
        except (TypeError, ValueError):
            return err("anomaly_window_minutes 必须是整数")       
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
    result = run_alert_scan()
    return ok(result, f"扫描完成，触发 {result.get('triggered', 0)} 条")


@alert_bp.get("/logs")
@jwt_required_custom
@role_required("admin", "user", "viewer")
def alert_logs():
    page = max(int(request.args.get("page", 1)), 1)  
    size = min(max(int(request.args.get("size", 20)), 1), 200) 
    q = AlertLog.query.order_by(AlertLog.triggered_at.desc())
    
    category = (request.args.get("category") or "").strip()
    if category in VALID_CATEGORIES:
        q = q.filter(AlertLog.category == category)
    p = q.paginate(page=page, per_page=size, error_out=False)
    items = [_log_to_dict(x) for x in p.items] 
    return ok({"items": items, "total": p.total, "page": page, "size": size})


@alert_bp.get("/chart/<path:filename>")
@jwt_required_custom
@role_required("admin", "user", "viewer")
def alert_chart(filename: str):
    """
    返回 Matplotlib 生成的 PNG。
    filename 形如 data/alerts/rule1_heat_20240101_120000.png
    String：strip 安全清洗；
    """
    project_root = Path(current_app.root_path)  
    chart_dir = project_root / "data" / "alerts"
    cleaned = filename.replace("..", "")  
    for prefix in ("data/alerts/", "data\\alerts/", "/"):   
        if cleaned.startswith(prefix):
            cleaned = cleaned[len(prefix):]
    return send_from_directory(str(chart_dir), cleaned, mimetype="image/png")


@alert_bp.post("/seed-defaults")
@jwt_required_custom
@role_required("admin")
def seed_defaults():
    """写入 iPhone Duo 首发默认规则组。"""
    defaults = [
        AlertRule(
            name="iPhone Duo 首发前-黄牛价格预热",
            metric_type="launch_campaign", rule_category=CATEGORY_PRE_LAUNCH,
            threshold_value=15, level1_threshold=15, level2_threshold=40,
            enabled=True,
        ),
        AlertRule(
            name="iPhone Duo 首发日-热度异常检测",
            metric_type="anomaly", rule_category=CATEGORY_LAUNCH_DAY,
            anomaly_window_minutes=30, zscore_threshold=2.5,
            level1_threshold=2.5, level2_threshold=3.75, enabled=True,
        ),
        AlertRule(
            name="iPhone Duo 首发日-负面情感集中爆发",
            metric_type="launch_campaign", rule_category=CATEGORY_LAUNCH_DAY,
            level1_threshold=0.3, level2_threshold=0.5, enabled=True,
        ),
        AlertRule(
            name="iPhone Duo 首发后-BUG/硬件/差评集中",
            metric_type="launch_campaign", rule_category=CATEGORY_POST_LAUNCH,
            threshold_value=12, level1_threshold=12, level2_threshold=30, enabled=True,
        ),
        AlertRule(
            name="iPhone Duo 通用-敏感词",
            metric_type="sensitive", rule_category=CATEGORY_GENERAL,
            sensitive_words="炸屏,黑屏,系统崩溃,发热警告,黄牛加价",
            level1_threshold=3, level2_threshold=15,
            negative_words=DEFAULT_LAUNCH_NEGATIVE,
            positive_words=DEFAULT_LAUNCH_POSITIVE, enabled=True,
        ),
    ]
    existing = {(r.name, r.metric_type) for r in AlertRule.query.all()}   
    added = 0
    for r in defaults:
        if (r.name, r.metric_type) in existing:  
            continue
        db.session.add(r)
        added += 1   
    db.session.commit()
    return ok({"added": added}, f"已写入 {added} 条默认规则（已存在的跳过）")
