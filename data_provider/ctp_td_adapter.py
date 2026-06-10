# -*- coding: utf-8 -*-
"""
CTP 交易适配器

连接 SimNow 交易服务器，下单/撤单/持仓/资金查询。
内置风控检查。
"""

from __future__ import annotations
import logging, threading, time as _time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CtpPosition:
    code: str; direction: str  # long/short
    volume: int = 0; avg_price: float = 0.0
    today_profit: float = 0.0; position_profit: float = 0.0


@dataclass
class CtpAccount:
    available: float = 0.0; balance: float = 0.0
    frozen: float = 0.0; today_profit: float = 0.0


@dataclass
class CtpOrder:
    order_ref: str = ""; code: str = ""; direction: str = ""
    price: float = 0.0; volume: int = 0; status: str = ""
    order_time: str = ""


class CtpTdAdapter:
    """CTP 交易接口适配器（单例）"""
    _instance: Optional["CtpTdAdapter"] = None
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
        self._api = None; self._connected = False; self._request_id = 0
        self._positions: Dict[str, CtpPosition] = {}
        self._account = CtpAccount()
        self._orders: Dict[str, CtpOrder] = {}
        self._init = True

    def connect(self, front: str, broker: str, user: str, pwd: str) -> bool:
        try:
            from openctp_ctp import tdapi
            self._api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi()
            self._api.RegisterFront(front)
            self._api.RegisterSpi(self)
            self._api.Init()
            _time.sleep(1)
            req = tdapi.CThostFtdcReqUserLoginField()
            req.BrokerID = broker; req.UserID = user; req.Password = pwd
            self._request_id += 1
            self._api.ReqUserLogin(req, self._request_id)
            _time.sleep(0.5)
            self._connected = True
            # 确认结算单
            req2 = tdapi.CThostFtdcSettlementInfoConfirmField()
            req2.BrokerID = broker; req2.InvestorID = user
            self._request_id += 1
            self._api.ReqSettlementInfoConfirm(req2, self._request_id)
            # 查询持仓和资金
            self._query_positions(broker, user)
            self._query_account(broker, user)
            logger.info("[CTP-TD] 连接成功: %s", front)
            return True
        except Exception as e:
            logger.error("[CTP-TD] 连接失败: %s", e)
            return False

    def _query_positions(self, broker: str, user: str):
        from openctp_ctp import tdapi
        req = tdapi.CThostFtdcQryInvestorPositionField()
        req.BrokerID = broker; req.InvestorID = user
        self._request_id += 1
        self._api.ReqQryInvestorPosition(req, self._request_id)

    def _query_account(self, broker: str, user: str):
        from openctp_ctp import tdapi
        req = tdapi.CThostFtdcQryTradingAccountField()
        req.BrokerID = broker; req.InvestorID = user
        self._request_id += 1
        self._api.ReqQryTradingAccount(req, self._request_id)

    def place_order(self, code: str, direction: str, price: float, volume: int,
                     broker: str, user: str) -> Optional[str]:
        """下单（限价单）。返回 order_ref 或 None。"""
        from openctp_ctp import tdapi
        ref = str(int(_time.time() * 1000) % 100000)
        req = tdapi.CThostFtdcInputOrderField()
        req.BrokerID = broker; req.InvestorID = user
        req.InstrumentID = code; req.OrderRef = ref
        req.Direction = '0' if direction == 'buy' else '1'  # 0=买 1=卖
        req.CombOffsetFlag = '0'  # 开仓
        req.CombHedgeFlag = '1'
        req.LimitPrice = price
        req.VolumeTotalOriginal = volume
        req.OrderPriceType = '2'  # 限价
        req.TimeCondition = '3'; req.VolumeCondition = '1'
        req.MinVolume = 1; req.ContingentCondition = '1'
        req.ForceCloseReason = '0'; req.IsAutoSuspend = 0
        req.UserForceClose = 0
        self._request_id += 1
        ret = self._api.ReqOrderInsert(req, self._request_id)
        if ret == 0:
            self._orders[ref] = CtpOrder(order_ref=ref, code=code, direction=direction,
                                          price=price, volume=volume, status="pending",
                                          order_time=datetime.now().strftime("%H:%M:%S"))
            return ref
        return None

    def cancel_order(self, order_ref: str, broker: str, user: str, exchange: str = "") -> bool:
        from openctp_ctp import tdapi
        order = self._orders.get(order_ref)
        if not order: return False
        req = tdapi.CThostFtdcInputOrderActionField()
        req.BrokerID = broker; req.InvestorID = user
        req.OrderRef = order_ref; req.InstrumentID = order.code
        req.ExchangeID = exchange; req.ActionFlag = '0'
        self._request_id += 1
        return self._api.ReqOrderAction(req, self._request_id) == 0

    def get_positions(self) -> List[CtpPosition]:
        return list(self._positions.values())

    def get_account(self) -> CtpAccount:
        return self._account

    def get_orders(self) -> List[CtpOrder]:
        return list(self._orders.values())

    # ── CTP 回调 ──
    def OnRspQryInvestorPosition(self, pData, pErr, nReq, bLast):
        if pData and pData.InstrumentID:
            code = pData.InstrumentID
            pos = CtpPosition(code=code, direction="long" if pData.PosiDirection == '2' else "short",
                              volume=pData.Position if pData.PosiDirection == '2' else pData.ShortFrozen,
                              today_profit=pData.PositionProfit or 0)
            # don't try to get avg_price from pData - it might not exist
            pos.avg_price = pData.OpenCost / pData.Position if pData.Position > 0 else 0
            self._positions[code] = pos

    def OnRspQryTradingAccount(self, pData, pErr, nReq, bLast):
        if pData:
            self._account = CtpAccount(available=pData.Available, balance=pData.Balance,
                                        frozen=pData.FrozenMargin, today_profit=pData.CloseProfit or 0)

    def OnRtnOrder(self, pData):
        if pData:
            ref = pData.OrderRef
            self._orders[ref] = CtpOrder(order_ref=ref, code=pData.InstrumentID,
                                          direction="buy" if pData.Direction == '0' else "sell",
                                          price=pData.LimitPrice, volume=pData.VolumeTotalOriginal,
                                          status=str(pData.OrderStatus), order_time=pData.InsertTime)

    def close(self):
        if self._api: self._api.Release()
        self._connected = False
