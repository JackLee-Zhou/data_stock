# -*- coding: utf-8 -*-
"""
期货行情接口

GET /api/v1/futures/quotes — 国内商品期货主力合约行情
"""

import logging
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException

from api.v1.schemas.futures import FuturesListResponse, FuturesQuote
from data_provider.base import DataFetcherManager

logger = logging.getLogger(__name__)

router = APIRouter()

TZ_SHANGHAI = timezone(timedelta(hours=8))


@router.get(
    "/quotes",
    response_model=FuturesListResponse,
    responses={
        200: {"description": "期货行情列表"},
        503: {"description": "期货数据暂不可用"},
    },
    summary="获取国内期货主力合约行情",
    description="返回国内商品期货主力合约的实时报价，包括合约代码、名称、最新价、涨跌幅、成交量、持仓量等。"
    "数据来源：新浪财经（通过 akshare）。",
)
def get_futures_quotes() -> FuturesListResponse:
    """获取国内商品期货主力合约行情。"""
    manager = DataFetcherManager()

    try:
        items_raw = manager.get_futures_quotes()
    except Exception as exc:
        logger.error("Failed to fetch futures quotes: %s", exc, exc_info=True)
        raise HTTPException(
            status_code=503,
            detail={
                "title": "期货数据获取失败",
                "message": "当前无法获取期货行情，请稍后重试。",
                "error_type": "futures_unavailable",
            },
        ) from exc

    if not items_raw:
        raise HTTPException(
            status_code=503,
            detail={
                "title": "期货数据暂不可用",
                "message": "所有数据源均未能返回有效期货数据。",
                "error_type": "futures_empty",
            },
        )

    items = [FuturesQuote(**item) for item in items_raw]
    return FuturesListResponse(
        items=items,
        total=len(items),
        updated_at=datetime.now(TZ_SHANGHAI).isoformat(),
    )
