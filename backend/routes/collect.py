"""
舆情分析系统 - 数据采集路由
============================

该模块负责数据采集相关的API接口，包括：
1. 采集规则管理（创建、查询、更新、删除、启用/禁用）
2. 执行采集任务
3. 查询采集日志
4. 查询采集数据

权限控制：
- admin: 可创建/编辑/删除采集规则，可执行采集
- user: 可创建/编辑/删除采集规则，可执行采集
- viewer: 无权限

采集类型：
- 新闻采集：模拟数据采集
- 微博采集：真实爬虫采集

API接口：
- GET /api/collect/rules: 查询采集规则列表
- POST /api/collect/rules: 创建采集规则
- PUT /api/collect/rules/<id>: 更新采集规则
- DELETE /api/collect/rules/<id>: 删除采集规则（管理员权限）
- POST /api/collect/run/<id>: 执行采集任务
- GET /api/collect/logs: 查询采集日志
- GET /api/collect/data: 查询采集数据
"""

from datetime import datetime

from flask import Blueprint, g, request

from decorators import jwt_required_custom, role_required
from extensions import db
from models import CollectRule, RawData
from services.collector_service import run_collect_by_rule
from utils.response import err, ok

collect_bp = Blueprint("collect", __name__)


def _parse_dt(v):
    """解析ISO格式的时间字符串"""
    try:
        return datetime.fromisoformat(str(v)) if v else None
    except Exception:
        return None


@collect_bp.get("/rules")
@jwt_required_custom
@role_required("admin", "user")
def list_rules():
    page = request.args.get("page", 1, type=int)
    size = request.args.get("size", 20, type=int)
    
    query = CollectRule.query.order_by(CollectRule.id.desc())
    total = query.count()
    rows = query.offset((page - 1) * size).limit(size).all()
    
    return ok(
        {
            "items": [
                {
                    "id": r.id,
                    "name": r.name,
                    "keywords": r.keywords,
                    "topic_keywords": r.topic_keywords,
                    "max_count": r.max_count,
                    "source_type": r.source_type,
                    "enabled": r.enabled,
                    "time_start": r.time_start.isoformat() if r.time_start else None,
                    "time_end": r.time_end.isoformat() if r.time_end else None,
                }
                for r in rows
            ],
            "total": total,
            "page": page,
            "size": size,
        }
    )


@collect_bp.post("/rules")
@jwt_required_custom
@role_required("admin", "user")
def create_rule():
    data = request.get_json(silent=True) or {}
    rule = CollectRule(
        name=(data.get("name") or "").strip(),
        keywords=(data.get("keywords") or "").strip(),
        topic_keywords=(data.get("topic_keywords") or "").strip(),
        time_start=_parse_dt(data.get("time_start")),
        time_end=_parse_dt(data.get("time_end")),
        max_count=int(data.get("max_count") or 100),
        source_type=(data.get("source_type") or "news").strip(),
        enabled=bool(data.get("enabled", True)),
        created_by=g.current_user.id,
    )
    if not rule.name or not rule.keywords:
        return err("name 和 keywords 不能为空")
    if rule.source_type not in {"news", "weibo"}:
        return err("source_type 仅支持 news/weibo")
    db.session.add(rule)
    db.session.commit()
    return ok({"id": rule.id}, "规则创建成功")


@collect_bp.put("/rules/<int:rule_id>")
@jwt_required_custom
@role_required("admin", "user")
def update_rule(rule_id: int):
    row = db.session.get(CollectRule, rule_id)
    if not row:
        return err("规则不存在", code=404, http_status=404)
    data = request.get_json(silent=True) or {}
    for field in ["name", "keywords", "topic_keywords", "source_type"]:
        if field in data:
            setattr(row, field, (data.get(field) or "").strip())
    if "max_count" in data:
        row.max_count = int(data.get("max_count") or 100)
    if "enabled" in data:
        row.enabled = bool(data.get("enabled"))
    if "time_start" in data:
        row.time_start = _parse_dt(data.get("time_start"))
    if "time_end" in data:
        row.time_end = _parse_dt(data.get("time_end"))
    db.session.commit()
    return ok({"id": row.id}, "规则已更新")


@collect_bp.put("/rules/<int:rule_id>/toggle")
@jwt_required_custom
@role_required("admin", "user")
def toggle_rule(rule_id: int):
    row = db.session.get(CollectRule, rule_id)
    if not row:
        return err("规则不存在", code=404, http_status=404)
    
    row.enabled = not row.enabled
    db.session.commit()
    
    status = "已启用" if row.enabled else "已禁用"
    return ok({
        "id": row.id,
        "enabled": row.enabled,
        "message": f"规则{status}"
    }, f"规则{status}")


@collect_bp.delete("/rules/<int:rule_id>")
@jwt_required_custom
@role_required("admin")
def delete_rule(rule_id: int):
    row = db.session.get(CollectRule, rule_id)
    if not row:
        return err("规则不存在", code=404, http_status=404)
    db.session.delete(row)
    db.session.commit()
    return ok(message="规则已删除")


@collect_bp.post("/run/<int:rule_id>")
@jwt_required_custom
@role_required("admin", "user")
def run_collect(rule_id: int):
    result = run_collect_by_rule(rule_id)
    return ok(result, "采集执行完成") if result.get("success") else err(result.get("message") or "执行失败")


@collect_bp.get("/raw")
@jwt_required_custom
@role_required("admin", "user")
def query_raw():
    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 20)), 1), 200)
    q = RawData.query.order_by(RawData.created_at.desc())
    p = q.paginate(page=page, per_page=size, error_out=False)
    items = [
        {
            "id": x.id,
            "title": x.title,
            "source_type": x.source_type,
            "published_at": x.published_at.isoformat() if x.published_at else None,
        }
        for x in p.items
    ]
    return ok({"items": items, "total": p.total, "page": page, "size": size})


@collect_bp.delete("/raw/<int:item_id>")
@jwt_required_custom
@role_required("admin", "user")
def delete_raw(item_id: int):
    row = db.session.get(RawData, item_id)
    if not row:
        return err("数据不存在", code=404, http_status=404)
    db.session.delete(row)
    db.session.commit()
    return ok(message="删除成功")


@collect_bp.post("/raw/dedup")
@jwt_required_custom
@role_required("admin", "user")
def dedup_raw():
    rows = RawData.query.order_by(RawData.id.asc()).all()
    seen, deleted = set(), 0
    for row in rows:
        if not row.dedup_hash:
            continue
        if row.dedup_hash in seen:
            db.session.delete(row)
            deleted += 1
        else:
            seen.add(row.dedup_hash)
    db.session.commit()
    return ok({"deleted_count": deleted}, "去重完成")