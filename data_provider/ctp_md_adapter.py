# -*- coding: utf-8 -*-
"""
CTP 行情适配器

连接 SimNow 行情服务器，订阅自选合约，每 500ms 接收深度行情推送。
数据写入内存缓存（前端实时展示）+ CtpTick 表（持久化）。

基于 openctp-ctp (CTPAPI Python binding)
"""

from __future__ import annotations

import logging
import threading
import time as _time
from datetime import datetime
from typing import Any, Dict, List, Optional

from data_provider.ctp_types import CtpQuote, CtpStatus, CtpTickData

logger = logging.getLogger(__name__)


class CtpMdAdapter:
    """CTP 行情接口适配器（单例）"""

    _instance: Optional["CtpMdAdapter"] = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = super().__new__(cls)
                    cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._api = None
        self._status = CtpStatus()
        self._quotes: Dict[str, CtpQuote] = {}
        self._tick_buffer: List[CtpTickData] = []
        self._buffer_lock = threading.Lock()
        self._request_id = 0
        self._connected = False
        self._initialized = True
        self._flusher_thread: Optional[threading.Thread] = None
        self._stop_flusher = False

    @property
    def status(self) -> CtpStatus:
        return self._status

    def connect(self, front_addr: str, broker_id: str, user_id: str, password: str) -> bool:
        """连接行情服务器并登录。"""
        try:
            from openctp_ctp import mdapi

            self._api = mdapi.CThostFtdcMdApi.CreateFtdcMdApi()
            self._status.front_address = front_addr

            # 注册回调
            self._api.RegisterFront(front_addr)
            self._api.RegisterSpi(self)

            self._api.Init()
            _time.sleep(1)

            # 登录
            req = mdapi.CThostFtdcReqUserLoginField()
            req.BrokerID = broker_id
            req.UserID = user_id
            req.Password = password
            self._request_id += 1
            ret = self._api.ReqUserLogin(req, self._request_id)
            if ret != 0:
                logger.error("[CTP-MD] 登录请求失败: ret=%d", ret)
                return False

            _time.sleep(0.5)
            self._connected = True
            self._status.connected = True
            self._status.logged_in = True

            # 启动 tick 刷盘线程
            self._start_flusher()
            logger.info("[CTP-MD] 连接成功: %s", front_addr)
            return True
        except Exception as exc:
            logger.error("[CTP-MD] 连接失败: %s", exc)
            self._status.last_error = str(exc)
            return False

    def subscribe(self, codes: List[str]) -> int:
        """订阅合约行情。返回成功订阅数。"""
        if not self._api or not self._connected:
            return 0
        subscribed = 0
        for code in codes:
            ret = self._api.SubscribeMarketData([code.encode()])
            if ret == 0:
                subscribed += 1
        self._status.subscribed_count = subscribed
        logger.info("[CTP-MD] 订阅合约: %d/%d", subscribed, len(codes))
        return subscribed

    def get_quotes(self) -> Dict[str, CtpQuote]:
        """获取当前所有行情快照（供前端轮询）。"""
        return dict(self._quotes)

    def get_quote(self, code: str) -> Optional[CtpQuote]:
        return self._quotes.get(code.upper())

    # ── CTP 回调（由 CTP 线程调用）──

    def OnFrontConnected(self):
        logger.info("[CTP-MD] 行情前置连接成功")
        self._status.connected = True

    def OnFrontDisconnected(self, reason: int):
        logger.warning("[CTP-MD] 行情前置断开: reason=%d", reason)
        self._status.connected = False

    def OnRspUserLogin(self, pRsp, pErr, nRequestID, bIsLast):
        if pErr is not None and pErr.ErrorID != 0:
            logger.error("[CTP-MD] 登录失败: %s", pErr.ErrorMsg)
            self._status.last_error = pErr.ErrorMsg
        else:
            logger.info("[CTP-MD] 登录成功: %s", pRsp.TradingDay if pRsp else "?")
            self._status.logged_in = True
            if pRsp:
                self._status.trading_day = pRsp.TradingDay

    def OnRtnDepthMarketData(self, pData):
        """行情推送回调（每 500ms）"""
        if not pData:
            return
        code = pData.InstrumentID
        now = datetime.now()
        quote = CtpQuote(
            code=code,
            price=pData.LastPrice,
            bid1=pData.BidPrice1 if pData.BidPrice1 > 0 else None,
            ask1=pData.AskPrice1 if pData.AskPrice1 > 0 else None,
            volume=pData.Volume,
            open_interest=pData.OpenInterest,
            high=pData.HighestPrice if pData.HighestPrice > 0 else None,
            low=pData.LowestPrice if pData.LowestPrice > 0 else None,
            open=pData.OpenPrice if pData.OpenPrice > 0 else None,
            prev_close=pData.PreSettlementPrice if pData.PreSettlementPrice > 0 else None,
            updated_at=now,
        )
        self._quotes[code] = quote

        # 写入 tick 缓冲（异步刷盘）
        with self._buffer_lock:
            self._tick_buffer.append(CtpTickData(
                code=code, trade_time=now,
                price=pData.LastPrice,
                bid1=quote.bid1, ask1=quote.ask1,
                volume=pData.Volume, open_interest=pData.OpenInterest,
            ))

    def _start_flusher(self):
        """启动后台刷盘线程（每 2 秒批量写入 DB）"""
        def _flush_loop():
            while not self._stop_flusher:
                _time.sleep(2)
                with self._buffer_lock:
                    if not self._tick_buffer:
                        continue
                    batch = self._tick_buffer
                    self._tick_buffer = []
                try:
                    from src.storage import DatabaseManager
                    db = DatabaseManager()
                    from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                    from src.storage import CtpTick as CtpTickModel
                    with db.session_scope() as s:
                        for t in batch:
                            s.execute(sqlite_insert(CtpTickModel).values(
                                code=t.code, trade_time=t.trade_time,
                                price=t.price, bid1=t.bid1, ask1=t.ask1,
                                volume=t.volume, open_interest=t.open_interest,
                            ).on_conflict_do_nothing())
                except Exception:
                    pass

        self._stop_flusher = False
        self._flusher_thread = threading.Thread(target=_flush_loop, daemon=True)
        self._flusher_thread.start()

    def close(self):
        self._stop_flusher = True
        if self._api:
            self._api.Release()
        self._connected = False
        self._status.connected = False
