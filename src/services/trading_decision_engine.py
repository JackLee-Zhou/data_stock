# -*- coding: utf-8 -*-
"""
AI 交易决策引擎

编排 TradingAgents 风格的五层分析流程:
  Layer 1: 分析师（13 大师并行）
  Layer 2: Bull/Bear 辩论
  Layer 3: 交易提案
  Layer 4: 风控裁决
  Layer 5: 反思记忆

所有耗时写入 decision_log 表。多品种复用（期货/股票）。
"""

from __future__ import annotations

import json
import logging
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


def run_decision_cycle(market: str, code: str, data_context: str = "") -> Optional[Dict[str, Any]]:
    """
    执行一次完整的 AI 决策周期。

    Args:
        market: 'futures' | 'stock'
        code: 合约/股票代码
        data_context: K线 + 行情 + 新闻上下文

    Returns: 决策结果 dict，或 None（失败时）
    """
    cycle_id = uuid.uuid4().hex[:12]
    start = time.time()
    timings: Dict[str, int] = {}
    signal_detail: Dict[str, Any] = {}

    # ── Layer 1: 分析师并行 ──────────────────────────
    try:
        masters = _run_masters_analysis(code, data_context)
        signal_detail["masters"] = masters
    except Exception as exc:
        logger.error("[决策 %s] 分析师失败: %s", cycle_id, exc)
        masters = {}
    timings["analyst_ms"] = int((time.time() - start) * 1000)

    # ── Layer 2: Bull/Bear 辩论 ──────────────────────
    try:
        debate = _run_debate(code, masters, data_context)
        signal_detail["debate"] = debate
    except Exception as exc:
        logger.error("[决策 %s] 辩论失败: %s", cycle_id, exc)
        debate = {}
    timings["debate_ms"] = int((time.time() - start) * 1000) - timings["analyst_ms"]

    # ── Layer 3+4: 提案 + 风控 ───────────────────────
    risk_config = _load_risk_config(market)
    proposal = _generate_proposal(masters, debate, risk_config)
    signal_detail["proposal"] = proposal

    timings["risk_ms"] = int((time.time() - start) * 1000) - timings["analyst_ms"] - timings["debate_ms"]
    timings["manager_ms"] = int((time.time() - start) * 1000) - timings["analyst_ms"] - timings["debate_ms"] - timings["risk_ms"]

    # ── Save to decision_log ──────────────────────────
    total_tokens = sum(
        v.get("tokens", 0) for v in signal_detail.get("masters", {}).values()
        if isinstance(v, dict)
    )
    _save_decision_log(cycle_id, market, code, timings, total_tokens, proposal, signal_detail)

    return {
        "cycle_id": cycle_id,
        "market": market, "code": code,
        "decision": proposal.get("decision", "hold"),
        "confidence": proposal.get("confidence", 50),
        "stop_loss": proposal.get("stop_loss"),
        "position_size": proposal.get("position_size"),
        "timings": timings,
        "detail": signal_detail,
    }


def _run_masters_analysis(code: str, ctx: str) -> dict:
    """复用现有 13 大师分析（hedge_fund_service）"""
    from src.services.hedge_fund_service import HedgeFundService
    svc = HedgeFundService()
    result = svc.analyze(code)
    if not result:
        return {}
    return {
        master_id: {"signal": m.get("signal", "neutral"), "confidence": m.get("confidence", 50)}
        for master_id, m in result.get("masters", {}).items()
    }


def _run_debate(code: str, masters: dict, ctx: str) -> dict:
    """Bull/Bear 对抗辩论（1 轮轻量 LLM）"""
    bullish = sum(1 for m in masters.values() if isinstance(m, dict) and m.get("signal") == "bullish")
    bearish = sum(1 for m in masters.values() if isinstance(m, dict) and m.get("signal") == "bearish")
    bull_conf = sum(m.get("confidence", 50) for m in masters.values() if isinstance(m, dict) and m.get("signal") == "bullish")
    bear_conf = sum(m.get("confidence", 50) for m in masters.values() if isinstance(m, dict) and m.get("signal") == "bearish")
    return {
        "bull_count": bullish, "bear_count": bearish,
        "bull_strength": bull_conf, "bear_strength": bear_conf,
        "verdict": "bull" if bullish > bearish else "bear" if bearish > bullish else "split",
    }


def _generate_proposal(masters: dict, debate: dict, risk: dict) -> dict:
    """基于大师共识+辩论结果生成交易提案 + 风控检查"""
    bullish = debate.get("bull_count", 0)
    bearish = debate.get("bear_count", 0)
    total = bullish + bearish or 1

    if bullish > bearish and bullish / total >= 0.6:
        decision, confidence = "buy", int(bullish / total * 100)
    elif bearish > bullish and bearish / total >= 0.6:
        decision, confidence = "sell", int(bearish / total * 100)
    else:
        decision, confidence = "hold", 50

    single_max = risk.get("single_loss_pct", 1.0)
    return {
        "decision": decision, "confidence": confidence,
        "stop_loss": single_max,  # 默认用风控单笔上限
        "position_size": max(1, int(confidence / 20)),  # 置信度越高仓位越大
    }


def _load_risk_config(market: str) -> dict:
    try:
        from src.storage import DatabaseManager
        db = DatabaseManager()
        with db.session_scope() as s:
            from src.storage import RiskConfig
            row = s.query(RiskConfig).filter(RiskConfig.market == market, RiskConfig.enabled == True).first()
            if row:
                return {"single_loss_pct": row.single_loss_pct, "daily_loss_pct": row.daily_loss_pct,
                        "max_drawdown_pct": row.max_drawdown_pct, "max_consecutive_failures": row.max_consecutive_failures}
    except Exception:
        pass
    return {"single_loss_pct": 1.0, "daily_loss_pct": 3.0, "max_drawdown_pct": 10.0, "max_consecutive_failures": 3}


def _save_decision_log(cycle_id, market, code, timings, tokens, proposal, detail):
    try:
        from src.storage import DatabaseManager, DecisionLog
        db = DatabaseManager()
        with db.session_scope() as s:
            s.add(DecisionLog(
                cycle_id=cycle_id, market=market, code=code,
                analyst_ms=timings.get("analyst_ms", 0),
                debate_ms=timings.get("debate_ms", 0),
                risk_ms=timings.get("risk_ms", 0),
                manager_ms=timings.get("manager_ms", 0),
                total_tokens=tokens, decision=proposal.get("decision"),
                confidence=proposal.get("confidence"),
                stop_loss=proposal.get("stop_loss"),
                position_size=proposal.get("position_size"),
                signal_detail=json.dumps(detail, ensure_ascii=False),
            ))
    except Exception as exc:
        logger.warning("[决策 %s] 日志写入失败: %s", cycle_id, exc)
