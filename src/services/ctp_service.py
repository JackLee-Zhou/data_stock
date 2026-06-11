# -*- coding: utf-8 -*-
"""CTP 服务 — TD 连接 → 查期货列表 → 轮询行情"""
import logging, os, threading, time as _time
from datetime import datetime
from typing import Optional

logger = logging.getLogger(__name__)

_quotes_cache: dict = {}
_futures_list: list = []  # [(code, name), ...]
_cache_lock = threading.Lock()
_ctp_started = False


def start_ctp():
    global _ctp_started
    if _ctp_started: return {"ok": True}

    front = os.getenv("CTP_TRADE_FRONT", "tcp://182.254.243.31:30002")
    user = os.getenv("CTP_USER_ID", ""); pwd = os.getenv("CTP_PASSWORD", "")
    if not user or not pwd:
        logger.warning("[CTP] 未配置账号"); return {"ok": False}

    from openctp_ctp import tdapi

    class Spi(tdapi.CThostFtdcTraderSpi):
        def __init__(s):
            tdapi.CThostFtdcTraderSpi.__init__(s)
            s._futures = {}; s._prices = {}; s._login = threading.Event()
        def OnFrontConnected(s):
            auth = tdapi.CThostFtdcReqAuthenticateField()
            auth.BrokerID = '9999'; auth.UserID = user; auth.AppID = 'simnow_client_test'
            auth.AuthCode = '0000000000000000'; auth.UserProductInfo = '@openctp'
            s.api.ReqAuthenticate(auth, 0)
        def OnRspAuthenticate(s, d, e, r, l):
            req = tdapi.CThostFtdcReqUserLoginField()
            req.BrokerID = '9999'; req.UserID = user; req.Password = pwd; req.UserProductInfo = '@openctp'
            s.api.ReqUserLogin(req, 0, 0, "")
        def OnRspUserLogin(s, d, e, r, l):
            logger.info("[CTP] Login OK: Day=%s", d.TradingDay)
            # 查所有期货合约
            for ex in ['SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'GFEX']:
                q = tdapi.CThostFtdcQryInstrumentField(); q.ExchangeID = ex
                s.api.ReqQryInstrument(q, 0)
        def OnRspQryInstrument(s, d, e, r, l):
            if d and d.InstrumentID and d.ProductClass == '1':
                s._futures[d.InstrumentID] = d.InstrumentName
            if l:
                global _futures_list
                _futures_list = [(c, n) for c, n in s._futures.items()]
                logger.info("[CTP] 期货合约: %d 个", len(_futures_list))
                s._login.set()
                # 开始轮询行情
                def _poll():
                    while True:
                        _time.sleep(2)
                        for ex in ['SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'GFEX']:
                            q = tdapi.CThostFtdcQryDepthMarketDataField()
                            q.ExchangeID = ex; s.api.ReqQryDepthMarketData(q, 0)
                threading.Thread(target=_poll, daemon=True).start()
        def OnRspQryDepthMarketData(s, d, e, r, l):
            if d and d.InstrumentID and d.LastPrice > 0 and d.InstrumentID in s._futures:
                with _cache_lock:
                    # 五档盘口
                    def _safe_bid_ask(price, volume):
                        p = price if (price and 0 < price < 1e100) else None
                        v = volume if (volume and volume > 0) else 0
                        return p, v
                    # 存 tick 到 DB（异步，不阻塞）
                    try:
                        from src.storage import DatabaseManager, CtpTick as CtpTickModel
                        from sqlalchemy.dialects.sqlite import insert as sqlite_insert
                        db = DatabaseManager()
                        with db.session_scope() as sess:
                            sess.execute(sqlite_insert(CtpTickModel).values(
                                code=d.InstrumentID, trade_time=datetime.now(),
                                price=d.LastPrice,
                                bid1=d.BidPrice1 if 0 < d.BidPrice1 < 1e100 else None,
                                ask1=d.AskPrice1 if 0 < d.AskPrice1 < 1e100 else None,
                                volume=d.Volume, open_interest=d.OpenInterest,
                            ).on_conflict_do_nothing())
                    except Exception: pass

                    _quotes_cache[d.InstrumentID] = {
                        "code": d.InstrumentID,
                        "name": s._futures.get(d.InstrumentID, d.InstrumentID),
                        "price": d.LastPrice,
                        "volume": d.Volume, "open_interest": d.OpenInterest,
                        "high": d.HighestPrice if d.HighestPrice > 0 else None,
                        "low": d.LowestPrice if d.LowestPrice > 0 else None,
                        "open": d.OpenPrice if d.OpenPrice > 0 else None,
                        "prev_close": d.PreSettlementPrice if d.PreSettlementPrice > 0 else None,
                        "depth": [
                            {"bp": _safe_bid_ask(d.BidPrice1, d.BidVolume1)[0],
                             "bv": _safe_bid_ask(d.BidPrice1, d.BidVolume1)[1],
                             "ap": _safe_bid_ask(d.AskPrice1, d.AskVolume1)[0],
                             "av": _safe_bid_ask(d.AskPrice1, d.AskVolume1)[1]},
                            {"bp": _safe_bid_ask(d.BidPrice2, d.BidVolume2)[0],
                             "bv": _safe_bid_ask(d.BidPrice2, d.BidVolume2)[1],
                             "ap": _safe_bid_ask(d.AskPrice2, d.AskVolume2)[0],
                             "av": _safe_bid_ask(d.AskPrice2, d.AskVolume2)[1]},
                            {"bp": _safe_bid_ask(d.BidPrice3, d.BidVolume3)[0],
                             "bv": _safe_bid_ask(d.BidPrice3, d.BidVolume3)[1],
                             "ap": _safe_bid_ask(d.AskPrice3, d.AskVolume3)[0],
                             "av": _safe_bid_ask(d.AskPrice3, d.AskVolume3)[1]},
                            {"bp": _safe_bid_ask(d.BidPrice4, d.BidVolume4)[0],
                             "bv": _safe_bid_ask(d.BidPrice4, d.BidVolume4)[1],
                             "ap": _safe_bid_ask(d.AskPrice4, d.AskVolume4)[0],
                             "av": _safe_bid_ask(d.AskPrice4, d.AskVolume4)[1]},
                            {"bp": _safe_bid_ask(d.BidPrice5, d.BidVolume5)[0],
                             "bv": _safe_bid_ask(d.BidPrice5, d.BidVolume5)[1],
                             "ap": _safe_bid_ask(d.AskPrice5, d.AskVolume5)[0],
                             "av": _safe_bid_ask(d.AskPrice5, d.AskVolume5)[1]},
                        ],
                    }

    flow = f'/tmp/ctp_g2_{user}'; os.makedirs(flow, exist_ok=True)
    spi = Spi()
    api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi(os.path.join(flow, user))
    spi.api = api; api.RegisterFront(front); api.RegisterSpi(spi); api.Init()

    if not spi._login.wait(timeout=20):
        logger.error("[CTP] 期货列表查询超时"); return {"ok": False}

    _ctp_started = True
    logger.info("[CTP] 就绪: %d 期货 + 行情轮询", len(_futures_list))
    return {"ok": True, "futures": len(_futures_list)}


def get_quotes() -> dict:
    with _cache_lock: return dict(_quotes_cache)


def get_futures_list() -> list:
    return list(_futures_list)


def get_status() -> dict:
    with _cache_lock:
        return {"connected": _ctp_started, "futures": len(_futures_list), "quotes": len(_quotes_cache)}
