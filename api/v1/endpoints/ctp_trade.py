# -*- coding: utf-8 -*-
"""CTP 交易 API"""

import logging, os
from fastapi import APIRouter, HTTPException, Query
from data_provider.ctp_td_adapter import CtpTdAdapter

logger = logging.getLogger(__name__)
router = APIRouter()


def _get_td():
    adapter = CtpTdAdapter()
    if not adapter._connected:
        broker = os.getenv("CTP_BROKER_ID", "9999")
        user = os.getenv("CTP_USER_ID", "")
        pwd = os.getenv("CTP_PASSWORD", "")
        front = os.getenv("CTP_TRADE_FRONT", "tcp://182.254.243.31:30001")
        if not user or not pwd:
            raise HTTPException(503, detail="CTP 账号未配置")
        adapter.connect(front, broker, user, pwd)
    return adapter, os.getenv("CTP_BROKER_ID", "9999"), os.getenv("CTP_USER_ID", "")


@router.get("/account", summary="账户资金")
def ctp_account():
    td, _, _ = _get_td()
    a = td.get_account()
    return {"available": a.available, "balance": a.balance, "frozen": a.frozen, "today_profit": a.today_profit}


@router.get("/positions", summary="当前持仓")
def ctp_positions():
    td, _, _ = _get_td()
    return [{"code": p.code, "direction": p.direction, "volume": p.volume,
             "avg_price": p.avg_price, "today_profit": p.today_profit} for p in td.get_positions()]


@router.get("/orders", summary="今日订单")
def ctp_orders():
    td, _, _ = _get_td()
    return [{"order_ref": o.order_ref, "code": o.code, "direction": o.direction,
             "price": o.price, "volume": o.volume, "status": o.status,
             "order_time": o.order_time} for o in td.get_orders()]


@router.post("/order", summary="下单")
def ctp_place_order(
    code: str = Query(...), direction: str = Query(...),  # buy/sell
    price: float = Query(...), volume: int = Query(...)):
    td, broker, user = _get_td()
    ref = td.place_order(code, direction, price, volume, broker, user)
    if not ref:
        raise HTTPException(500, detail="下单失败")
    return {"order_ref": ref}


@router.delete("/order", summary="撤单")
def ctp_cancel(order_ref: str = Query(...)):
    td, broker, user = _get_td()
    ok = td.cancel_order(order_ref, broker, user)
    return {"success": ok}
