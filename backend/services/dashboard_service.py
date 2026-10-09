import json
from collections import Counter, defaultdict
from datetime import datetime, timedelta

from extensions import db
from models import AlertLog, AlertRule, CollectRule, FusedData, RawData, SentimentResult
from services.analyze_service import compute_tfidf_keywords


def _parse_source_counts(payload):
    if not payload:
        return {}
    try:
        return json.loads(payload)
    except Exception:
        return {}


def build_dashboard_snapshot():
    now = datetime.utcnow()
    last_24h = now - timedelta(hours=24)

    raw_total = RawData.query.count()
    fused_total = FusedData.query.count()
    rules_total = CollectRule.query.count()
    alerts_total = AlertRule.query.count()
    raw_last_24h = RawData.query.filter(RawData.created_at >= last_24h).count()
    alerts_last_24h = AlertLog.query.filter(AlertLog.triggered_at >= last_24h).count()

    latest_raw = RawData.query.order_by(RawData.created_at.desc()).limit(120).all()
    latest_fused = FusedData.query.order_by(FusedData.window_start.desc()).limit(300).all()
    latest_alerts = AlertLog.query.order_by(AlertLog.triggered_at.desc()).limit(6).all()

    docs = [f"{row.title or ''} {row.content or ''}" for row in latest_raw]
    hot_keywords = [
        {
            "keyword": row.keyword,
            "score": round(float(row.fused_score or 0), 4),
            "window_start": row.window_start.isoformat() if row.window_start else None,
        }
        for row in sorted(latest_fused, key=lambda item: float(item.fused_score or 0), reverse=True)[:8]
    ]

    source_counter = Counter((row.source_type or "unknown") for row in latest_raw)
    source_distribution = [{"name": key, "value": value} for key, value in source_counter.items()]

    warnings = [
        {
            "id": row.id,
            "level": row.level,
            "message": row.message,
            "triggered_at": row.triggered_at.isoformat() if row.triggered_at else None,
        }
        for row in latest_alerts
    ]

    return {
        "cards": [
            {"label": "原始数据", "value": raw_total, "delta": raw_last_24h, "unit": "条", "tone": "primary"},
            {"label": "融合主题", "value": fused_total, "delta": len(latest_fused), "unit": "项", "tone": "success"},
            {"label": "采集规则", "value": rules_total, "delta": None, "unit": "条", "tone": "info"},
            {"label": "24h 预警", "value": alerts_last_24h, "delta": alerts_total, "unit": "次", "tone": "danger"},
        ],
        "hot_keywords": hot_keywords,
        "warnings": warnings,
        "keyword_brief": compute_tfidf_keywords(docs, top_k=12),
        "source_distribution": source_distribution,
        "quick_entries": [
            {"key": "collect", "title": "执行采集", "desc": "创建规则并抓取最新原始数据。"},
            {"key": "process", "title": "运行融合", "desc": "清洗文本并生成主题热度结果。"},
            {"key": "analyze", "title": "进入分析", "desc": "查看词云、趋势、来源和 NLP 结果。"},
            {"key": "alert", "title": "检查预警", "desc": "快速查看高等级预警日志与规则。"},
        ],
    }


def build_visualization_payload(hours=72, keyword=None, source_type=None, top_k=20, page=1, size=20):
    end = datetime.utcnow()
    start = end - timedelta(hours=hours)

    raw_query = RawData.query.filter(RawData.created_at >= start)
    if source_type:
        raw_query = raw_query.filter(RawData.source_type == source_type)
    # 用于统计/词云的采样集合（避免全量过大）
    raw_rows = raw_query.order_by(RawData.created_at.desc()).limit(300).all()
    raw_total = raw_query.count()
    page = max(int(page or 1), 1)
    size = min(max(int(size or 20), 1), 200)
    raw_page = raw_query.order_by(RawData.created_at.desc()).paginate(page=page, per_page=size, error_out=False)

    fused_query = FusedData.query.filter(FusedData.window_start >= start)
    if keyword:
        fused_query = fused_query.filter(FusedData.keyword.contains(keyword))
    fused_rows = fused_query.order_by(FusedData.window_start.asc()).limit(1000).all()

    docs = [f"{row.title or ''} {row.content or ''}" for row in raw_rows]
    wordcloud = [
        {"name": item["term"], "value": max(int(item["score"] * 100), 1)}
        for item in compute_tfidf_keywords(docs, top_k=top_k)
    ]

    hot_counter = defaultdict(float)
    trend_counter = defaultdict(float)
    for row in fused_rows:
        hot_counter[row.keyword] += float(row.fused_score or 0)
        time_key = row.window_start.strftime("%m-%d %H:00") if row.window_start else "unknown"
        trend_counter[time_key] += float(row.fused_score or 0)

    ranking = [
        {"keyword": key, "score": round(value, 4)}
        for key, value in sorted(hot_counter.items(), key=lambda item: item[1], reverse=True)[:top_k]
    ]
    trend = [{"time": key, "score": round(value, 4)} for key, value in sorted(trend_counter.items(), key=lambda item: item[0])]

    source_counter = Counter((row.source_type or "unknown") for row in raw_rows)
    source_distribution = [{"name": key, "value": value} for key, value in source_counter.items()]

    page_ids = [row.id for row in raw_page.items]
    sentiment_map = {}
    if page_ids:
        for s in SentimentResult.query.filter(SentimentResult.raw_id.in_(page_ids)).all():
            sentiment_map[s.raw_id] = {"label": s.label, "score": s.score}

    drilldown = []
    for row in raw_page.items:
        senti = sentiment_map.get(row.id) or {"label": None, "score": None}
        drilldown.append(
            {
                "id": row.id,
                "title": row.title,
                "source_type": row.source_type,
                "published_at": row.published_at.isoformat() if row.published_at else None,
                "keyword_hit": row.keyword_hit,
                "content_preview": (row.content or "")[:120],
                "sentiment_label": senti.get("label"),
                "sentiment_score": senti.get("score"),
            }
        )

    # 情感分布（基于当前筛选窗口内已计算情感的记录）
    sentiment_dist = []
    try:
        agg = (
            db.session.query(SentimentResult.label, db.func.count(SentimentResult.id))
            .join(RawData, RawData.id == SentimentResult.raw_id)
            .filter(RawData.created_at >= start)
        )
        if source_type:
            agg = agg.filter(RawData.source_type == source_type)
        sentiment_dist = [{"name": label or "unknown", "value": int(cnt)} for label, cnt in agg.group_by(SentimentResult.label).all()]
    except Exception:
        sentiment_dist = []

    fused_source_counter = Counter()
    for row in fused_rows:
        counts = _parse_source_counts(row.source_counts_json)
        for key, value in counts.items():
            fused_source_counter[key] += int(value or 0)

    return {
        "filters": {"hours": hours, "keyword": keyword or "", "source_type": source_type or "", "top_k": top_k},
        "wordcloud": wordcloud,
        "ranking": ranking,
        "trend": trend,
        "source_distribution": source_distribution,
        "fused_source_distribution": [{"name": key, "value": value} for key, value in fused_source_counter.items()],
        "records": drilldown,
        "records_total": raw_total,
        "records_page": page,
        "records_size": size,
        "sentiment_distribution": sentiment_dist,
    }
