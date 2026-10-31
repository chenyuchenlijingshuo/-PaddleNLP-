"""
微博平台下消费数码新品首发的舆情洞察与策略分析 —— 预警服务
=============================================================
预警主流程：
    DataLoader 加载 DB → Pandas 合成 DataFrame → 按规则 dispatch
        ├─ threshold        阈值（热度值）
        ├─ sensitive        敏感词（regex 匹配）
        ├─ anomaly          异常检测（NumPy z-score）
        └─ launch_campaign  首发专项（pre / launch_day / post）
            → 写 AlertLog → Matplotlib 生成 chart → commit
"""

from __future__ import annotations   

import json          
import logging       
import re            
from datetime import datetime, timedelta  
from pathlib import Path                   


from extensions import db
from models import AlertLog, AlertRule, FusedData, RawData, SentimentResult
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

logger = logging.getLogger(__name__)


try:
    import numpy as np       
    _HAS_NUMPY = True        
except ImportError:           
    np = None               
    _HAS_NUMPY = False      
    logger.warning("numpy 未安装，异常检测模式不可用")

try:
    import pandas as pd     
    _HAS_PANDAS = True       
except ImportError:          
    pd = None              
    _HAS_PANDAS = False    
    logger.warning("pandas 未安装，预警服务降级运行")

try:
    import matplotlib        
    matplotlib.use("Agg")   
    import matplotlib.pyplot as plt
    matplotlib.rcParams["axes.unicode_minus"] = False   # 负号正常显示
    
    for _f in ["SimHei", "Microsoft YaHei", "Arial Unicode MS", "DejaVu Sans"]:
        try:
            matplotlib.rcParams["font.sans-serif"] = [_f]
            break
        except Exception:
            continue
    _HAS_MPL = True         
except ImportError as ex:     
    plt = None               
    _HAS_MPL = False        
    logger.warning("matplotlib 未安装，不生成预警图表: %s", ex)


try:
    from bs4 import BeautifulSoup as BS  
    _HAS_BS4 = True                      
except ImportError:                         
    BS = None                              
    _HAS_BS4 = False                       
    logger.warning("bs4 未安装，文本不会做 HTML 清洗")


# —— 输出目录 ——
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_ALERT_CHART_DIR = _PROJECT_ROOT / "data" / "alerts"
_ALERT_CHART_DIR.mkdir(parents=True, exist_ok=True)


def clean_html(text: str) -> str:
    """ BeautifulSoup：剥离 HTML 标签，失败时用正则兜底。"""
    if not text:
        return ""
    if _HAS_BS4:
        try:
            soup = BS(text, "lxml")
            return soup.get_text(separator=" ")   
        except Exception:   
            pass
    return re.sub(r"<[^>]+>", " ", str(text))      


def split_words(words: str) -> list[str]:   
    """按逗号分割，中文逗号一并处理。"""
    if not words:
        return []                 
    raw = words.replace("，", ",").split(",")  
    return [w.strip() for w in raw if w.strip()]  


def build_regex(patterns: list[str]) -> re.Pattern | None:  
    """
    把敏感词列表编译成一个正则。
    逐个 try 编译，非法 pattern 用字面量兜底。
    list comprehension
    优先级
    """
    if not patterns:                    
        return None
    escaped = []
    for p in patterns:                  
        try:
            re.compile(p)              
            escaped.append(p)          
        except re.error:                
            escaped.append(re.escape(p))  
    if not escaped:
        return None
    try:
        return re.compile("|".join(f"(?:{x})" for x in escaped))   
    except re.error as ex:
        logger.warning("正则编译失败 %s，降级为字面量 in 匹配: %s", escaped, ex)
        return None


