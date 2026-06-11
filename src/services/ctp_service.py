# -*- coding: utf-8 -*-
"""CTP 统一服务 — TD ReqQryDepthMarketData 轮询行情"""

import logging, os
from typing import Optional

from data_provider.ctp_md_adapter import CtpMdAdapter
from data_provider.ctp_types import CtpStatus

logger = logging.getLogger(__name__)
_ctp_started = False


def start_ctp() -> CtpStatus:
    global _ctp_started
    if _ctp_started: return CtpMdAdapter().status

    front = os.getenv("CTP_TRADE_FRONT", "tcp://182.254.243.31:30001")
    broker = os.getenv("CTP_BROKER_ID", "9999")
    user = os.getenv("CTP_USER_ID", "")
    pwd = os.getenv("CTP_PASSWORD", "")

    if not user or not pwd:
        logger.warning("[CTP] 未配置账号，跳过")
        return CtpStatus(connected=False, last_error="未配置")

    adapter = CtpMdAdapter()
    ok = adapter.connect(front, broker, user, pwd)
    _ctp_started = True
    return adapter.status


def get_quotes() -> dict:
    return CtpMdAdapter().get_quotes()


def get_quote(code: str) -> Optional[dict]:
    return CtpMdAdapter().get_quote(code)


def get_status() -> CtpStatus:
    return CtpMdAdapter().status
