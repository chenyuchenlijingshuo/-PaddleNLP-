"""
舆情分析系统 - 数据分析路由
============================

该模块负责数据分析相关的API接口，包括：
1. TF-IDF关键词提取
2. 热点排行榜
3. 时间趋势分析
4. 来源分布统计
5. 情感分析（PaddleNLP）
6. 文本分类（PaddleNLP）
7. 模型性能评估

技术实现：
- TF-IDF算法：词频-逆文档频率
- 热度计算：基于融合分值聚合
- 情感分析：PaddleNLP Taskflow API
- 文本分类：PaddleNLP Taskflow API

API接口：
- GET /api/analyze/tfidf: TF-IDF关键词提取
- GET /api/analyze/hot: 热点排行榜
- GET /api/analyze/trend: 时间趋势分析
- GET /api/analyze/source: 来源分布统计
- GET /api/analyze/visualization: 可视化数据
- POST /api/analyze/sentiment: 情感分析
- POST /api/analyze/classify: 文本分类
- GET /api/analyze/nlp-status: NLP状态
- POST /api/analyze/evaluation: 模型性能评估
"""

from datetime import datetime, timedelta

from flask import Blueprint, request

from decorators import jwt_required_custom
from models import FusedData, RawData
from services.analyze_service import compute_hot_top, compute_tfidf_keywords, compute_trend
from services.dashboard_service import build_visualization_payload
from services.evaluation_service import evaluate_sentiment_model, get_dataset_info
from services.paddlenlp_service import analyze_sentiment, classify_texts, paddlenlp_status
from utils.response import ok

analyze_bp = Blueprint("analyze", __name__)


@analyze_bp.get("/tfidf")
@jwt_required_custom
def tfidf_keywords():
    limit = min(max(int(request.args.get("limit", 200)), 1), 2000)
    top_k = min(max(int(request.args.get("top_k", 20)), 1), 200)
    rows = RawData.query.order_by(RawData.id.desc()).limit(limit).all()
    docs = [(r.title or "") + " " + (r.content or "") for r in rows]
    return ok(compute_tfidf_keywords(docs, top_k=top_k))


@analyze_bp.get("/hot")
@jwt_required_custom
def hot_top():
    rows = FusedData.query.order_by(FusedData.window_start.desc()).limit(1000).all()
    return ok(compute_hot_top(rows, top_n=min(max(int(request.args.get("top_n", 20)), 1), 200)))


@analyze_bp.get("/trend")
@jwt_required_custom
def trend():
    keyword = (request.args.get("keyword") or "").strip()
    start = datetime.utcnow() - timedelta(hours=min(max(int(request.args.get("hours", 24)), 1), 24 * 30))
    rows = FusedData.query.filter(FusedData.window_start >= start).order_by(FusedData.window_start.asc()).all()
    return ok(compute_trend(rows, keyword=keyword or None))


@analyze_bp.get("/visualization")
@jwt_required_custom
def visualization():
    hours = min(max(int(request.args.get("hours", 72)), 1), 24 * 30)
    top_k = min(max(int(request.args.get("top_k", 20)), 5), 50)
    keyword = (request.args.get("keyword") or "").strip() or None
    source_type = (request.args.get("source_type") or "").strip() or None
    page = max(int(request.args.get("page", 1)), 1)
    size = min(max(int(request.args.get("size", 20)), 1), 200)
    return ok(build_visualization_payload(hours=hours, keyword=keyword, source_type=source_type, top_k=top_k, page=page, size=size))


@analyze_bp.get("/nlp/status")
@jwt_required_custom
def nlp_status():
    return ok(paddlenlp_status())


@analyze_bp.post("/nlp/sentiment")
@jwt_required_custom
def nlp_sentiment():
    data = request.get_json(silent=True) or {}
    return ok(analyze_sentiment(data.get("texts") or []))


@analyze_bp.post("/nlp/classify")
@jwt_required_custom
def nlp_classify():
    data = request.get_json(silent=True) or {}
    return ok(classify_texts(data.get("texts") or []))


@analyze_bp.get("/nlp/evaluate")
@jwt_required_custom
def nlp_evaluate():
    sample_size = request.args.get("sample_size", type=int)
    return ok(evaluate_sentiment_model(sample_size=sample_size))


@analyze_bp.get("/nlp/dataset/info")
@jwt_required_custom
def nlp_dataset_info():
    return ok(get_dataset_info())