def build_milestone_regexes() -> dict[str, re.Pattern]:   
    """iPhone Duo 首发场景下，预编译几类重点关键词。"""
    bucket = {
        "黄牛": re.compile(r"黄牛|代购|溢价|加价|炒到|期货"),
        "价格": re.compile(r"\d{4,6}\s*[¥￥]|[¥￥]\s*\d{4,6}|贵|便宜|降价|涨价"),
        "BUG":  re.compile(r"bug|闪退|崩溃|死机|重启|掉帧|卡顿"),
        "硬件": re.compile(r"发热|续航|信号|屏幕|漏液|进灰|缝隙|掉漆"),
        "差评": re.compile(r"差评|翻车|割韭菜|智商税|后悔|不值|失望"),
        "正面": re.compile(r"真香|必入|香爆|推荐|值得|首发抢到"),
    }
    return {k: v for k, v in bucket.items()}   


def level_by_threshold(value: float, lv1: float | None, lv2: float | None) -> int:   
    """FlowControl：2=重度, 1=轻度, 0=不触发。"""
    try:
        v = float(value)    
    except (TypeError, ValueError):   
        return 0
    lv2 = float(lv2) if lv2 else None
    lv1 = float(lv1) if lv1 else None
    if lv2 is not None and v >= lv2:  
        return 2
    if lv1 is not None and v >= lv1:
        return 1
    return 0



def _load_raw_df()-> "pd.DataFrame | None": 
    """RawData + SentimentResult 合并成 DataFrame。"""
    if not _HAS_PANDAS:
        return None
    rows = db.session.query(RawData, SentimentResult).outerjoin(
        SentimentResult, SentimentResult.raw_id == RawData.id
    ).all()
    records = []
    for r, s in rows:
        clean = clean_html((r.title or "") + " " + (r.content or ""))  
        records.append({
            "id": r.id,
            "rule_id": r.rule_id,
            "title": r.title or "",
            "content": r.content or "",
            "text": clean,
            "keyword_hit": r.keyword_hit or "",
            "source_type": r.source_type or "",
            "published_at": r.published_at or r.created_at,
            "created_at": r.created_at,
            "sentiment_label": (s.label if s else None) or "unknown",
            "sentiment_score": (s.score if s else None),
        })
    if not records:
        return pd.DataFrame(columns=[
            "id", "rule_id", "title", "content", "text",
            "keyword_hit", "source_type", "published_at", "created_at",
            "sentiment_label", "sentiment_score",
        ])
    df = pd.DataFrame(records)      
    for col in ["published_at", "created_at"]:
        df[col] = pd.to_datetime(df[col], errors="coerce", utc=True) 
    return df


def _load_fused_df() -> "pd.DataFrame | None":  
    """FusedData 直接转 DataFrame。"""
    if not _HAS_PANDAS:
        return None
    rows = FusedData.query.all()
    records = [{
        "id": r.id, "keyword": r.keyword,
        "window_start": r.window_start, "window_end": r.window_end,
        "fused_score": float(r.fused_score or 0.0),
        "created_at": r.created_at,
    } for r in rows]
    df = pd.DataFrame(records)
    if not df.empty:
        for col in ["window_start", "window_end", "created_at"]:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df



def safe_zscore(values: "np.ndarray") -> "np.ndarray":  
    """NumPy：返回 z-score；全零 / 单值时返回 0 数组，避免除零。"""
    if not _HAS_NUMPY:
        return np.array([], dtype=float)
    arr = np.asarray(values, dtype=float)
    if arr.size < 2:         
        return np.zeros_like(arr)
    std = np.std(arr, ddof=0)
    if std == 0 or np.isnan(std):   
        return np.zeros_like(arr)
    mean = np.mean(arr)
    return (arr - mean) / std   


# =============================================================
#  Matplotlib 图表
# =============================================================

def _save_chart(fig: "plt.Figure | None", rule_id: int, tag: str) -> str | None:  
    """ Matplotlib：保存 Figure，返回相对路径；失败静默返回 None。"""
    if fig is None or not _HAS_MPL:
        return None
    try:
        fname = f"rule{rule_id}_{tag}_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.png"   
        fpath = _ALERT_CHART_DIR / fname
        fig.tight_layout()
        fig.savefig(fpath, dpi=110, facecolor="white")
        plt.close(fig)
        rel = f"data/alerts/{fname}"
        return rel
    except Exception as ex:
        logger.warning("图表保存失败 rule=%s tag=%s: %s", rule_id, tag, ex)
        try:
            plt.close(fig)
        except Exception:
            pass
        return None


