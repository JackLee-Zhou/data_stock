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
    """
    K线 — daily用akshare历史数据，分时用CTP tick聚合。
    CTP tick 存在 ctp_tick 表，每2秒写入。首次加载需等 tick 积累。
    """
    from src.storage import DatabaseManager
    db = DatabaseManager()

    items = []
    if period == "daily":
        # 日K：akshare历史数据
        import akshare as ak, os as _os, certifi
        if not _os.environ.get("SSL_CERT_FILE"): _os.environ["SSL_CERT_FILE"] = certifi.where()
        try:
            df = ak.futures_zh_daily_sina(symbol=code)
            if df is not None and not df.empty:
                for _, r in df.tail(days).iterrows():
                    items.append(KlineItem(trade_date=str(r.get("date", "")),
                        open=float(r.get("open", 0) or 0), high=float(r.get("high", 0) or 0),
                        low=float(r.get("low", 0) or 0), close=float(r.get("close", 0) or 0),
                        volume=float(r.get("volume", 0) or 0), open_interest=float(r.get("hold", 0) or 0)))
        except Exception as exc:
            logger.warning("日K失败 %s: %s", code, exc)
    else:
        # 分时K线：从 CTP tick 聚合
        from sqlalchemy import text, func
        minutes = {"1m": 1, "5m": 5, "15m": 15}.get(period, 1)
        limit = {"1m": 240, "5m": 200, "15m": 100}.get(period, 240)
        try:
            with db.session_scope() as s:
                rows = s.execute(text(f"""
                    SELECT
                        strftime('%Y-%m-%d %H:%M:00', trade_time, '-{minutes} minutes') as bucket,
                        MIN(price) as low, MAX(price) as high,
                        FIRST_VALUE(price) OVER win as open,
                        LAST_VALUE(price) OVER win as close,
                        SUM(volume) as total_volume,
                        MAX(open_interest) as oi
                    FROM ctp_tick
                    WHERE code = :code AND trade_time >= datetime('now', '-1 day')
                    GROUP BY bucket
                    WINDOW win AS (PARTITION BY bucket ORDER BY trade_time ROWS BETWEEN UNBOUNDED PRECEDING AND UNBOUNDED FOLLOWING)
                    ORDER BY bucket DESC
                    LIMIT :limit
                """), {"code": code, "limit": limit}).fetchall()
                for r in reversed(rows):
                    items.append(KlineItem(trade_date=r[0],
                        open=float(r[3] or r[4] or 0), high=float(r[2] or 0),
                        low=float(r[1] or 0), close=float(r[4] or 0),
                        volume=float(r[5] or 0), open_interest=float(r[6] or 0)))
        except Exception as exc:
            logger.warning("CTP tick聚合失败 %s: %s", code, exc)

    return FuturesKlineResponse(code=code, klines=items, from_cache=False)
