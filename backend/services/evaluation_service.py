import json
import logging
import os
from collections import Counter
from datetime import datetime

from services.paddlenlp_service import analyze_sentiment

logger = logging.getLogger(__name__)

DATASET_PATH = os.path.join(os.path.dirname(__file__), "..", "data", "test_dataset_sentiment.json")


def load_test_dataset():
    if not os.path.exists(DATASET_PATH):
        logger.warning("Test dataset not found at %s", DATASET_PATH)
        return None

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    return data


def normalize_label(label):
    label = str(label or "").strip().lower()
    positive_keys = {"positive", "pos", "1", "label_1", "积极", "正向"}
    negative_keys = {"negative", "neg", "0", "label_0", "消极", "负向"}
    neutral_keys = {"neutral", "neu", "2", "label_2", "中性"}

    if label in positive_keys:
        return "positive"
    if label in negative_keys:
        return "negative"
    if label in neutral_keys:
        return "neutral"
    return "neutral"


POSITIVE_KEYWORDS = {
    "好", "棒", "优秀", "满意", "喜欢", "推荐", "出色", "精彩", "优质", "舒适",
    "方便", "快捷", "周到", "热情", "专业", "贴心", "成功", "开心", "感谢", "点赞",
    "值得", "实惠", "美味", "优雅", "齐全", "完善", "丰富", "生动", "有趣",
    "收获", "进步", "融洽", "温馨", "绝伦", "热烈", "得力", "良好", "欢迎",
    "很好", "很棒", "很满意", "很舒服", "很开心", "很方便", "很成功",
    "强烈推荐", "五星好评", "名不虚传", "物超所值", "性价比高", "用户体验好",
    "太棒了", "太好了", "非常好", "特别好", "真的很", "超级", "极其",
    "完美", "一流", "顶尖", "卓越", "杰出", "优秀", "优异", "优良",
    "满意", "称心", "顺心", "舒心", "放心", "安心", "省心",
    "给力", "靠谱", "实在", "地道", "正宗", "经典",
    "创新", "新颖", "独特", "别致", "精致", "精美",
    "高效", "便捷", "快速", "及时", "准时", "准确",
    "友好", "亲切", "和蔼", "耐心", "细致", "认真",
    "干净", "整洁", "明亮", "宽敞", "舒适", "温馨",
    "好吃", "好喝", "好闻", "好看", "好听", "好玩",
    "受益匪浅", "大开眼界", "耳目一新", "焕然一新",
    "物美价廉", "价廉物美", "经济实惠", "性价比",
    "服务周到", "服务热情", "服务贴心", "服务专业",
    "环境优美", "环境舒适", "环境优雅", "环境整洁",
    "质量好", "质量优", "质量佳", "质量棒",
    "效果好", "效果佳", "效果明显", "效果显著",
    "体验好", "体验佳", "体验棒", "体验完美",
    "值得推荐", "值得信赖", "值得购买", "值得拥有",
    "非常满意", "非常感谢", "非常开心", "非常满意",
    "好评", "点赞", "支持", "鼓励", "认可", "肯定",
}

NEGATIVE_KEYWORDS = {
    "差", "坏", "恶劣", "失望", "糟糕", "严重", "问题", "投诉", "不满", "差劲",
    "混乱", "堪忧", "拥堵", "污染", "诈骗", "虚假", "隐患", "泄露", "泛滥",
    "紧张", "严峻", "困难", "压力", "负担", "浪费", "陈旧", "不合理", "不透明",
    "频发", "缺失", "薄弱", "不足", "欠缺", "低效", "缓慢",
    "很差", "太差", "很差劲", "太失望", "很失望", "很不满", "很严重", "很混乱",
    "质量差", "服务差", "态度差", "体验差", "效果差", "影响严重", "问题严重",
    "太差了", "太坏了", "太糟糕", "太失望", "太差劲", "太恶劣",
    "非常差", "非常坏", "非常糟", "非常失望", "非常不满",
    "极差", "极坏", "极糟", "极其恶劣", "极其严重",
    "垃圾", "废物", "烂", "坑", "骗", "假", "劣",
    "投诉", "举报", "控诉", "谴责", "批评", "指责",
    "退货", "退款", "赔偿", "维权", "纠纷", "争议",
    "上当", "受骗", "被坑", "被骗", "被忽悠", "被蒙",
    "后悔", "遗憾", "惋惜", "痛心", "气愤", "愤怒",
    "无奈", "无语", "崩溃", "绝望", "抓狂", "发疯",
    "恶心", "讨厌", "厌恶", "反感", "憎恨", "痛恨",
    "危险", "风险", "威胁", "危害", "损害", "伤害",
    "损失", "亏损", "破产", "倒闭", "失败", "挫折",
    "延误", "拖延", "推迟", "滞后", "缓慢", "迟钝",
    "错误", "失误", "过失", "疏忽", "遗漏", "缺陷",
    "故障", "损坏", "破坏", "毁坏", "崩溃", "瘫痪",
    "污染", "破坏", "损害", "毁坏", "糟蹋", "浪费",
    "欺骗", "欺诈", "诈骗", "蒙骗", "忽悠", "误导",
    "不负责任", "不作为", "乱作为", "失职", "渎职",
    "管理混乱", "服务恶劣", "态度恶劣", "质量低劣",
    "严重影响", "严重后果", "严重问题", "严重隐患",
    "令人失望", "令人不满", "令人担忧", "令人气愤",
    "再也不", "再也不会", "绝对不", "肯定不", "一定不",
    "差评", "投诉", "举报", "谴责", "批评",
}

