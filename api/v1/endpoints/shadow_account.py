# -*- coding: utf-8 -*-
"""
模拟交易（Shadow Account）接口

复用 portfolio_* 表，通过 paper 市场区分真实/模拟。
"""

import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from src.storage import DatabaseManager

logger = logging.getLogger(__name__)
router = APIRouter()

SHADOW_MARKET = "paper"


def _get_shadow_account():
    """获取或创建默认模拟账户。"""
    db = DatabaseManager()
    with db.session_scope() as s:
        from src.storage import PortfolioAccount
        acct = s.query(PortfolioAccount).filter(
            PortfolioAccount.market == SHADOW_MARKET,
            PortfolioAccount.is_active == True,  # noqa: E712
        ).first()
        if not acct:
            acct = PortfolioAccount(
                owner_id="default",
                name="模拟账户",
                market=SHADOW_MARKET,
                base_currency="CNY",
                is_active=True,
            )
            s.add(acct)
            s.flush()
            # 注入初始资金 100 万
            from src.storage import PortfolioCashLedger
            s.add(PortfolioCashLedger(
                account_id=acct.id,
                event_date=date.today(),
                direction="deposit",
                amount=1_000_000,
                currency="CNY",
                note="初始资金",
            ))
            s.flush()
        return {"id": acct.id, "name": acct.name}


@router.get("/shadow/account", summary="获取模拟账户")
def get_shadow_account():
    acct = _get_shadow_account()
    db = DatabaseManager()
    with db.session_scope() as s:
        from src.storage import PortfolioCashLedger
        cash_records = (
            s.query(PortfolioCashLedger)
            .filter(PortfolioCashLedger.account_id == acct["id"])
            .all()
        )
        deposits = sum(r.amount for r in cash_records if r.direction == "deposit")
        withdraws = sum(r.amount for r in cash_records if r.direction == "withdraw")
        # 计算已实现盈亏
        from src.storage import PortfolioTrade
        trades = (
            s.query(PortfolioTrade)
            .filter(PortfolioTrade.account_id == acct["id"])
            .all()
        )
        total_cost = sum((t.quantity or 0) * (t.price or 0) for t in trades if t.side == "buy")
        total_sold = sum((t.quantity or 0) * (t.price or 0) for t in trades if t.side == "sell")
    return {
        **acct,
        "balance": deposits - withdraws,
        "total_cost": round(total_cost, 2),
        "total_sold": round(total_sold, 2),
        "realized_pnl": round(total_sold - total_cost, 2),
    }


@router.post("/shadow/trade", summary="记录模拟交易")
def record_shadow_trade(
    symbol: str = Query(..., description="股票代码"),
    side: str = Query(..., description="buy/sell"),
    quantity: float = Query(..., description="数量（股）"),
    price: float = Query(..., description="成交价"),
    note: str = Query("", description="备注"),
):
    acct = _get_shadow_account()
    db = DatabaseManager()
    with db.session_scope() as s:
        from src.storage import PortfolioTrade
        trade = PortfolioTrade(
            account_id=acct["id"],
            symbol=symbol.upper(),
            market=SHADOW_MARKET,
            currency="CNY",
            trade_date=date.today(),
            side=side.lower(),
            quantity=quantity,
            price=price,
            note=note or f"模拟{'买入' if side == 'buy' else '卖出'} {symbol}",
        )
        s.add(trade)
        s.flush()
        return {"id": trade.id, "symbol": symbol, "side": side, "quantity": quantity, "price": price}


@router.get("/shadow/positions", summary="当前持仓")
def get_shadow_positions():
    acct = _get_shadow_account()
    db = DatabaseManager()
    with db.session_scope() as s:
        from src.storage import PortfolioTrade
        trades = (
            s.query(PortfolioTrade)
            .filter(PortfolioTrade.account_id == acct["id"])
            .order_by(PortfolioTrade.trade_date)
            .all()
        )
    # 汇总持仓
    positions: dict = {}
    for t in trades:
        sym = t.symbol
        if sym not in positions:
            positions[sym] = {"symbol": sym, "quantity": 0, "total_cost": 0}
        if t.side == "buy":
            positions[sym]["quantity"] += t.quantity or 0
            positions[sym]["total_cost"] += (t.quantity or 0) * (t.price or 0)
        else:
            if positions[sym]["quantity"] > 0:
                avg_cost = positions[sym]["total_cost"] / positions[sym]["quantity"]
                positions[sym]["total_cost"] -= (t.quantity or 0) * avg_cost
            positions[sym]["quantity"] -= t.quantity or 0

    result = []
    for pos in positions.values():
        if pos["quantity"] > 0.001:
            pos["avg_cost"] = round(pos["total_cost"] / pos["quantity"], 2) if pos["quantity"] > 0 else 0
            pos["quantity"] = round(pos["quantity"], 2)
            pos["total_cost"] = round(pos["total_cost"], 2)
            result.append(pos)

    return {"positions": result, "count": len(result)}


@router.get("/shadow/history", summary="交易历史")
def get_shadow_history(limit: int = Query(50)):
    acct = _get_shadow_account()
    db = DatabaseManager()
    with db.session_scope() as s:
        from src.storage import PortfolioTrade
        trades = (
            s.query(PortfolioTrade)
            .filter(PortfolioTrade.account_id == acct["id"])
            .order_by(PortfolioTrade.trade_date.desc())
            .limit(limit)
            .all()
        )
    return {
        "trades": [
            {
                "id": t.id,
                "symbol": t.symbol,
                "side": t.side,
                "quantity": t.quantity,
                "price": t.price,
                "date": str(t.trade_date) if t.trade_date else None,
                "note": t.note,
            }
            for t in trades
        ]
    }
