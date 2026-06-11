# -*- coding: utf-8 -*-
"""CTP 行情 API"""

import logging

from fastapi import APIRouter

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
