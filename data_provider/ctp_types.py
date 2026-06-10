# -*- coding: utf-8 -*-
"""CTP 行情数据结构"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class CtpTickData:
    code: str
    trade_time: datetime
    price: float = 0.0
    bid1: Optional[float] = None
    ask1: Optional[float] = None
    volume: float = 0.0
    open_interest: float = 0.0


@dataclass
class CtpQuote:
    """内存缓存行情快照"""
    code: str
    name: str = ""
    price: float = 0.0
    change_pct: float = 0.0
    bid1: Optional[float] = None
    ask1: Optional[float] = None
    volume: float = 0.0
    open_interest: float = 0.0
    high: Optional[float] = None
    low: Optional[float] = None
    open: Optional[float] = None
    prev_close: Optional[float] = None
    updated_at: datetime = field(default_factory=datetime.now)


@dataclass
class CtpStatus:
    connected: bool = False
    logged_in: bool = False
    front_address: str = ""
    trading_day: str = ""
    last_error: str = ""
    subscribed_count: int = 0
