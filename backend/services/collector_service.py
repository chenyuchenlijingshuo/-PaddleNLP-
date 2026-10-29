"""
舆情分析系统 - 数据采集服务
============================

该模块负责舆情数据的采集功能，包括：
1. 新闻数据采集（模拟数据）
2. 微博数据采集（真实爬虫）
3. 采集规则执行
4. 数据去重和存储

技术实现：
- 微博采集：调用外部weibo-crawler项目
- 新闻采集：目前使用模拟数据，可扩展为真实爬虫
- 限流控制：使用MinuteRateLimiter防止请求过频
- 数据去重：基于内容哈希值去重

主要函数：
- run_collect_by_rule: 执行采集规则
- _fetch_weibo_items: 微博数据采集
- _fetch_news_with_fallback: 新闻数据采集
"""

import logging
import random
import re
import sqlite3
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
import json

import requests

from config import Config
from extensions import db
from models import CollectRule, CollectRunLog, RawData
from services.rate_limiter import MinuteRateLimiter
from utils.security import content_dedup_hash

logger = logging.getLogger(__name__)

# 限流器：控制每分钟最大请求数
_rate_limiter = MinuteRateLimiter(max_per_minute=Config.COLLECT_MAX_REQUESTS_PER_MINUTE)

# 微博爬虫相关路径配置
PROJECT_ROOT = Path(__file__).resolve().parents[2]
WEIBO_CRAWLER_DIR = PROJECT_ROOT / "weibo-crawler"
WEIBO_SQLITE_PATH = WEIBO_CRAWLER_DIR / "weibodata.db"
WEIBO_USER_LIST_PATH = WEIBO_CRAWLER_DIR / "user_id_list.txt"
WEIBO_DATA_DIR = WEIBO_CRAWLER_DIR / "weibo_data"
WEIBO_CONFIG_PATH = WEIBO_CRAWLER_DIR / "config.json"


def _split_values(raw: str):
    """
    分割字符串值
    
    功能说明：
    - 将换行符替换为逗号
    - 按逗号分割字符串
    - 去除空白项
    
    参数：
    - raw: 原始字符串
    
    返回值：
    - 分割后的字符串列表
    """
    text = (raw or "").replace("\n", ",").replace("\r", ",")
    # 兼容中文输入法下的全角逗号、顿号、分号
    for sep in ["，", "、", "；", ";"]:
        text = text.replace(sep, ",")
    return [item.strip() for item in text.split(",") if item.strip()]


def _mock_items(rule: CollectRule):
    """
    生成模拟采集数据
    
    功能说明：
    - 用于测试和演示
    - 根据规则生成模拟新闻或微博数据
    - 时间递减模拟真实数据
    
    参数：
    - rule: 采集规则对象
    
    返回值：
    - 模拟数据列表
    """
    now = datetime.utcnow()
    keywords = _split_values(rule.keywords) or ["舆情"]
    items = []
    for i in range(max(min(rule.max_count or 10, 50), 1)):
        kw = random.choice(keywords)
        src = "模拟新闻站" if rule.source_type == "news" else "模拟微博"
        items.append(
            {
                "title": f"{kw} 事件进展 #{i + 1}",
                "content": f"这是一条关于 {kw} 的模拟{rule.source_type}内容。",
                "published_at": now - timedelta(minutes=i * 3),
                "source_name": src,
                "url": f"https://example.com/{rule.source_type}/{rule.id}/{i + 1}",
                "keyword_hit": kw,
                "source_type": rule.source_type,
            }
        )
    return items


def _fetch_news_with_fallback(rule: CollectRule):
    """
    新闻数据采集（带降级机制）
    
    功能说明：
    - 检测网络连接状态
    - 网络正常时返回模拟数据
    - 网络异常时返回降级模拟数据
    - 使用限流器控制请求频率
    
    参数：
    - rule: 采集规则对象
    
    返回值：
    - (数据列表, 状态信息)
    """
    _rate_limiter.acquire()
    try:
        requests.get("https://httpbin.org/get", timeout=3)
        return _mock_items(rule), "network-ok-mock-data"
    except Exception as ex:
        logger.warning("collector network fallback: %s", ex)
        return _mock_items(rule), f"fallback-mock: {ex}"


def _parse_weibo_datetime(value):
    if not value:
        return None
    text = str(value).strip()
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def _build_weibo_url(row):
    weibo_id = row.get("id")
    return f"https://m.weibo.cn/detail/{weibo_id}" if weibo_id else "https://m.weibo.cn/"


def _prepare_weibo_user_list(rule: CollectRule):
    user_ids = _split_values(rule.keywords)
    if not user_ids:
        raise ValueError("微博采集需要填写用户ID")
    invalid = [item for item in user_ids if not item.isdigit()]
    if invalid:
        raise ValueError("微博用户ID只能填写数字，多个用逗号分隔")
    WEIBO_USER_LIST_PATH.write_text("\n".join(user_ids), encoding="utf-8")
    return user_ids