def _plot_heat_timeseries(fused_df: "pd.DataFrame", rule_id: int, tag: str = "heat") -> str | None:
    """ Matplotlib 热度时序（30min 桶）。Pandas 聚合。"""
    if fused_df is None or fused_df.empty or not _HAS_PANDAS or not _HAS_MPL:
        return None
    try:
        df = fused_df.copy()
        df["bucket"] = df["window_start"].dt.to_period("30min").dt.to_timestamp()  
        grouped = df.groupby("bucket", as_index=False)["fused_score"].sum()         
        fig, ax = plt.subplots(figsize=(8, 3.5))
        ax.plot(grouped["bucket"], grouped["fused_score"], marker="o", linewidth=1.8,
                color="#1f77b4", markerfacecolor="#ff7f0e")
        ax.set_title("热度时间序列 (30min 桶)")
        ax.set_xlabel("时间")
        ax.set_ylabel("融合热度")
        fig.autofmt_xdate()
        return _save_chart(fig, rule_id, tag)
    except Exception as ex:
        logger.warning("时序图生成失败: %s", ex)
        return None


def _plot_sentiment_pie(raw_df: "pd.DataFrame", rule_id: int, tag: str = "sentiment") -> str | None:
    """ Matplotlib 情感饼图。Pandas value_counts。"""
    if raw_df is None or raw_df.empty or not _HAS_PANDAS or not _HAS_MPL:
        return None
    try:
        counts = raw_df["sentiment_label"].value_counts(normalize=False)  
        if counts.empty:
            return None
        fig, ax = plt.subplots(figsize=(5, 4))
        ax.pie(counts.values, labels=counts.index, autopct="%1.1f%%",
               colors=["#2ca02c", "#d62728", "#7f7f7f", "#bcbd22"][:len(counts)])  
        ax.set_title("情感分布")
        return _save_chart(fig, rule_id, tag)
    except Exception as ex:
        logger.warning("饼图生成失败: %s", ex)
        return None


def _plot_negative_bar(hit_counter: dict, rule_id: int, tag: str = "neg_words") -> str | None:   
    """ Matplotlib 负面关键词条形图。 Dict 转 Pandas。"""
    if not hit_counter or not _HAS_PANDAS or not _HAS_MPL:
        return None
    try:
        df = pd.DataFrame(sorted(hit_counter.items(), key=lambda x: -x[1]), columns=["word", "count"])   
        if df.empty:
            return None
        fig, ax = plt.subplots(figsize=(7, max(3, 0.35 * len(df))))
        ax.barh(df["word"], df["count"], color="#d62728")
        ax.invert_yaxis()
        ax.set_title("负面关键词命中 Top")
        ax.set_xlabel("命中次数")
        return _save_chart(fig, rule_id, tag)
    except Exception as ex:
        logger.warning("条形图生成失败: %s", ex)
        return None


# =============================================================
#  各类型预警实现（Ch4 FlowControl + Ch11 Exception）
# =============================================================

def _scan_threshold(rule: AlertRule, fused_df: "pd.DataFrame | None") -> tuple[int, str, dict]:
    """阈值预警：近 1h 融合热度 / 条数。Ch10 timedelta + Pandas mask。"""
    if fused_df is None or fused_df.empty:
        return 0, "", {}
    cutoff = datetime.utcnow() - timedelta(hours=1)   
    mask = fused_df["window_start"] >= pd.Timestamp(cutoff, tz="UTC") 
    window = fused_df.loc[mask]
    total_score = float(window["fused_score"].sum() if not window.empty else 0.0)
    cnt = int(len(window))

    threshold = float(rule.threshold_value or rule.level1_threshold or 0.0)
    if threshold <= 0:  
        level = level_by_threshold(total_score, 0, 0)
    else:
        if total_score < threshold:  
            return 0, "", {"total_score_1h": total_score, "count": cnt}
        level = level_by_threshold(total_score, rule.level1_threshold, rule.level2_threshold) or 1

    msg = f"[阈值预警] 近1h热度={total_score:.2f} 超过阈值={threshold:.2f}" 
    return level, msg, {"total_score_1h": total_score, "count": cnt, "threshold": threshold}


