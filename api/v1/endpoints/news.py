# -*- coding: utf-8 -*-
"""新闻监控 API"""

import logging
from fastapi import APIRouter, Query

from src.services.news_monitor import get_recent_news, scan_news_for_contracts, start_news_monitor

logger = logging.getLogger(__name__)
router = APIRouter()


@router.get("/events", summary="查询合约相关新闻")
def news_events(code: str = Query(...), minutes: int = Query(30, ge=1, le=1440)):
    return {"events": get_recent_news(code, minutes)}


@router.post("/scan", summary="手动触发新闻扫描")
def news_scan(code: str = Query(None)):
    codes = [code] if code else None
    scan_news_for_contracts(codes)
    return {"status": "ok"}