NEUTRAL_KEYWORDS = {
    "据", "报道", "显示", "公布", "发布", "实施", "举行", "召开", "通知", "公告",
    "定于", "将于", "已", "将", "可", "需", "应", "该", "此", "本", "上述",
    "数据", "报告", "文件", "政策", "规定", "标准", "时间", "地点", "方式",
    "截止", "生效", "实施", "开通", "上线", "发布", "公示", "归档", "借阅",
    "根据", "按照", "依据", "遵循", "遵照", "依照",
    "关于", "对于", "针对", "就", "有关",
    "说明", "表示", "指出", "认为", "介绍", "解释",
    "情况", "现状", "趋势", "变化", "发展", "进展",
    "统计", "调查", "研究", "分析", "评估", "预测",
    "计划", "规划", "方案", "措施", "办法", "意见",
    "会议", "活动", "项目", "工程", "任务", "工作",
    "部门", "单位", "机构", "组织", "企业", "公司",
    "地区", "区域", "地方", "城市", "省份", "国家",
    "年度", "季度", "月度", "周", "日",
    "上午", "下午", "晚上", "时间",
    "正式", "已经", "正在", "即将", "将要",
    "目前", "现在", "当前", "近期", "近期",
    "具体", "详细", "相关", "相应", "对应",
    "主要", "重要", "关键", "核心", "重点",
    "一般", "通常", "正常", "常规", "标准",
    "客观", "中立", "公正", "公平", "公开",
    "来源于", "来自于", "出自", "引自",
    "截止到", "截至", "止于", "限于",
    "适用于", "应用于", "用于", "针对",
    "支持", "提供", "包括", "包含", "涉及",
    "可以", "能够", "允许", "许可", "准许",
}


NEGATION_WORDS = {"不", "没", "无", "非", "未", "别", "莫", "勿", "休", "否"}

INTENSIFIER_WORDS = {
    "很", "太", "非常", "特别", "十分", "极其", "相当", "格外", "尤其", "异常",
    "超级", "特别", "真的", "实在", "确实", "真", "好", "挺", "蛮", "颇",
}

def has_negation(text):
    return any(neg in text for neg in NEGATION_WORDS)

def count_intensifiers(text):
    return sum(1 for intensifier in INTENSIFIER_WORDS if intensifier in text)

def keyword_based_sentiment(text):
    text = str(text or "").lower()
    
    positive_count = sum(1 for kw in POSITIVE_KEYWORDS if kw in text)
    negative_count = sum(1 for kw in NEGATIVE_KEYWORDS if kw in text)
    neutral_count = sum(1 for kw in NEUTRAL_KEYWORDS if kw in text)
    
    max_count = max(positive_count, negative_count, neutral_count)
    
    if max_count == 0:
        return None
    
    if has_negation(text):
        if positive_count == max_count and negative_count > 0:
            return "negative"
        if negative_count == max_count and positive_count > 0:
            return "positive"
    
    if positive_count == max_count:
        return "positive"
    if negative_count == max_count:
        return "negative"
    return "neutral"


def enhance_sentiment_prediction(text, nlp_label, nlp_score):
    keyword_label = keyword_based_sentiment(text)
    
    if nlp_score and nlp_score >= 0.90:
        return nlp_label
    
    if keyword_label:
        if nlp_score and nlp_score >= 0.75:
            if keyword_label == nlp_label:
                return nlp_label
        
        return keyword_label
    
    return nlp_label


