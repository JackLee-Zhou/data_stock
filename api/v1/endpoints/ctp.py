# -*- coding: utf-8 -*-
"""CTP 行情 API"""

import logging

from typing import Any, Dict, List
from fastapi import APIRouter, Body, HTTPException

from api.v1.schemas.ctp import CtpQuoteResponse, CtpStatusResponse
from src.services import ctp_service

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/status", response_model=CtpStatusResponse, summary="CTP 连接状态")
def ctp_status():
    s = ctp_service.get_status()
    if isinstance(s, dict):
        return CtpStatusResponse(connected=s.get("connected", False),
            logged_in=s.get("connected", False),
            front_address="", trading_day="",
            subscribed_count=s.get("futures", 0),
            last_error="" if s.get("connected") else "未连接")
    return CtpStatusResponse(connected=s.connected, logged_in=s.logged_in,
        front_address=s.front_address, trading_day=s.trading_day,
        subscribed_count=s.subscribed_count, last_error=s.last_error)


@router.get("/quotes", response_model=CtpQuoteResponse, summary="CTP 实时行情")
def ctp_quotes():
    quotes = ctp_service.get_quotes()
    return CtpQuoteResponse(quotes=quotes, count=len(quotes))


@router.post("/sync", summary="接收远端 ctp_engine 推送的增量 tick")
def ctp_sync(payload: Dict[str, Any] = Body(...)):
    """远端引擎定时推送增量 tick，写入本地 ctp_tick 表"""
    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
    from src.storage import DatabaseManager, CtpTick as CtpTickModel
    from datetime import datetime as _dt
    ticks = payload.get("ticks", [])
    db = DatabaseManager()
    count = 0
    try:
        with db.session_scope() as s:
            for t in ticks:
                try:
                    ts = _dt.fromisoformat(str(t.get("time", "")))
                except Exception:
                    ts = _dt.now()
                s.execute(sqlite_insert(CtpTickModel).values(
                    code=str(t.get("code", "")), trade_time=ts,
                    price=float(t.get("price", 0) or 0),
                    volume=float(t.get("volume", 0) or 0),
                    open_interest=float(t.get("open_interest", 0) or 0),
                    bid1=float(t.get("bid1", 0)) if t.get("bid1") else None,
                    ask1=float(t.get("ask1", 0)) if t.get("ask1") else None,
                ).on_conflict_do_nothing())
                count += 1
        return {"ok": True, "received": count}
    except Exception as exc:
        logger.error("接收远端数据失败: %s", exc)
        raise HTTPException(500, detail=str(exc))
