#!/usr/bin/env python3
"""
使用官方 base_tdapi 查询 SimNow 所有合约
"""
import time, os, sys
os.environ['NO_PROXY'] = '*'

examples = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../integrations/ctp.examples/openctp-ctp')
sys.path.insert(0, examples)
from base_tdapi import CTdSpiBase, tdapi
from config import envs

instruments = []

class Spi(CTdSpiBase):
    def __init__(self):
        conf = envs['simu1'].copy()
        conf['user_id'] = '125964'
        conf['password'] = '@Lijinzhou666'
        super().__init__(conf)

    def req(self):
        self.print("查询全部合约...")
        req = tdapi.CThostFtdcQryInstrumentField()
        self._api.ReqQryInstrument(req, 0)

    def OnRspQryInstrument(self, d, e, r, l):
        if d and d.InstrumentID:
            instruments.append(f"[{d.ExchangeID}] {d.InstrumentID} {d.InstrumentName}")
        if l:
            self.print(f"查询完成，共 {len(instruments)} 个合约")
            for inst in instruments[:30]:
                print(f"  {inst}")

spi = Spi()
time.sleep(3)
spi.req()
spi.wait_last()
