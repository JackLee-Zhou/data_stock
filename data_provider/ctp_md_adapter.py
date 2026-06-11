# -*- coding: utf-8 -*-
"""
CTP 行情适配器 — TD ReqQryDepthMarketData 轮询模式

新 SimNow (182.254.243.31) 的 MD SubscribeMarketData 无回调，
行情必须通过 TD API 的 ReqQryDepthMarketData 主动查询。

基于官方示例: integrations/ctp.examples/openctp-ctp/ReqQryDepthMarketData.py
"""

from __future__ import annotations
import logging, os, threading, time as _time
from datetime import datetime
from typing import Any, Dict, List, Optional

from openctp_ctp import tdapi
from data_provider.ctp_types import CtpQuote, CtpStatus

logger = logging.getLogger(__name__)


class CtpMdAdapter(tdapi.CThostFtdcTraderSpi):
    """CTP 行情适配器（基于 TD API 轮询行情）"""
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
        tdapi.CThostFtdcTraderSpi.__init__(self)
        self._api: Any = None
        self._status = CtpStatus()
        self._quotes: Dict[str, CtpQuote] = {}
        self._connected = self._logged_in = False
        self._stop = False
        self._login_event = threading.Event()
        self._quote_event = threading.Event()
        self._init = True

    @property
    def status(self) -> CtpStatus: return self._status

    def connect(self, front: str, broker: str, user: str, pwd: str) -> bool:
        try:
            self._status.front_address = front
            self._broker, self._user, self._pwd = broker, user, pwd

            flow = f'/tmp/ctp_td_flow_{user}'
            os.makedirs(flow, exist_ok=True)
            self._api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi(os.path.join(flow, user))
            self._api.RegisterFront(front)
            self._api.RegisterSpi(self)
            self._api.Init()
            logger.info("[CTP-TD] 连接中... %s", front)

            if not self._login_event.wait(timeout=10):
                logger.error("[CTP-TD] 登录超时")
                return False

            self._status.connected = True; self._status.logged_in = True
            logger.info("[CTP-TD] 已连接, Day=%s", self._status.trading_day)
            # 延时后首次查询（让 settlement confirm 完成）
            threading.Timer(2.0, self._query_quotes).start()
            self._start_poller()
            return True
        except Exception as e:
            logger.error("[CTP-TD] 连接失败: %s", e)
            self._status.last_error = str(e)
            return False

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
        if not q: return None
        return {"code": q.code, "price": q.price, "bid1": q.bid1, "ask1": q.ask1}

    # ── TD SPI Callbacks ──

    def OnFrontConnected(self):
        auth = tdapi.CThostFtdcReqAuthenticateField()
        auth.BrokerID = self._broker; auth.UserID = self._user
        auth.AppID = 'simnow_client_test'; auth.AuthCode = '0000000000000000'; auth.UserProductInfo = '@openctp'
        self._api.ReqAuthenticate(auth, 0)

    def OnRspAuthenticate(self, d, e, r, l):
        if e and e.ErrorID != 0:
            logger.error("[CTP-TD] 认证失败: %s", e.ErrorMsg)
            self._status.last_error = e.ErrorMsg; return
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = self._broker; req.UserID = self._user; req.Password = self._pwd; req.UserProductInfo = '@openctp'
        self._api.ReqUserLogin(req, 0, 0, "")

    def OnRspUserLogin(self, d, e, r, l):
        if e and e.ErrorID != 0:
            logger.error("[CTP-TD] 登录失败: %s", e.ErrorMsg)
            self._status.last_error = e.ErrorMsg; return
        self._trading_day = d.TradingDay if d else ""
        self._status.trading_day = self._trading_day
        self._status.logged_in = True; self._connected = True
        logger.info("[CTP-TD] 登录成功: Day=%s Front=%s Session=%s", d.TradingDay, d.FrontID, d.SessionID)
        # 确认结算单
        req = tdapi.CThostFtdcSettlementInfoConfirmField()
        req.BrokerID = self._broker; req.InvestorID = self._user
        self._api.ReqSettlementInfoConfirm(req, 0)
        self._login_event.set()

    def OnRspSettlementInfoConfirm(self, d, e, r, l):
        if e and e.ErrorID:
            logger.warning("[CTP-TD] 结算确认失败: %s", e.ErrorMsg)
        # 首次查询行情
        self._query_quotes()

    def OnRspQryDepthMarketData(self, d, e, r, l):
        if l:
            logger.info("[CTP-TD] 行情查询完成: %d 条", len(self._quotes))
            self._status.subscribed_count = len(self._quotes)
        if d and d.InstrumentID and d.LastPrice and d.LastPrice > 0:
            code = d.InstrumentID
            self._quotes[code] = CtpQuote(
                code=code, price=d.LastPrice,
                bid1=d.BidPrice1 if d.BidPrice1 > 0 and d.BidPrice1 < 1e100 else None,
                ask1=d.AskPrice1 if d.AskPrice1 > 0 and d.AskPrice1 < 1e100 else None,
                volume=d.Volume, open_interest=d.OpenInterest,
                high=d.HighestPrice if d.HighestPrice > 0 else None,
                low=d.LowestPrice if d.LowestPrice > 0 else None,
                open=d.OpenPrice if d.OpenPrice > 0 else None,
                prev_close=d.PreSettlementPrice if d.PreSettlementPrice > 0 else None,
                updated_at=datetime.now(),
            )
        if l:
            self._status.subscribed_count = len(self._quotes)
            self._quote_event.set()

    # ── 轮询 ──

    def _query_quotes(self):
        if not self._api or not self._connected: return
        logger.info("[CTP-TD] 查询行情...")
        req = tdapi.CThostFtdcQryDepthMarketDataField()
        self._api.ReqQryDepthMarketData(req, 0)

    def _start_poller(self):
        def _loop():
            while not self._stop:
                _time.sleep(3)
                self._query_quotes()
        t = threading.Thread(target=_loop, daemon=True); t.start()

    def close(self):
        self._stop = True
        if self._api: self._api.Release()
