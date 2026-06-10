# -*- coding: utf-8 -*-
"""CTP 统一服务：管理行情/交易连接生命周期，启动时自动连接 SimNow"""

import logging
import os
from typing import Optional

from data_provider.ctp_md_adapter import CtpMdAdapter
from data_provider.ctp_types import CtpQuote, CtpStatus

logger = logging.getLogger(__name__)

_ctp_started = False


def start_ctp() -> CtpStatus:
    """启动 CTP 行情连接（从 .env 读取配置）"""
    global _ctp_started
    if _ctp_started:
        return CtpMdAdapter().status

    md_front = os.getenv("CTP_MD_FRONT", "tcp://180.168.146.187:10131")
    broker = os.getenv("CTP_BROKER_ID", "9999")
    user = os.getenv("CTP_USER_ID", "")
    pwd = os.getenv("CTP_PASSWORD", "")

    if not user or not pwd:
        logger.warning("[CTP] 未配置 CTP_USER_ID / CTP_PASSWORD，跳过 CTP 连接")
        return CtpStatus(connected=False, last_error="未配置账号")

    adapter = CtpMdAdapter()
    ok = adapter.connect(md_front, broker, user, pwd)
    if not ok:
        return adapter.status

    # 从 watchlist 读取自选期货合约
    try:
        from src.storage import DatabaseManager
        db = DatabaseManager()
        codes = db.get_watchlist("futures")
        if not codes:
            codes = db.get_watchlist("default")
        if codes:
            adapter.subscribe([c.upper() for c in codes])
    except Exception as exc:
        logger.warning("[CTP] 读取自选合约失败: %s", exc)

    _ctp_started = True
    return adapter.status


def get_quotes() -> dict:
    adapter = CtpMdAdapter()
    quotes = adapter.get_quotes()
    return {k: {
        "code": q.code, "name": q.name, "price": q.price,
        "change_pct": q.change_pct, "bid1": q.bid1, "ask1": q.ask1,
        "volume": q.volume, "open_interest": q.open_interest,
        "high": q.high, "low": q.low, "open": q.open,
        "prev_close": q.prev_close,
        "updated_at": q.updated_at.isoformat() if q.updated_at else "",
    } for k, q in quotes.items()}


def get_quote(code: str) -> Optional[dict]:
    q = CtpMdAdapter().get_quote(code)
    if not q:
        return None
    return {"code": q.code, "price": q.price, "bid1": q.bid1, "ask1": q.ask1,
            "volume": q.volume, "open_interest": q.open_interest,
            "updated_at": q.updated_at.isoformat() if q.updated_at else ""}


def get_status() -> CtpStatus:
    return CtpMdAdapter().status