def _scan_sensitive(rule: AlertRule, raw_df: "pd.DataFrame | None") -> tuple[int, str, dict]:
    """敏感词预警：regex 匹配"""
    words = split_words(rule.sensitive_words)
    neg_words = split_words(rule.negative_words)
    all_words = list(dict.fromkeys(words + neg_words))  
    if not all_words or raw_df is None or raw_df.empty:
        return 0, "", {}

    cutoff = datetime.utcnow() - timedelta(hours=24)  
    mask = raw_df["created_at"] >= pd.Timestamp(cutoff, tz="UTC")
    df = raw_df.loc[mask].copy()
    if df.empty:
        return 0, "", {}

    pattern = build_regex(all_words)  
    if pattern is None:
        return 0, "", {}

    # Pandas str 向量化 findall
    all_matches = df["text"].fillna("").apply(pattern.findall)
    hit_rows = all_matches[all_matches.apply(len) > 0]   # Pandas boolean indexing
    hit_count = int(all_matches.apply(len).sum())

    word_counter: dict[str, int] = {}  
    for matches in hit_rows:
        for w in matches:
            word_counter[w] = word_counter.get(w, 0) + 1

    if hit_count == 0:
        return 0, "", {}

    level = level_by_threshold(hit_count, rule.level1_threshold or 3, rule.level2_threshold or 15) or 1
    msg = f"[敏感词预警] 近24h命中 {hit_count} 次 / {len(hit_rows)} 条，Top: {list(word_counter)[:5]}"
    hits_sample = []
    for idx, row in df.loc[hit_rows.index[:5]].iterrows():
        hits_sample.append({"id": int(row["id"]), "title": row["title"], "words": hit_rows[idx]})
    return level, msg, {"hit_count": hit_count, "word_counter": word_counter, "hits": hits_sample}


