# -*- coding: utf-8 -*-
"""CTP 统一服务 — TD ReqQryDepthMarketData 轮询行情"""
import logging, os, threading, time as _time
from typing import Optional

from data_provider.ctp_md_adapter import CtpMdAdapter
from data_provider.ctp_types import CtpStatus

logger = logging.getLogger(__name__)

# 模块级行情缓存（解决 singleton 跨线程丢失问题）
_quotes_cache: dict = {}
_cache_lock = threading.Lock()
_ctp_started = False


def start_ctp() -> CtpStatus:
    global _ctp_started
    if _ctp_started: return CtpMdAdapter().status

    front = os.getenv("CTP_TRADE_FRONT", "tcp://182.254.243.31:30001")
    user = os.getenv("CTP_USER_ID", ""); pwd = os.getenv("CTP_PASSWORD", "")
    if not user or not pwd:
        logger.warning("[CTP] 未配置账号")
        return CtpStatus(connected=False, last_error="未配置")

    adapter = CtpMdAdapter()
    ok = adapter.connect(front, "9999", user, pwd)
    if not ok: return adapter.status

    _ctp_started = True
    # 启动轮询线程，数据写入 _quotes_cache
    _start_poller(adapter)
    return adapter.status


def _start_poller(adapter: CtpMdAdapter):
    def _poll():
        from openctp_ctp import tdapi
        while True:
            _time.sleep(2)
            req = tdapi.CThostFtdcQryDepthMarketDataField()
            adapter._api.ReqQryDepthMarketData(req, 0)

    # 替换适配器的回调，写入缓存
    import types
    orig = adapter.OnRspQryDepthMarketData

    def _on_data(self, d, e, r, l):
        if d and d.InstrumentID and d.LastPrice > 0:
            code = d.InstrumentID
            with _cache_lock:
                _quotes_cache[code] = {
                    "code": code, "price": d.LastPrice,
                    "bid1": d.BidPrice1 if 0 < d.BidPrice1 < 1e100 else None,
                    "ask1": d.AskPrice1 if 0 < d.AskPrice1 < 1e100 else None,
                    "volume": d.Volume, "open_interest": d.OpenInterest,
                    "high": d.HighestPrice if d.HighestPrice > 0 else None,
                    "low": d.LowestPrice if d.LowestPrice > 0 else None,
                    "open": d.OpenPrice if d.OpenPrice > 0 else None,
                    "prev_close": d.PreSettlementPrice if d.PreSettlementPrice > 0 else None,
                }
        orig(d, e, r, l)

    adapter.OnRspQryDepthMarketData = types.MethodType(_on_data, adapter)
    t = threading.Thread(target=_poll, daemon=True); t.start()


def get_quotes() -> dict:
    with _cache_lock: return dict(_quotes_cache)


def get_status() -> CtpStatus:
    return CtpMdAdapter().status
