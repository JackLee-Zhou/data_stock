# -*- coding: utf-8 -*-
"""
CTP 行情适配器 — 基于官方 openctp-ctp 示例

参考: integrations/ctp.examples/openctp-ctp/SubscribeMarketData.py
"""

from __future__ import annotations
import logging, os, threading, time as _time
from datetime import datetime
from typing import Any, Dict, List, Optional

from openctp_ctp import mdapi
from data_provider.ctp_types import CtpQuote, CtpStatus, CtpTickData

logger = logging.getLogger(__name__)


class CtpMdAdapter(mdapi.CThostFtdcMdSpi):
    """CTP 行情适配器（继承 CThostFtdcMdSpi）"""
    _instance: Optional["CtpMdAdapter"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._init = False
        return cls._instance

    def __init__(self):
        if self._init: return
        mdapi.CThostFtdcMdSpi.__init__(self)
        self._api: Any = None
        self._status = CtpStatus()
        self._quotes: Dict[str, CtpQuote] = {}
        self._tick_buffer: List[dict] = []
        self._buffer_lock = threading.Lock()
        self._connected = False; self._logged_in = False
        self._stop = False; self._flusher: Optional[threading.Thread] = None
        self._login_event = threading.Event()
        self._init = True

    @property
    def status(self) -> CtpStatus: return self._status

    def connect(self, front: str, broker: str, user: str, pwd: str) -> bool:
        try:
            self._status.front_address = front
            self._broker, self._user, self._pwd = broker, user, pwd

            flow = f'/tmp/ctp_md_flow_{user}'
            os.makedirs(flow, exist_ok=True)
            self._api = mdapi.CThostFtdcMdApi.CreateFtdcMdApi(os.path.join(flow, user))
            self._api.RegisterFront(front)
            self._api.RegisterSpi(self)
            self._api.Init()
            logger.info("[CTP-MD] 连接中... %s", front)

            # 等待登录完成（OnFrontConnected → ReqUserLogin → OnRspUserLogin）
            if not self._login_event.wait(timeout=10):
                logger.error("[CTP-MD] 登录超时")
                return False

            self._status.connected = True; self._status.logged_in = True
            self._start_flusher()
            logger.info("[CTP-MD] 已连接, TradingDay=%s", self._status.trading_day)
            return True
        except Exception as e:
            logger.error("[CTP-MD] 连接失败: %s", e)
            self._status.last_error = str(e)
            return False

    def subscribe(self, codes: List[str]) -> int:
        if not self._api or not self._connected: return 0
        encoded = [c.encode('utf-8') for c in codes]
        ret = self._api.SubscribeMarketData(encoded, len(encoded))
        self._status.subscribed_count = len(codes)
        logger.info("[CTP-MD] 订阅 %d 合约, ret=%d", len(codes), ret)
        return len(codes) if ret == 0 else 0

    def get_quotes(self) -> dict:
        return {k: {
            "code": q.code, "price": q.price, "change_pct": q.change_pct,
            "bid1": q.bid1, "ask1": q.ask1, "volume": q.volume,
            "open_interest": q.open_interest,
            "high": q.high, "low": q.low, "open": q.open, "prev_close": q.prev_close,
            "updated_at": q.updated_at.isoformat() if q.updated_at else "",
        } for k, q in self._quotes.items()}

    def get_quote(self, code: str) -> Optional[dict]:
        q = self._quotes.get(code.upper())
        return {"code": q.code, "price": q.price, "bid1": q.bid1, "ask1": q.ask1} if q else None

    # ── CTP SPI Callbacks ──

    def OnFrontConnected(self):
        """连接成功 → 登录"""
        req = mdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self._broker; req.UserID = self._user; req.Password = self._pwd
        req.UserProductInfo = '@openctp'
        self._api.ReqUserLogin(req, 0)

    def OnFrontDisconnected(self, reason: int):
        self._connected = False; self._status.connected = False
        logger.warning("[CTP-MD] 断开: reason=%d", reason)

    def OnRspUserLogin(self, d, e, r, l):
        if e and e.ErrorID != 0:
            logger.error("[CTP-MD] 登录失败: %s", e.ErrorMsg)
            self._status.last_error = e.ErrorMsg
            return
        self._trading_day = d.TradingDay if d else ""
        self._status.trading_day = self._trading_day
        self._status.logged_in = True
        self._connected = True
        logger.info("[CTP-MD] 登录成功: Day=%s Front=%s Session=%s",
                     d.TradingDay, d.FrontID, d.SessionID)
        self._login_event.set()

    def OnRtnDepthMarketData(self, d):
        if not d: return
        code = d.InstrumentID; now = datetime.now()
        q = CtpQuote(code=code, price=d.LastPrice,
                     bid1=d.BidPrice1 if d.BidPrice1 > 0 else None,
                     ask1=d.AskPrice1 if d.AskPrice1 > 0 else None,
                     volume=d.Volume, open_interest=d.OpenInterest,
                     high=d.HighestPrice if d.HighestPrice > 0 else None,
                     low=d.LowestPrice if d.LowestPrice > 0 else None,
                     open=d.OpenPrice if d.OpenPrice > 0 else None,
                     prev_close=d.PreSettlementPrice if d.PreSettlementPrice > 0 else None,
                     updated_at=now)
        self._quotes[code] = q
        with self._buffer_lock:
            self._tick_buffer.append({"code": code, "trade_time": now, "price": d.LastPrice,
                                       "bid1": q.bid1, "ask1": q.ask1,
                                       "volume": d.Volume, "open_interest": d.OpenInterest})

    # ── Tick 刷盘 ──

    def _start_flusher(self):
        def _loop():
            while not self._stop:
                _time.sleep(2)
                with self._buffer_lock:
                    if not self._tick_buffer: continue
                    batch = self._tick_buffer; self._tick_buffer = []
                try:
                    from src.storage import DatabaseManager, CtpTick
                    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                    db = DatabaseManager()
                    with db.session_scope() as s:
                        for t in batch:
                            s.execute(sqlite_insert(CtpTick).values(**t).on_conflict_do_nothing())
                except Exception: pass
        self._stop = False
        self._flusher = threading.Thread(target=_loop, daemon=True); self._flusher.start()

    def close(self):
        self._stop = True
        if self._api: self._api.Release()