def _scan_anomaly(rule: AlertRule, fused_df: "pd.DataFrame | None") -> tuple[int, str, dict]:
    """
     NumPy + Pandas rolling z-score 异常检测。
    Datetime: 30min 桶 + window_minutes / 30 滑动窗口。
    """
    if fused_df is None or fused_df.empty or not _HAS_PANDAS or not _HAS_NUMPY:
        return 0, "", {}

    window_min = int(rule.anomaly_window_minutes or 60)
    threshold = float(rule.zscore_threshold or 2.5)

    df = fused_df.copy().sort_values("window_start")
    df["bucket"] = df["window_start"].dt.to_period("30min").dt.to_timestamp()   
    grouped = df.groupby("bucket", as_index=False)["fused_score"].sum()

    if len(grouped) < 4:
        return 0, "", {"note": "数据点不足，至少需要 4 个 30min 桶"}

    win_size = max(2, window_min // 30)   
    grouped["rolling_mean"] = grouped["fused_score"].rolling(win_size, min_periods=2).mean()   # Pandas rolling
    grouped["rolling_std"] = grouped["fused_score"].rolling(win_size, min_periods=2).std().fillna(0)
    grouped["base_mean"] = grouped["rolling_mean"].shift(1)
    grouped["base_std"] = grouped["rolling_std"].shift(1).replace(0, np.nan)
    grouped["z"] = (grouped["fused_score"] - grouped["base_mean"]) / grouped["base_std"]  

    last = grouped.iloc[-1]
    if pd.isna(last["z"]) or abs(float(last["z"])) < threshold:   
        return 0, "", {"last_z": None, "threshold": threshold}

    level = 2 if abs(float(last["z"])) >= threshold * 1.5 else 1  
    msg = f"[异常检测] 最新桶 z-score={float(last['z']):.2f} 超过阈值 {threshold}"
    return level, msg, {
        "last_z": float(last["z"]), "threshold": threshold,
        "last_score": float(last["fused_score"]),
        "base_mean": float(last["base_mean"]), "base_std": float(last["base_std"]),
    }


def _scan_launch_campaign(rule: AlertRule,
                          raw_df: "pd.DataFrame | None",
                          fused_df: "pd.DataFrame | None") -> tuple[int, str, dict]:
    """
    iPhone Duo 首发专项预警 —— 按 rule_category 分发。
    if-elif-else 三阶段
    build_milestone_regexes 六类关键词
    每类预编译 pattern
     24h / 7d 时间窗
    BS4 + Pandas str 清洗后再 regex
    """
    category = rule.rule_category or CATEGORY_PRE_LAUNCH
    milestones = build_milestone_regexes()
    cutoff_24 = datetime.utcnow() - timedelta(hours=24) 
    cutoff_7d = datetime.utcnow() - timedelta(days=7)

    if raw_df is None or raw_df.empty:
        return 0, "", {"note": "暂无原始数据"}
    df24 = raw_df.loc[raw_df["created_at"] >= pd.Timestamp(cutoff_24, tz="UTC")].copy()
    df7 = raw_df.loc[raw_df["created_at"] >= pd.Timestamp(cutoff_7d, tz="UTC")].copy()

    snapshot: dict = {"category": category}
    if df24.empty and df7.empty:
        return 0, "", {"note": "近 7 天无数据", **snapshot}

    # Dict 统计每类 pattern 的命中数
    bucket_hits: dict[str, dict] = {}
    for name, pat in milestones.items():
        hits24 = df24["text"].fillna("").apply(lambda t: bool(pat.search(t))).sum()  
        hits7 = df7["text"].fillna("").apply(lambda t: bool(pat.search(t))).sum()
        bucket_hits[name] = {"24h": int(hits24), "7d": int(hits7)}

    # 负面情感占比
    neg_ratio = None
    try:
        if not df24.empty:
            neg = (df24["sentiment_label"] == "negative").sum()
            total = (df24["sentiment_label"] != "unknown").sum()
            neg_ratio = float(neg / total) if total else None 
    except Exception:
        neg_ratio = None

    snapshot["bucket_hits"] = bucket_hits
    snapshot["negative_ratio_24h"] = neg_ratio

    #  FlowControl: 三阶段分发
    if category == CATEGORY_PRE_LAUNCH:
        hit = bucket_hits["黄牛"]["24h"]
        neg_price = bucket_hits["价格"]["24h"]
        threshold = float(rule.threshold_value or 20)
        score = hit * 2 + neg_price   
        if score < threshold:
            return 0, "", snapshot
        level = level_by_threshold(score, rule.level1_threshold or threshold, rule.level2_threshold or threshold * 3) or 1
        msg = f"[首发前预警] 预热期黄牛={hit}/价格={neg_price}, 综合={score}"
        return level, msg, snapshot

    if category == CATEGORY_LAUNCH_DAY:
        heat_level, heat_msg, heat_snap = _scan_anomaly(rule, fused_df)
        neg_threshold = float(rule.level1_threshold or 0.3)
        neg_level = 2 if (neg_ratio is not None and neg_ratio >= 0.5) else (1 if (neg_ratio is not None and neg_ratio >= neg_threshold) else 0)
        overall_level = max(heat_level, neg_level)   
        if overall_level == 0 and heat_level == 0:
            return 0, "", snapshot
        parts = []
        if heat_msg:
            parts.append(heat_msg.replace("[异常检测]", "[首发日热度异常]"))   
        if neg_ratio is not None and neg_ratio >= neg_threshold:
            parts.append(f"[首发日情感爆发] 24h 负面占比 {neg_ratio:.0%}")
        snapshot["anomaly"] = heat_snap
        snapshot["negative_ratio_trigger"] = neg_level > 0
        return overall_level, "；".join(parts) if parts else "[首发日预警]", snapshot

    if category == CATEGORY_POST_LAUNCH:
        bug = bucket_hits["BUG"]["7d"]
        hw = bucket_hits["硬件"]["7d"]
        bad = bucket_hits["差评"]["7d"]
        threshold = float(rule.threshold_value or 10)
        score = bug + hw + bad
        if score < threshold:
            return 0, "", snapshot
        level = level_by_threshold(score, rule.level1_threshold or threshold, rule.level2_threshold or threshold * 2.5) or 1
        msg = f"[首发后预警] 7d: BUG={bug}/硬件={hw}/差评={bad}, 综合={score}"
        return level, msg, snapshot

    # general 兜底
    pos = bucket_hits["正面"]["24h"]
    neg = bucket_hits["差评"]["24h"] + bucket_hits["BUG"]["24h"]
    if neg <= pos:   
        return 0, "", snapshot
    level = level_by_threshold(neg - pos, rule.level1_threshold or 5, rule.level2_threshold or 15) or 1
    return level, f"[通用首发预警] 负面-正面 = {neg - pos}", snapshot


# =============================================================
#  主入口 —— Ch9 Dict Dispatch + Ch11 Exception 分段
# =============================================================

_SCAN_DISPATCHER = {   
    "threshold": _scan_threshold,
    "sensitive": _scan_sensitive,
    "anomaly": _scan_anomaly,
    "launch_campaign": _scan_launch_campaign,
}


def run_alert_scan() -> dict:  
    """预警扫描主入口"""
    rules: list[AlertRule] = AlertRule.query.filter_by(enabled=True).all()
    if not rules:
        return {"triggered": 0, "logs": []}

    # 预加载 DataFrame
    try:  
        raw_df = _load_raw_df()
    except Exception as ex:
        logger.exception("RawData DataFrame 加载失败: %s", ex)
        raw_df = None
    try:
        fused_df = _load_fused_df()
    except Exception as ex:
        logger.exception("FusedData DataFrame 加载失败: %s", ex)
        fused_df = None


    triggered = 0
    
    logs_payload: list[dict] = []

    for rule in rules:   
        func = _SCAN_DISPATCHER.get(rule.metric_type, _scan_threshold)   
        try:
           
            if rule.metric_type == "launch_campaign":
                level, msg, snap = func(rule, raw_df, fused_df)
            elif rule.metric_type == "anomaly":
                level, msg, snap = func(rule, fused_df)
            elif rule.metric_type == "threshold":
                level, msg, snap = func(rule, fused_df)
            else:  # sensitive
                level, msg, snap = func(rule, raw_df)
        except Exception as ex:
            logger.exception("规则 %s(%s) 扫描异常: %s", rule.id, rule.name, ex)
            continue

        if level == 0:  
            continue

        # Matplotlib 图表
        chart_path: str | None = None
        try:
            if rule.metric_type in ("threshold", "anomaly", "launch_campaign") and fused_df is not None:
                chart_path = _plot_heat_timeseries(fused_df, rule.id, tag=f"heat")
            if rule.metric_type in ("sensitive", "launch_campaign") and raw_df is not None:
                if "word_counter" in snap:
                    chart_path = _plot_negative_bar(snap.get("word_counter") or {}, rule.id, tag=f"neg")
                elif raw_df is not None and not raw_df.empty:
                    chart_path = _plot_sentiment_pie(raw_df, rule.id, tag=f"sent")
        except Exception as ex:
            logger.warning("规则 %s 图表生成失败: %s", rule.id, ex)
            chart_path = None

        # 写库
        category = rule.rule_category if rule.rule_category in VALID_CATEGORIES else CATEGORY_GENERAL
        db.session.add(AlertLog(   
            rule_id=rule.id, category=category, level=level, message=msg,
            metric_type=rule.metric_type,
            data_snapshot=json.dumps(snap or {}, ensure_ascii=False, default=str),
            chart_path=chart_path,
        ))
        triggered += 1   
        logs_payload.append({
            "rule_id": rule.id, "rule_name": rule.name, "category": category,
            "level": level, "metric_type": rule.metric_type,
            "message": msg, "chart_path": chart_path,
        })
    db.session.commit()
    return {"triggered": triggered, "logs": logs_payload}
