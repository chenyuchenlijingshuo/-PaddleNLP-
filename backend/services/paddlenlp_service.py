import logging
import os
from functools import lru_cache


LOGGER = logging.getLogger(__name__)
LIGHT_MODE = os.getenv("PADDLENLP_LIGHT_MODE", "0").strip() in {"1", "true", "True"}
CLASSIFY_FALLBACK_ENABLED = os.getenv("PADDLENLP_CLASSIFY_FALLBACK", "1").strip() not in {"0", "false", "False"}


def _safe_texts(texts):
    return [str(item or "").strip() for item in texts if str(item or "").strip()]


@lru_cache(maxsize=1)
def _taskflow_factory():
    try:
        from paddlenlp import Taskflow
    except Exception as exc:  # pragma: no cover - depends on runtime install
        LOGGER.warning("PaddleNLP import failed: %s", exc)
        return {"available": False, "reason": str(exc), "sentiment": None, "classifier": None}

    sentiment = None
    classifier = None
    errors = []

    if not LIGHT_MODE:
        try:
            sentiment = Taskflow("sentiment_analysis")
        except Exception as exc:  # pragma: no cover - depends on runtime install
            errors.append(f"sentiment_analysis init failed: {exc}")
            LOGGER.warning("PaddleNLP sentiment task init failed: %s", exc)
    else:
        LOGGER.info("PaddleNLP light mode enabled, skip heavy sentiment task init")

    try:
        classifier = Taskflow("text_classification")
    except Exception as exc:  # pragma: no cover - depends on runtime install
        errors.append(f"text_classification init failed: {exc}")
        LOGGER.warning("PaddleNLP classification task init failed: %s", exc)

    return {
        "available": bool(sentiment or classifier),
        "reason": "; ".join(errors),
        "sentiment": sentiment,
        "classifier": classifier,
    }


def paddlenlp_status():
    factory = _taskflow_factory()
    sentiment_ready = factory["sentiment"] is not None or (LIGHT_MODE and factory["classifier"] is not None)
    classification_ready = factory["classifier"] is not None or CLASSIFY_FALLBACK_ENABLED
    reason = ""
    if not factory["available"]:
        reason = "PaddleNLP 环境未就绪，请检查依赖安装。"
    elif factory["classifier"] is None and CLASSIFY_FALLBACK_ENABLED:
        reason = "文本分类模型暂不可用，已启用系统内置兜底分类策略。"
    elif factory["reason"]:
        reason = "模型部分能力未就绪，但不影响当前情感分析流程。"
    return {
        "available": factory["available"],
        "reason": reason,
        "sentiment_ready": sentiment_ready,
        "classification_ready": classification_ready,
    }


def _normalize_sentiment_item(item):
    if not isinstance(item, dict):
        return {"label": "unknown", "score": None}
    return {
        "label": item.get("label") or item.get("sentiment") or "unknown",
        "score": item.get("score"),
        "positive_probs": item.get("positive_probs"),
        "negative_probs": item.get("negative_probs"),
    }


def _normalize_sentiment_from_classifier(item):
    label = str(item.get("label") or "unknown").strip().lower()
    score = item.get("score")
    positive_keys = {"positive", "pos", "1", "label_1", "积极", "正向"}
    negative_keys = {"negative", "neg", "0", "label_0", "消极", "负向"}
    if label in positive_keys:
        mapped = "positive"
    elif label in negative_keys:
        mapped = "negative"
    else:
        mapped = "neutral"
    return {
        "label": mapped,
        "score": score,
        "positive_probs": score if mapped == "positive" else None,
        "negative_probs": score if mapped == "negative" else None,
    }


def analyze_sentiment(texts):
    factory = _taskflow_factory()
    cleaned = _safe_texts(texts)
    if not cleaned:
        return {"available": factory["available"], "items": [], "message": "no valid texts"}
    if factory["sentiment"]:
        result = factory["sentiment"](cleaned)
        items = []
        for text, raw in zip(cleaned, result):
            items.append({"text": text, **_normalize_sentiment_item(raw)})
        return {"available": True, "items": items, "message": "ok"}

    # 轻量模式下用文本分类任务兜底，避免加载超大 sentiment 模型导致内存错误
    if factory["classifier"]:
        result = factory["classifier"](cleaned)
        cls_items = [_normalize_classification_item(text, raw) for text, raw in zip(cleaned, result)]
        items = [{"text": x["text"], **_normalize_sentiment_from_classifier(x)} for x in cls_items]
        return {"available": True, "items": items, "message": "ok (light-mode classifier fallback)"}

    return {"available": False, "items": [], "message": factory["reason"] or "sentiment task unavailable"}


def _normalize_classification_item(text, raw):
    if isinstance(raw, dict):
        label = raw.get("label") or raw.get("predictions") or raw.get("text_label") or "unknown"
        score = raw.get("score")
        return {"text": text, "label": label, "score": score, "raw": raw}
    if isinstance(raw, list) and raw:
        first = raw[0]
        if isinstance(first, dict):
            return {
                "text": text,
                "label": first.get("label") or first.get("class_name") or "unknown",
                "score": first.get("score"),
                "raw": raw,
            }
    return {"text": text, "label": "unknown", "score": None, "raw": raw}


def _fallback_classification_item(text):
    t = (text or "").lower()
    if any(x in t for x in ["谣言", "危机", "负面", "投诉", "事故", "风险", "冲突"]):
        return {"text": text, "label": "风险舆情", "score": 0.72, "raw": {"source": "fallback"}}
    if any(x in t for x in ["政策", "发布", "通报", "官方", "公告", "回应"]):
        return {"text": text, "label": "官方信息", "score": 0.68, "raw": {"source": "fallback"}}
    if any(x in t for x in ["活动", "品牌", "新品", "宣传", "合作", "代言"]):
        return {"text": text, "label": "传播营销", "score": 0.66, "raw": {"source": "fallback"}}
    return {"text": text, "label": "一般舆情", "score": 0.6, "raw": {"source": "fallback"}}


def classify_texts(texts):
    factory = _taskflow_factory()
    cleaned = _safe_texts(texts)
    if not cleaned:
        return {"available": factory["available"], "items": [], "message": "no valid texts"}
    if factory["classifier"]:
        result = factory["classifier"](cleaned)
        items = [_normalize_classification_item(text, raw) for text, raw in zip(cleaned, result)]
        return {"available": True, "items": items, "message": "ok"}

    if CLASSIFY_FALLBACK_ENABLED:
        items = [_fallback_classification_item(text) for text in cleaned]
        return {"available": True, "items": items, "message": "ok (fallback)"}

    return {"available": False, "items": [], "message": "classification task unavailable"}
