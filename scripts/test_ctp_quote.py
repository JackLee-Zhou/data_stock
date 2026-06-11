#!/usr/bin/env python3
"""
TD API 直接查询行情快照 (ReqQryDepthMarketData)
不通过 MD 订阅，直接通过交易 API 查询。

用法: python scripts/test_ctp_quote.py
"""
import time, os, sys
os.environ['NO_PROXY'] = '*'

# 使用官方基类
examples_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../integrations/ctp.examples/openctp-ctp')
sys.path.insert(0, examples_dir)

from base_tdapi import CTdSpiBase, tdapi
from config import envs

class Spi(CTdSpiBase):
    def __init__(self):
        conf = envs['simu1'].copy()
        conf['user_id'] = '125964'
        conf['password'] = '@Lijinzhou666'
        super().__init__(conf)

    def req(self):
        """查询行情快照（不传InstrumentID=查所有）"""
        self.print("查询所有合约行情快照...")
        req = tdapi.CThostFtdcQryDepthMarketDataField()
        self._api.ReqQryDepthMarketData(req, 0)

    def OnRspQryDepthMarketData(self, d, e, r, l):
        if d and d.InstrumentID:
            print(f'  行情: {d.InstrumentID} ¥{d.LastPrice} 买{d.BidPrice1} 卖{d.AskPrice1} 量{d.Volume}')
        if l:
            self.print("查询完成")

spi = Spi()
time.sleep(3)
spi.req()
spi.wait_last()
