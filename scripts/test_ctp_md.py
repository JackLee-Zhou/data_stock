#!/usr/bin/env python3
"""
CTP 行情订阅测试 — 通过 TD 查询 SimNow 实际支持的合约，
然后用正确的合约代码订阅 MD 行情。
"""
import time, os, sys
os.environ['NO_PROXY'] = '*'
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))
from openctp_ctp import tdapi, mdapi

UID = os.environ['CTP_USER_ID']
PWD = os.environ['CTP_PASSWORD']

found_instruments = []

# ============ Step 1: 通过 TD 查询实际可用合约 ============
class TdSpi(tdapi.CThostFtdcTraderSpi):
    def __init__(self):
        tdapi.CThostFtdcTraderSpi.__init__(self)
    def OnFrontConnected(self):
        auth = tdapi.CThostFtdcReqAuthenticateField()
        auth.BrokerID = '9999'; auth.UserID = UID
        auth.AppID = 'simnow_client_test'; auth.AuthCode = '0000000000000000'
        self.api.ReqAuthenticate(auth, 1)
    def OnRspAuthenticate(self, d, e, r, l):
        print(f'Auth: {"OK" if (not e or e.ErrorID==0) else f"FAIL {e.ErrorMsg}"}')
        req = tdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = '9999'; req.UserID = UID; req.Password = PWD
        self.api.ReqUserLogin(req, 2, 0, b'')
    def OnRspUserLogin(self, d, e, r, l):
        print(f'Login: {d.TradingDay if d else "?"}')
        # 查询各交易所合约
        for ex in ['SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE']:
            q = tdapi.CThostFtdcQryInstrumentField()
            q.ExchangeID = ex; self.api.ReqQryInstrument(q, 3)
    def OnRspQryInstrument(self, d, e, r, l):
        if d and d.InstrumentID:
            found_instruments.append((d.InstrumentID, d.ExchangeID))

# Run TD
td_spi = TdSpi()
td = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi(UID)
td_spi.api = td
td.RegisterFront('tcp://182.254.243.31:30001')
td.RegisterSpi(td_spi)
td.Init()
print('Step 1: Querying instruments via TD...')
for _ in range(15): time.sleep(1)
print(f'Found {len(found_instruments)} instruments')
for code, ex in found_instruments[:20]:
    print(f'  [{ex}] {code}')

# ============ Step 2: 用找到的合约订阅 MD ============
if found_instruments:
    md_ticks = []
    class MdSpi(mdapi.CThostFtdcMdSpi):
        def __init__(self):
            mdapi.CThostFtdcMdSpi.__init__(self)
        def OnFrontConnected(self):
            req = mdapi.CThostFtdcReqUserLoginField()
            req.BrokerID='9999'; req.UserID=UID; req.Password=PWD
            self.api.ReqUserLogin(req, 1)
        def OnRspUserLogin(self, d, e, r, l):
            codes = [c for c, _ in found_instruments[:10]]
            for c in codes:
                self.api.SubscribeMarketData([c.encode()], 1)
            print(f'Subscribed {len(codes)} contracts from TD query')
        def OnRtnDepthMarketData(self, d):
            md_ticks.append(d)
            print(f'TICK: {d.InstrumentID} ¥{d.LastPrice} vol={d.Volume}')

    md_spi = MdSpi()
    md = mdapi.CThostFtdcMdApi.CreateFtdcMdApi("market")
    md_spi.api = md
    md.RegisterFront('tcp://182.254.243.31:30011')
    md.RegisterSpi(md_spi)
    md.Init()
    print('Step 2: Waiting for market data...')
    for _ in range(30): time.sleep(1)
    print(f'MD ticks received: {len(md_ticks)}')
else:
    print('No instruments found - cannot test MD')
