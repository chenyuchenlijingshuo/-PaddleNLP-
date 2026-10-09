import logging
from collections import Counter

from extensions import db
from models import RawData, SentimentResult
from services.paddlenlp_service import analyze_sentiment

logger = logging.getLogger(__name__)


def run_sentiment_batch(limit=200, only_missing=True):
    limit = min(max(int(limit or 200), 1), 1000)

    q = RawData.query.order_by(RawData.created_at.desc())
    rows = q.limit(limit).all()
    if not rows:
        return {"success": True, "available": False, "processed": 0, "upserted": 0, "message": "no raw data"}

    if only_missing:
        existing = {
            x.raw_id
            for x in SentimentResult.query.filter(SentimentResult.raw_id.in_([r.id for r in rows])).all()
        }
        rows = [r for r in rows if r.id not in existing]

    texts = [f"{r.title or ''} {r.content or ''}".strip() for r in rows]
    payload = analyze_sentiment(texts)
    if not payload.get("available"):
        return {
            "success": False,
            "available": False,
            "processed": len(texts),
            "upserted": 0,
            "message": payload.get("message") or "sentiment unavailable",
        }

    items = payload.get("items") or []
    upserted = 0
    label_counter = Counter()
    for row, item in zip(rows, items):
        label = (item.get("label") or "unknown").strip() or "unknown"
        score = item.get("score")
        label_counter[label] += 1
        existing_row = SentimentResult.query.filter_by(raw_id=row.id).first()
        if existing_row:
            existing_row.label = label
            existing_row.score = float(score) if score is not None else None
        else:
            db.session.add(
                SentimentResult(
                    raw_id=row.id,
                    label=label,
                    score=float(score) if score is not None else None,
                )
            )
        upserted += 1

    db.session.commit()
    logger.info("sentiment batch done: processed=%s upserted=%s", len(texts), upserted)
    return {
        "success": True,
        "available": True,
        "processed": len(texts),
        "upserted": upserted,
        "labels": [{"label": k, "count": v} for k, v in label_counter.most_common()],
        "message": "ok",
    }