def _to_weibo_date(value):
    if not value:
        return ""
    return value.strftime("%Y-%m-%d")


def _sync_weibo_config_with_rule(rule: CollectRule):
    """
    Keep weibo-crawler config aligned with current rule time range so
    synchronous runs avoid scanning too large windows.
    """
    if not WEIBO_CONFIG_PATH.exists():
        return
    try:
        raw = WEIBO_CONFIG_PATH.read_text(encoding="utf-8")
        config = json.loads(raw)
    except Exception:
        logger.warning("unable to read weibo config, skip sync")
        return

    since_source = rule.time_start or (datetime.utcnow() - timedelta(days=7))
    since_date = _to_weibo_date(since_source)
    end_date = _to_weibo_date(rule.time_end)
    max_session = max(min(int(rule.max_count or 30), 200), 10)
    page_count = max(min(max_session, 20), 10)

    config["since_date"] = since_date
    config["end_date"] = end_date
    config["page_weibo_count"] = page_count

    try:
        WEIBO_CONFIG_PATH.write_text(json.dumps(config, ensure_ascii=False, indent=4), encoding="utf-8")
    except Exception as e:
        logger.warning("unable to write weibo config: %s", e)


def _tail_text(text: str, max_lines: int = 8):
    lines = [x for x in (text or "").splitlines() if x.strip()]
    if not lines:
        return ""
    return "\n".join(lines[-max_lines:])



def _match_topic_keywords(item, topic_keywords):
    text = f"{item.get('title') or ''}\n{item.get('content') or ''}".lower()
    hits = []
    for kw in topic_keywords:
        if kw and kw.lower() in text and kw not in hits:
            hits.append(kw)
    return hits


def _load_weibo_items_from_sqlite(rule: CollectRule, user_ids, limit):
    if not WEIBO_SQLITE_PATH.exists():
        raise FileNotFoundError(f"未找到微博结果库: {WEIBO_SQLITE_PATH}")

    items = []
    target_ids = set(user_ids)
    with sqlite3.connect(WEIBO_SQLITE_PATH) as conn:
        conn.row_factory = sqlite3.Row
        rows = conn.execute("SELECT * FROM weibo ORDER BY created_at DESC").fetchall()
        for row in rows:
            data = dict(row)
            row_user_id = str(data.get("user_id") or "").strip()
            if target_ids and row_user_id not in target_ids:
                continue
            content = (data.get("text") or "").strip()
            published_at = _parse_weibo_datetime(data.get("created_at"))
            if rule.time_start and published_at and published_at < rule.time_start:
                continue
            if rule.time_end and published_at and published_at > rule.time_end:
                continue
            items.append(
                {
                    "title": content[:60] or f"微博 {data.get('id', '')}",
                    "content": content,
                    "published_at": published_at,
                    "source_name": data.get("screen_name") or "微博",
                    "url": _build_weibo_url(data),
                    "keyword_hit": row_user_id,
                    "source_type": "weibo",
                }
            )
            if len(items) >= limit:
                break
    return items


def _load_weibo_items_from_files(rule: CollectRule, user_ids, limit):
    if not WEIBO_DATA_DIR.exists():
        raise FileNotFoundError(f"未找到微博数据目录: {WEIBO_DATA_DIR}")

    target_ids = set(str(x).strip() for x in user_ids)
    json_paths = []
    for uid in target_ids:
        json_paths.extend(list(WEIBO_DATA_DIR.rglob(f"{uid}.json")))

    items = []
    for path in json_paths:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue

        user = payload.get("user") or {}
        weibos = payload.get("weibo") or []
        for wb in weibos:
            row_user_id = str(wb.get("user_id") or user.get("id") or "").strip()
            if target_ids and row_user_id not in target_ids:
                continue
            published_at = _parse_weibo_datetime(wb.get("created_at") or wb.get("full_created_at"))
            if rule.time_start and published_at and published_at < rule.time_start:
                continue
            if rule.time_end and published_at and published_at > rule.time_end:
                continue
            text = (wb.get("text") or "").strip()
            items.append(
                {
                    "title": text[:60] or f"微博 {wb.get('id', '')}",
                    "content": text,
                    "published_at": published_at,
                    "source_name": wb.get("screen_name") or user.get("screen_name") or "微博",
                    "url": _build_weibo_url(wb),
                    "keyword_hit": row_user_id,
                    "source_type": "weibo",
                }
            )
            if len(items) >= limit:
                break
        if len(items) >= limit:
            break

    items.sort(key=lambda x: x.get("published_at") or datetime.min, reverse=True)
    return items[:limit]