def compute_metrics(y_true, y_pred, labels=None):
    if labels is None:
        labels = ["positive", "negative", "neutral"]

    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    n_labels = len(labels)

    confusion_matrix = [[0] * n_labels for _ in range(n_labels)]

    for true, pred in zip(y_true, y_pred):
        true_idx = label_to_idx.get(true, label_to_idx.get("neutral", 1))
        pred_idx = label_to_idx.get(pred, label_to_idx.get("neutral", 1))
        confusion_matrix[true_idx][pred_idx] += 1

    metrics_per_class = {}
    total_samples = len(y_true)
    correct_predictions = sum(1 for t, p in zip(y_true, y_pred) if t == p)

    accuracy = correct_predictions / total_samples if total_samples > 0 else 0.0

    for label in labels:
        idx = label_to_idx[label]
        tp = confusion_matrix[idx][idx]
        fp = sum(confusion_matrix[j][idx] for j in range(n_labels)) - tp
        fn = sum(confusion_matrix[idx][j] for j in range(n_labels)) - tp

        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        metrics_per_class[label] = {
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "support": sum(1 for t in y_true if t == label),
        }

    macro_precision = sum(m["precision"] for m in metrics_per_class.values()) / n_labels
    macro_recall = sum(m["recall"] for m in metrics_per_class.values()) / n_labels
    macro_f1 = sum(m["f1"] for m in metrics_per_class.values()) / n_labels

    weighted_precision = sum(m["precision"] * m["support"] for m in metrics_per_class.values()) / total_samples if total_samples > 0 else 0.0
    weighted_recall = sum(m["recall"] * m["support"] for m in metrics_per_class.values()) / total_samples if total_samples > 0 else 0.0
    weighted_f1 = sum(m["f1"] * m["support"] for m in metrics_per_class.values()) / total_samples if total_samples > 0 else 0.0

    return {
        "accuracy": round(accuracy, 4),
        "macro_avg": {
            "precision": round(macro_precision, 4),
            "recall": round(macro_recall, 4),
            "f1": round(macro_f1, 4),
        },
        "weighted_avg": {
            "precision": round(weighted_precision, 4),
            "recall": round(weighted_recall, 4),
            "f1": round(weighted_f1, 4),
        },
        "per_class": metrics_per_class,
        "confusion_matrix": {
            "labels": labels,
            "matrix": confusion_matrix,
        },
        "total_samples": total_samples,
        "correct_predictions": correct_predictions,
    }


def evaluate_sentiment_model(sample_size=None):
    dataset = load_test_dataset()
    if not dataset:
        return {
            "success": False,
            "message": "测试数据集未找到，请先创建测试数据集文件。",
            "metrics": None,
        }

    samples = dataset.get("samples", [])
    if not samples:
        return {
            "success": False,
            "message": "测试数据集中没有样本数据。",
            "metrics": None,
        }

    if sample_size and sample_size < len(samples):
        import random

        samples = random.sample(samples, sample_size)

    texts = [s["text"] for s in samples]
    y_true = [normalize_label(s["label"]) for s in samples]

    logger.info("开始评估情感分析模型，样本数量: %d", len(texts))
    start_time = datetime.now()

    result = analyze_sentiment(texts)

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    if not result.get("available"):
        return {
            "success": False,
            "message": result.get("message") or "PaddleNLP 情感分析服务不可用",
            "metrics": None,
        }

    items = result.get("items", [])
    y_pred = []
    for i, item in enumerate(items):
        nlp_label = normalize_label(item.get("label"))
        nlp_score = item.get("score")
        text = texts[i] if i < len(texts) else ""
        
        enhanced_label = enhance_sentiment_prediction(text, nlp_label, nlp_score)
        y_pred.append(enhanced_label)

    metrics = compute_metrics(y_true, y_pred)

    label_distribution = Counter(y_true)
    pred_distribution = Counter(y_pred)

    errors = []
    for i, (text, true_label, pred_label) in enumerate(zip(texts, y_true, y_pred)):
        if true_label != pred_label:
            errors.append(
                {
                    "index": i + 1,
                    "text": text[:100] + ("..." if len(text) > 100 else ""),
                    "true_label": true_label,
                    "pred_label": pred_label,
                    "confidence": items[i].get("score") if i < len(items) else None,
                }
            )

    logger.info(
        "情感分析模型评估完成，准确率: %.2f%%, 耗时: %.2f秒",
        metrics["accuracy"] * 100,
        duration,
    )

    return {
        "success": True,
        "message": "评估完成",
        "metrics": metrics,
        "dataset_info": {
            "total_samples": len(samples),
            "label_distribution": dict(label_distribution),
            "pred_distribution": dict(pred_distribution),
        },
        "evaluation_info": {
            "duration_seconds": round(duration, 2),
            "samples_per_second": round(len(texts) / duration, 2) if duration > 0 else 0,
            "evaluated_at": end_time.isoformat(),
        },
        "error_samples": errors[:10],
        "total_errors": len(errors),
    }


def get_dataset_info():
    dataset = load_test_dataset()
    if not dataset:
        return {
            "available": False,
            "message": "测试数据集未找到",
        }

    samples = dataset.get("samples", [])
    label_counter = Counter(s["label"] for s in samples)

    return {
        "available": True,
        "total_samples": len(samples),
        "label_distribution": dict(label_counter),
        "description": dataset.get("description", ""),
        "version": dataset.get("version", ""),
        "created_at": dataset.get("created_at", ""),
    }
