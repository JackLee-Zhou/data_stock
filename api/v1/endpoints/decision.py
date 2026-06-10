# -*- coding: utf-8 -*-
"""AI 决策引擎 API"""

import logging
from fastapi import APIRouter, Query

from src.services.trading_decision_engine import run_decision_cycle

logger = logging.getLogger(__name__)
router = APIRouter()


@router.post("/analyze", summary="触发 AI 决策周期")
def trigger_decision(
    market: str = Query("futures", description="futures/stock"),
    code: str = Query(..., description="合约/股票代码"),
):
    result = run_decision_cycle(market, code)
    return result if result else {"error": "决策失败"}
