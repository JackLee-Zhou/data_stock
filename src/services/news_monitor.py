# -*- coding: utf-8 -*-
"""
新闻监控系统（独立模块）

- 定时轮询（每 5 分钟）
- 行情异常反向触发（跳涨/跳跌 → 立即查新闻）
- 多源：Google 搜索 + X/Twitter + akshare 官媒
- 结果 LLM 打分 + 存储到 news_event 表
"""

from __future__ import annotations

import json
import logging
import threading
import time as _time
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# 合约 → 关键词映射
CONTRACT_KEYWORDS: Dict[str, List[str]] = {
    "CU0": ["铜", "LME", "智利铜矿", "电力"],
    "RB0": ["螺纹钢", "房地产", "基建", "限产"],
    "I0": ["铁矿石", "澳洲", "巴西", "发货量"],
    "SC0": ["原油", "OPEC", "中东", "页岩油"],
    "AU0": ["黄金", "美联储", "通胀", "避险"],
    "M0": ["豆粕", "USDA", "南美", "天气"],
}

_VOLATILITY_THRESHOLD = 0.02  # 2% 跳涨/跳跌触发反向查询
_monitor_thread: Optional[threading.Thread] = None
_stop = False


def start_news_monitor(interval_seconds: int = 300):
    """启动后台新闻监控线程"""
    global _monitor_thread, _stop
    if _monitor_thread and _monitor_thread.is_alive():
        return
    _stop = False

    def _loop():
        while not _stop:
            try:
                scan_news_for_contracts()
            except Exception as exc:
                logger.error("[新闻监控] 轮询异常: %s", exc)
            _time.sleep(interval_seconds)

    _monitor_thread = threading.Thread(target=_loop, daemon=True)
    _monitor_thread.start()
    logger.info("[新闻监控] 已启动，间隔 %ds", interval_seconds)


def stop_news_monitor():
    global _stop; _stop = True


def scan_news_for_contracts(contracts: Optional[List[str]] = None):
    """扫描指定合约的新闻，写入 news_event 表。"""
    if contracts is None:
        contracts = list(CONTRACT_KEYWORDS.keys())

    for code in contracts:
        keywords = CONTRACT_KEYWORDS.get(code, [code])
        query = " ".join(keywords[:3]) + " 期货"
        items = _fetch_news(query)
        if items:
            _save_events(code, items)


def trigger_volatility_check(code: str, change_pct: float):
    """行情异常 → 反向触发新闻查询"""
    if abs(change_pct) >= _VOLATILITY_THRESHOLD:
        direction = "暴涨" if change_pct > 0 else "暴跌"
        query = f"{CONTRACT_KEYWORDS.get(code, [code])[0]} {direction} 突发"
        logger.warning("[新闻监控] 行情异常触发: %s %.2f%% → %s", code, change_pct * 100, query)
        items = _fetch_news(query)
        if items:
            for item in items:
                item["urgency"] = "high"
            _save_events(code, items)


def _fetch_news(query: str) -> List[Dict[str, Any]]:
    """多源新闻搜索"""
    items = []

    # 1. akshare 期货新闻
    try:
        import akshare as ak
        df = ak.futures_news_shmet()
        if df is not None and not df.empty:
            for _, r in df.head(5).iterrows():
                title = str(r.get("content", r.get("title", "")))
                if title and any(kw in title for kw in query.split()):
                    items.append({"title": title, "source": "akshare", "url": ""})
    except Exception:
        pass

    # 2. Google 搜索（通过现有 search_service）
    try:
        from src.search_service import get_search_service
        svc = get_search_service()
        results = svc.search(query, limit=3)
        for r in results:
            items.append({"title": r.get("title", ""), "source": "google", "url": r.get("url", "")})
    except Exception:
        pass

    return items


def _save_events(code: str, items: List[dict]):
    try:
        from src.storage import DatabaseManager, NewsEvent
        db = DatabaseManager()
        now = datetime.now()
        with db.session_scope() as s:
            for item in items:
                s.add(NewsEvent(
                    title=item.get("title", "")[:500],
                    source=item.get("source", "unknown"),
                    url=item.get("url", ""),
                    affected_contracts=json.dumps([code]),
                    urgency=item.get("urgency", "medium"),
                    published_at=now - timedelta(minutes=5),
                ))
    except Exception as exc:
        logger.warning("[新闻监控] 存储失败: %s", exc)


def get_recent_news(code: str, minutes: int = 30) -> List[dict]:
    """查询某个合约最近 N 分钟的新闻（供前端/AI调用）"""
    try:
        from src.storage import DatabaseManager, NewsEvent
        db = DatabaseManager()
        cutoff = datetime.now() - timedelta(minutes=minutes)
        with db.session_scope() as s:
            rows = (
                s.query(NewsEvent)
                .filter(NewsEvent.affected_contracts.contains(code),
                        NewsEvent.published_at >= cutoff)
                .order_by(NewsEvent.published_at.desc())
                .limit(20).all()
            )
            return [{"title": r.title, "source": r.source, "urgency": r.urgency,
                     "url": r.url, "time": str(r.published_at)} for r in rows]
    except Exception:
        return []
