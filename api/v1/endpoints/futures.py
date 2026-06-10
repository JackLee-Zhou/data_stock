# -*- coding: utf-8 -*-
"""期货行情 + K线"""

import logging
import time
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from api.v1.schemas.futures import FuturesKlineResponse, FuturesListResponse, FuturesQuote, KlineItem
from data_provider.base import DataFetcherManager

logger = logging.getLogger(__name__)
router = APIRouter()
TZ = timezone(timedelta(hours=8))

_LAST_FETCH_TS = 0  # 请求间隔控制，防止被 ban


def _classify(code: str, name: str) -> str:
    """futures_global_spot_em 返回的全是全球期货（CBOT/CME/COMEX等），国内期货需单独API"""
    return "international"


def _rate_limit():
    global _LAST_FETCH_TS
    elapsed = time.time() - _LAST_FETCH_TS
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _LAST_FETCH_TS = time.time()


@router.get("/quotes", response_model=FuturesListResponse)
def get_futures_quotes(market: Optional[str] = Query(None, description="domestic/international/all")):
    manager = DataFetcherManager()
    try:
        items_raw = manager.get_futures_quotes() or []
    except Exception as exc:
        raise HTTPException(503, detail={"title": "获取失败", "message": str(exc)}) from exc
    items = [{**r, "market": _classify(r.get("contract_code", ""), r.get("contract_name", ""))} for r in items_raw]
    if market and market != "all":
        items = [i for i in items if i["market"] == market]
    return FuturesListResponse(items=[FuturesQuote(**i) for i in items], total=len(items),
                               updated_at=datetime.now(TZ).isoformat())


@router.get("/quotes/{code:path}/kline", response_model=FuturesKlineResponse)
def get_futures_kline(code: str, days: int = Query(120, ge=1, le=365)):
    """获取合约日K线，增量拉取 + 本地缓存"""
    from src.storage import DatabaseManager
    db = DatabaseManager()

    # 1. 查 DB 已有最新日期
    latest_date = db.get_futures_latest_date(code)
    today = date.today()
    fetch_start: Optional[date] = None

    if latest_date is None:
        # 首次加载：拉 120 天
        fetch_start = today - timedelta(days=days * 2)  # 留余量
    elif latest_date < today - timedelta(days=1):
        # 有缺失：增量拉取
        fetch_start = latest_date - timedelta(days=2)
    # 否则：数据已是最新，不拉取

    from_cache = True
    if fetch_start:
        _rate_limit()
        import akshare as ak
        rows = []
        # 尝试多个K线接口（全球期货代码不兼容 hist_em）
        base = "".join(c for c in str(code) if c.isalpha()).upper()  # CL00Y → CL
        apis = [
            ("global_hist", lambda: ak.futures_global_hist_em(symbol=base)),
            ("main_sina", lambda: ak.futures_main_sina(symbol=code, start_date=fetch_start.strftime("%Y%m%d"), end_date=today.strftime("%Y%m%d"))),
        ]
        for api_name, fn in apis:
            try:
                df = fn()
                if df is not None and not df.empty:
                    rows = [
                        {"trade_date": str(r.get("日期", "")), "open": float(r.get("开盘", r.get("open", 0)) or 0),
                         "high": float(r.get("最高", r.get("high", 0)) or 0), "low": float(r.get("最低", r.get("low", 0)) or 0),
                         "close": float(r.get("收盘", r.get("close", 0)) or 0), "volume": float(r.get("成交量", r.get("volume", 0)) or 0),
                         "open_interest": float(r.get("持仓量", r.get("open_interest", 0)) or 0)}
                        for _, r in df.iterrows()
                    ]
                    if rows:
                        from_cache = False
                        break
            except Exception as exc:
                logger.debug("期货K线 %s 尝试 %s 失败: %s", code, api_name, exc)
        if rows:
            db.save_futures_daily(code, rows)

    # 2. 返回 DB 数据
    klines = db.get_futures_daily(code, days)
    return FuturesKlineResponse(
        code=code,
        klines=[KlineItem(**k) for k in klines],
        from_cache=bool(from_cache and klines),
    )