def _run_weibo_crawler():
    if not WEIBO_CRAWLER_DIR.exists():
        raise FileNotFoundError(f"未找到目录: {WEIBO_CRAWLER_DIR}")
    if not WEIBO_USER_LIST_PATH.exists():
        raise FileNotFoundError(f"未找到用户列表: {WEIBO_USER_LIST_PATH}")

    try:
        result = subprocess.run(
            [sys.executable, "weibo.py"],
            cwd=str(WEIBO_CRAWLER_DIR),
            capture_output=True,
            text=True,
            timeout=900,
        )
    except subprocess.TimeoutExpired as ex:
        tail = _tail_text((ex.stdout or "") + "\n" + (ex.stderr or ""))
        raise RuntimeError(f"微博爬虫执行超时(>900秒){f'，最近输出：{tail}' if tail else ''}") from ex
    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        brief = _tail_text(stderr or stdout)
        raise RuntimeError(brief or "微博爬虫执行失败")
    return "weibo-crawler-ok"


def _fetch_weibo_items(rule: CollectRule):
    _rate_limiter.acquire()
    user_ids = _prepare_weibo_user_list(rule)
    _sync_weibo_config_with_rule(rule)
    info = _run_weibo_crawler()

    limit = max(rule.max_count or 100, 1)
    topic_keywords = _split_values(rule.topic_keywords or "")
    # 配置主题词时多取一些原始微博，避免过滤后数量不足
    fetch_limit = max(limit * 3, 100) if topic_keywords else limit

    # 优先从爬虫输出文件读取（该项目默认输出 json/csv），若存在 sqlite 则回退使用 sqlite
    if WEIBO_SQLITE_PATH.exists():
        items = _load_weibo_items_from_sqlite(rule, user_ids, fetch_limit)
        if not items:
            items = _load_weibo_items_from_files(rule, user_ids, fetch_limit)
            if items:
                info = f"{info}; sqlite-empty-fallback-json"
            else:
                info = f"{info}; 未找到用户ID {user_ids} 的微博数据，请检查用户ID是否正确或Cookie是否过期"
    else:
        items = _load_weibo_items_from_files(rule, user_ids, fetch_limit)
        if not items:
            info = f"{info}; 未找到用户ID {user_ids} 的微博数据文件"

    if topic_keywords and items:
        matched = []
        for item in items:
            hits = _match_topic_keywords(item, topic_keywords)
            if not hits:
                continue
            item["keyword_hit"] = ",".join(hits)
            matched.append(item)
        info = f"{info}; 主题筛选命中 {len(matched)}/{len(items)} 条"
        items = matched

    return items[:limit], info


def _fetch_items(rule: CollectRule):
    if rule.source_type == "weibo":
        return _fetch_weibo_items(rule)
    return _fetch_news_with_fallback(rule)


def run_collect_by_rule(rule_id: int):
    rule = db.session.get(CollectRule, rule_id)
    if not rule:
        return {"success": False, "message": "规则不存在"}
    if not rule.enabled:
        return {"success": False, "message": "规则未启用"}
    # Avoid duplicate sync runs for the same rule.
    existing_running = (
        CollectRunLog.query.filter_by(rule_id=rule.id, status="running")
        .order_by(CollectRunLog.started_at.desc())
        .first()
    )
    if existing_running:
        started_at = existing_running.started_at or datetime.utcnow()
        if datetime.utcnow() - started_at < timedelta(minutes=5):
            return {"success": False, "message": "该规则已有采集任务在执行中，请稍后再试"}
        existing_running.status = "failed"
        existing_running.message = "任务状态已过期，自动标记失败"
        existing_running.ended_at = datetime.utcnow()
        db.session.add(existing_running)
        db.session.commit()

    run_log = CollectRunLog(rule_id=rule.id, status="running", message="starting")
    db.session.add(run_log)
    db.session.commit()
    inserted = 0

    try:
        items, info = _fetch_items(rule)
        for x in items:
            pub = x.get("published_at") or datetime.utcnow()
            dedup_hash = content_dedup_hash(
                x.get("title", ""),
                x.get("source_name", ""),
                pub.isoformat(),
                x.get("url", ""),
            )
            if RawData.query.filter_by(dedup_hash=dedup_hash).first():
                continue
            db.session.add(
                RawData(
                    rule_id=rule.id,
                    title=x.get("title"),
                    content=x.get("content"),
                    published_at=pub,
                    source_name=x.get("source_name"),
                    url=x.get("url"),
                    keyword_hit=x.get("keyword_hit"),
                    source_type=x.get("source_type") or rule.source_type,
                    dedup_hash=dedup_hash,
                )
            )
            inserted += 1

        run_log.status = "success"
        run_log.message = info
        run_log.items_fetched = inserted
        run_log.ended_at = datetime.utcnow()
        db.session.commit()
        return {
            "success": True,
            "rule_id": rule.id,
            "inserted": inserted,
            "status": run_log.status,
            "message": run_log.message,
        }
    except Exception as ex:
        db.session.rollback()
        logger.exception("collector run error")
        run_log.status = "failed"
        run_log.message = str(ex)
        run_log.ended_at = datetime.utcnow()
        db.session.add(run_log)
        db.session.commit()
        return {"success": False, "message": str(ex)}