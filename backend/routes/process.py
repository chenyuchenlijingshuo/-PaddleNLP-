"""
舆情分析系统 - 数据处理路由
============================

该模块负责数据处理相关的API接口，包括：
1. 数据预处理（清洗、分词）
2. 数据融合（多源数据聚合）
3. 融合配置管理
4. 数据导出（管理员权限）
5. 批量情感分析

权限控制：
- admin: 可执行预处理、融合、修改配置、导出数据
- user: 可执行预处理、融合
- viewer: 只能查看数据

技术实现：
- 数据清洗：去除HTML标签、特殊字符
- 文本分词：提取关键词
- 数据融合：基于时间窗口的加权融合
- 数据导出：CSV格式导出

API接口：
- POST /api/process/preprocess/run: 执行预处理
- POST /api/process/fusion/run: 执行融合
- GET /api/process/fusion/config: 获取融合配置
- PUT /api/process/fusion/config: 更新融合配置（管理员权限）
- GET /api/process/fused: 查询融合数据
- GET /api/process/export: 导出数据（管理员权限）
- POST /api/process/sentiment/batch: 批量情感分析
"""

import csv
import io
import json
from datetime import datetime, timedelta

from flask import Blueprint, Response, request

from decorators import jwt_required_custom, role_required
from extensions import db
from models import FusedData, FusionConfig, RawData
from services.nlp_batch_service import run_sentiment_batch
from services.process_service import clean_and_normalize, run_fusion, tokenize_text
from utils.response import err, ok

process_bp = Blueprint("process", __name__)


@process_bp.post("/preprocess/run")
@jwt_required_custom
@role_required("admin", "user")
def preprocess_run():
    rows = RawData.query.order_by(RawData.id.desc()).limit(1000).all()
    affected = 0
    for row in rows:
        after = clean_and_normalize(row.content or "")
        if after != (row.content or ""):
            row.content = after
            affected += 1
        row.keyword_hit = ",".join(tokenize_text(f"{row.title or ''} {row.content or ''}")[:20])
    db.session.commit()
    return ok({"total": len(rows), "updated": affected}, "预处理完成")


@process_bp.get("/fusion/config")
@jwt_required_custom
@role_required("admin", "user")
def get_fusion_config():
    cfg = FusionConfig.query.first() or FusionConfig()
    if not cfg.id:
        db.session.add(cfg)
        db.session.commit()
    return ok({"time_window_minutes": cfg.time_window_minutes, "weight_news": cfg.weight_news, "weight_weibo": cfg.weight_weibo})


@process_bp.put("/fusion/config")
@jwt_required_custom
@role_required("admin")
def update_fusion_config():
    cfg = FusionConfig.query.first() or FusionConfig()
    data = request.get_json(silent=True) or {}
    if "time_window_minutes" in data:
        cfg.time_window_minutes = int(data.get("time_window_minutes") or 60)
    if "weight_news" in data:
        cfg.weight_news = float(data.get("weight_news") or 1.0)
    if "weight_weibo" in data:
        cfg.weight_weibo = float(data.get("weight_weibo") or 0.8)
    if not cfg.id:
        db.session.add(cfg)
    db.session.commit()
    return ok(message="融合配置已更新")


@process_bp.post("/fusion/run")
@jwt_required_custom
@role_required("admin", "user")
def fusion_run():
    return ok(run_fusion(), "融合执行完成")


@process_bp.post("/nlp/sentiment/run")
@jwt_required_custom
@role_required("admin", "user")
def run_sentiment_job():
    data = request.get_json(silent=True) or {}
    limit = int(data.get("limit") or 200)
    only_missing = bool(data.get("only_missing", True))
    result = run_sentiment_batch(limit=limit, only_missing=only_missing)
    return ok(result, "情感分析执行完成") if result.get("success") else err(result.get("message") or "执行失败")


@process_bp.get("/fused")
@jwt_required_custom
def fused_list():
    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 20)), 1), 200)
    q = FusedData.query.order_by(FusedData.window_start.desc())
    p = q.paginate(page=page, per_page=size, error_out=False)
    items = [
        {
            "id": x.id,
            "keyword": x.keyword,
            "window_start": x.window_start.isoformat() if x.window_start else None,
            "fused_score": x.fused_score,
        }
        for x in p.items
    ]
    return ok({"items": items, "total": p.total, "page": page, "size": size})


@process_bp.post("/fused")
@jwt_required_custom
@role_required("admin")
def fused_create():
    data = request.get_json(silent=True) or {}
    row = FusedData(
        keyword=(data.get("keyword") or "").strip(),
        window_start=datetime.fromisoformat(data.get("window_start")) if data.get("window_start") else datetime.utcnow() - timedelta(hours=1),
        window_end=datetime.fromisoformat(data.get("window_end")) if data.get("window_end") else datetime.utcnow(),
        fused_score=float(data.get("fused_score") or 0),
        summary_text=(data.get("summary_text") or "").strip(),
        source_counts_json=json.dumps(data.get("source_counts") or {}, ensure_ascii=False),
    )
    if not row.keyword:
        return err("keyword 不能为空")
    db.session.add(row)
    db.session.commit()
    return ok({"id": row.id}, "新增融合数据成功")


@process_bp.put("/fused/<int:item_id>")
@jwt_required_custom
@role_required("admin")
def fused_update(item_id: int):
    row = db.session.get(FusedData, item_id)
    if not row:
        return err("记录不存在", code=404, http_status=404)
    data = request.get_json(silent=True) or {}
    if "keyword" in data:
        row.keyword = (data.get("keyword") or "").strip()
    if "fused_score" in data:
        row.fused_score = float(data.get("fused_score") or 0)
    db.session.commit()
    return ok(message="更新成功")


@process_bp.delete("/fused/<int:item_id>")
@jwt_required_custom
@role_required("admin")
def fused_delete(item_id: int):
    row = db.session.get(FusedData, item_id)
    if not row:
        return err("记录不存在", code=404, http_status=404)
    db.session.delete(row)
    db.session.commit()
    return ok(message="删除成功")


@process_bp.get("/fused/export.csv")
@jwt_required_custom
@role_required("admin")
def fused_export_csv():
    rows = FusedData.query.order_by(FusedData.id.asc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "keyword", "window_start", "window_end", "fused_score", "summary_text"])
    for x in rows:
        writer.writerow([x.id, x.keyword, x.window_start.isoformat() if x.window_start else "", x.window_end.isoformat() if x.window_end else "", x.fused_score, x.summary_text or ""])
    return Response(output.getvalue(), mimetype="text/csv; charset=utf-8", headers={"Content-Disposition": "attachment; filename=fused_data.csv"})
