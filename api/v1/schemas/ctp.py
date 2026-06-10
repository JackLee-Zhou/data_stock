# -*- coding: utf-8 -*-
"""CTP Schema"""

from typing import Dict, List, Optional
from pydantic import BaseModel, Field


class CtpQuoteResponse(BaseModel):
    quotes: Dict[str, dict] = Field(default_factory=dict)
    count: int = 0


class CtpStatusResponse(BaseModel):
    connected: bool; logged_in: bool
    front_address: str = ""
    trading_day: str = ""
    subscribed_count: int = 0
    last_error: str = ""
