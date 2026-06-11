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
    """期货行情 — 直接从 CTP 实时数据（Group2: 238个期货合约）"""
    items = []
    try:
        from src.services.ctp_service import get_quotes as get_ctp_quotes
        ctp = get_ctp_quotes()
        for code, q in ctp.items():
            price = q.get("price", 0) or 0
            if price <= 0: continue
            prev = q.get("prev_close") or price
            chg = ((price - prev) / prev * 100) if prev else 0
            items.append({
                "contract_code": code,
                "contract_name": q.get("name", code),
                "last_price": round(price, 2),
                "change": round(price - prev, 2),
                "change_pct": round(chg, 2),
                "volume": int(q.get("volume", 0) or 0),
                "open_interest": int(q.get("open_interest", 0) or 0),
                "high": q.get("high"), "low": q.get("low"),
                "open": q.get("open"), "prev_close": q.get("prev_close") or price,
                "bid1": q.get("bid1"), "ask1": q.get("ask1"),
                "market": "domestic",
            })
        items.sort(key=lambda x: x.get("volume", 0), reverse=True)
    except Exception as exc:
        logger.warning("CTP行情失败: %s", exc)

    if market and market != "all":
        items = [i for i in items if i["market"] == market]
    return FuturesListResponse(items=[FuturesQuote(**i) for i in items[:200]], total=len(items),
                               updated_at=datetime.now(TZ).isoformat())


@router.get("/quotes/{code:path}/kline", response_model=FuturesKlineResponse)
def get_futures_kline(code: str, days: int = Query(120, ge=1, le=365),
                       period: str = Query("daily", description="daily|1m|5m|15m")):
    """K线 — daily用futures_zh_daily_sina，分时用futures_zh_minute_sina"""
    import akshare as ak, os as _os, certifi
    if not _os.environ.get("SSL_CERT_FILE"): _os.environ["SSL_CERT_FILE"] = certifi.where()

    items = []
    sym = code if any(c.isdigit() for c in code) else code
    try:
        if period == "daily":
            df = ak.futures_zh_daily_sina(symbol=sym)
            if df is not None and not df.empty:
                for _, r in df.tail(days).iterrows():
                    items.append(KlineItem(trade_date=str(r.get("date", "")),
                        open=float(r.get("open", 0) or 0), high=float(r.get("high", 0) or 0),
                        low=float(r.get("low", 0) or 0), close=float(r.get("close", 0) or 0),
                        volume=float(r.get("volume", 0) or 0), open_interest=float(r.get("hold", 0) or 0)))
        else:
            limit = {"1m": 240, "5m": 200, "15m": 100}.get(period, 240)
            df = ak.futures_zh_minute_sina(symbol=sym)
            if df is not None and not df.empty:
                for _, r in df.tail(limit).iterrows():
                    items.append(KlineItem(trade_date=str(r.get("datetime", "")),
                        open=float(r.get("open", 0) or 0), high=float(r.get("high", 0) or 0),
                        low=float(r.get("low", 0) or 0), close=float(r.get("close", 0) or 0),
                        volume=float(r.get("volume", 0) or 0), open_interest=float(r.get("hold", 0) or 0)))
    except Exception as exc:
        logger.warning("K线失败 %s: %s", code, exc)

    return FuturesKlineResponse(code=code, klines=items, from_cache=bool(items))
