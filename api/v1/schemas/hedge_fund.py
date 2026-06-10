# -*- coding: utf-8 -*-
"""大师会诊 Schema"""

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class MasterSignal(BaseModel):
    name: str = Field(..., description="大师名称")
    signal: str = Field(..., description="bullish|bearish|neutral")
    confidence: int = Field(..., ge=0, le=100)
    reasoning: Optional[str] = Field(None, description="分析理由")


class AggregatedSignal(BaseModel):
    signal: str
    confidence: int
    bullish_count: int
    bearish_count: int
    neutral_count: int
    total_masters: int


class HedgeFundResponse(BaseModel):
    stock_code: str
    masters: Dict[str, MasterSignal]
    aggregated: AggregatedSignal
    generated_at: str
    analysis_time_ms: Optional[int] = None
