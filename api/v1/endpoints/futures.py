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
    """根据数据源自动分类：Sina主力合约 = 国内，Global = 国际"""
    return "domestic"  # 当前数据源为 Sina 国内期货


def _rate_limit():
    global _LAST_FETCH_TS
    elapsed = time.time() - _LAST_FETCH_TS
    if elapsed < 1.0:
        time.sleep(1.0 - elapsed)
    _LAST_FETCH_TS = time.time()


@router.get("/quotes", response_model=FuturesListResponse)
def get_futures_quotes(market: Optional[str] = Query(None, description="domestic/international/all")):
    """期货合约列表 — akshare fallback 34个主力合约，点击查看K线"""
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
        # CU0 → CU（去掉末尾数字0）
        base = "".join(c for c in str(code) if c.isalpha())
        for sym in [base.upper(), base.lower()]:
            try:
                df = ak.futures_zh_daily_sina(symbol=sym)
                if df is not None and not df.empty and len(df) > 0:
                    for _, r in df.iterrows():
                        ds = str(r.get("date", r.get("日期", "")))
                        try: td = datetime.strptime(ds[:10], "%Y-%m-%d").date()
                        except Exception: td = date.today()
                        rows.append({
                            "trade_date": td,
                            "open": float(r.get("open", r.get("开盘价", 0)) or 0),
                            "high": float(r.get("high", r.get("最高价", 0)) or 0),
                            "low": float(r.get("low", r.get("最低价", 0)) or 0),
                            "close": float(r.get("close", r.get("收盘价", 0)) or 0),
                            "volume": float(r.get("volume", r.get("成交量", 0)) or 0),
                            "open_interest": float(r.get("hold", r.get("持仓量", 0)) or 0),
                        })
                    if rows: from_cache = False; break
            except Exception: continue
        if rows:
            db.save_futures_daily(code, rows)

    # 2. 返回 DB 数据
    klines = db.get_futures_daily(code, days)
    return FuturesKlineResponse(
        code=code,
        klines=[KlineItem(**k) for k in klines],
        from_cache=bool(from_cache and klines),
    )
