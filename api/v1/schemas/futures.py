# -*- coding: utf-8 -*-
"""期货行情 Schema"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FuturesQuote(BaseModel):
    contract_code: str = Field(..., description="合约代码")
    contract_name: str = Field(..., description="合约名称")
    last_price: float = Field(..., description="最新价")
    change: float = Field(0.0, description="涨跌额")
    change_pct: float = Field(0.0, description="涨跌幅(%)")
    volume: int = Field(0, description="成交量")
    open_interest: int = Field(0, description="持仓量")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    open: Optional[float] = Field(None, description="开盘价")
    prev_close: Optional[float] = Field(None, description="昨收价")
    market: str = Field("international", description="domestic/international")


class FuturesListResponse(BaseModel):
    items: List[FuturesQuote]
    total: int
    updated_at: str


class KlineItem(BaseModel):
    trade_date: str; open: float; high: float; low: float; close: float
    volume: float = 0.0; open_interest: float = 0.0


class FuturesKlineResponse(BaseModel):
    code: str
    klines: List[KlineItem] = []
    from_cache: bool = True
