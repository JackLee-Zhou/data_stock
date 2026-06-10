# -*- coding: utf-8 -*-
"""期货行情 + K线"""

import logging
import time
from datetime import date, datetime as _dt, timedelta, timezone
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
        try:
            df = ak.futures_zh_daily_sina(symbol=code)
            if df is not None and not df.empty:
                rows = []
                for _, r in df.iterrows():
                    dt_str = str(r.get("日期", ""))
                    try:
                        td = _dt.strptime(dt_str, "%Y-%m-%d").date() if len(dt_str) > 10 else _dt.strptime(dt_str, "%Y-%m-%d").date()
                    except Exception:
                        td = date.today()
                    if len(dt_str) == 8:
                        td = _dt.strptime(dt_str, "%Y%m%d").date()
                    rows.append({
                        "trade_date": td,
                        "open": float(r.get("开盘价", r.get("open", 0)) or 0),
                        "high": float(r.get("最高价", r.get("high", 0)) or 0),
                        "low": float(r.get("最低价", r.get("low", 0)) or 0),
                        "close": float(r.get("收盘价", r.get("close", 0)) or 0),
                        "volume": float(r.get("成交量", r.get("volume", 0)) or 0),
                        "open_interest": float(r.get("持仓量", r.get("open_interest", 0)) or 0),
                    })
                if rows:
                    from_cache = False
                    db.save_futures_daily(code, rows)
        except Exception as exc:
            logger.warning("期货K线 %s 拉取失败: %s", code, exc)

    # 2. 返回 DB 数据
    klines = db.get_futures_daily(code, days)
    return FuturesKlineResponse(
        code=code,
        klines=[KlineItem(**k) for k in klines],
        from_cache=bool(from_cache and klines),
    )
