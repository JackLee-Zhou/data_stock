# -*- coding: utf-8 -*-
"""
大师会诊接口

POST /api/v1/hedge-fund/analyze — 13 位投资大师并行分析个股
"""

import logging

from fastapi import APIRouter, HTTPException

from api.v1.schemas.hedge_fund import (
    AggregatedSignal, HedgeFundResponse, MasterSignal,
)
from src.services.hedge_fund_service import HedgeFundService

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/analyze",
    response_model=HedgeFundResponse,
    responses={
        200: {"description": "大师会诊结果"},
        404: {"description": "股票数据不存在"},
        503: {"description": "LLM 不可用"},
    },
    summary="大师会诊：多投资大师视角分析个股",
    description="13 位投资大师（巴菲特、格雷厄姆、芒格等）基于同一份股票数据，"
    "各自按照投资哲学给出买入/持有/卖出信号，最终聚合为综合判断。",
)
def analyze_hedge_fund(stock_code: str) -> HedgeFundResponse:
    service = HedgeFundService()
    try:
        result = service.analyze(stock_code)
    except RuntimeError as exc:
        raise HTTPException(503, detail={"title": "LLM 未配置", "message": str(exc)}) from exc

    if result is None:
        raise HTTPException(404, detail={
            "title": "无数据", "message": f"未找到 {stock_code} 的分析数据"
        })

    return HedgeFundResponse(
        stock_code=result["stock_code"],
        masters={k: MasterSignal(**v) for k, v in result["masters"].items()},
        aggregated=AggregatedSignal(**result["aggregated"]),
        generated_at=result["generated_at"],
        analysis_time_ms=result.get("analysis_time_ms"),
    )
