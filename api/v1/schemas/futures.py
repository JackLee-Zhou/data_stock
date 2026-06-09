# -*- coding: utf-8 -*-
"""
期货行情 Schema
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class FuturesQuote(BaseModel):
    """单个期货合约行情"""
    contract_code: str = Field(..., description="合约代码", json_schema_extra={"example": "A2501"})
    contract_name: str = Field(..., description="合约名称", json_schema_extra={"example": "沪铝2501"})
    last_price: float = Field(..., description="最新价")
    change: float = Field(..., description="涨跌额")
    change_pct: float = Field(..., description="涨跌幅(%)")
    volume: int = Field(0, description="成交量(手)")
    open_interest: int = Field(0, description="持仓量(手)")
    high: Optional[float] = Field(None, description="最高价")
    low: Optional[float] = Field(None, description="最低价")
    open: Optional[float] = Field(None, description="开盘价")
    prev_close: Optional[float] = Field(None, description="前收盘价")

    class Config:
        from_attributes = True


class FuturesListResponse(BaseModel):
    """期货行情列表响应"""
    items: List[FuturesQuote] = Field(..., description="期货合约列表")
    total: int = Field(..., description="总数")
    updated_at: str = Field(..., description="更新时间(ISO 8601)")
