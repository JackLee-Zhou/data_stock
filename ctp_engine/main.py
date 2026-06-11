#!/usr/bin/env python3
"""
CTP 行情订阅独立引擎 (远端部署版)

- MD API 推送模式订阅全市场期货行情
- Queue 解耦回调与存储
- 按天 SQLite 分库归档
- Console 交互式命令行
- 日志滚动
- 定时向本地 Web 服务器推送增量数据

启动: python ctp_engine/main.py
退出: Ctrl+C (优雅关闭) 或 console 中输入 quit

架构参考:
  知乎《CTP程序化交易进阶系列》- Queue 解耦
  博客园《CTP行情实时写入MySQL》- 数据落库模式
"""

import cmd
import json
import logging
import os
import sqlite3
import sys
import threading
import time
from datetime import datetime, date, timezone, timedelta

TZ = timezone(timedelta(hours=8))  # 北京时间 UTC+8
from logging.handlers import RotatingFileHandler
from queue import Queue
from typing import Dict, List, Optional

# ── 路径配置 ─────────────────────────────────────────
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENGINE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(ENGINE_DIR, "data")
LOG_DIR = os.path.join(ENGINE_DIR, "logs")
sys.path.insert(0, PROJECT_ROOT)

# 加载 .env
from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

from openctp_ctp import mdapi, tdapi

# ── 配置 ────────────────────────────────────────────
MD_FRONT = os.getenv("CTP_MD_FRONT", "tcp://182.254.243.31:30012")
TD_FRONT = os.getenv("CTP_TRADE_FRONT", "tcp://182.254.243.31:30002")
BROKER_ID = os.getenv("CTP_BROKER_ID", "9999")
USER_ID = os.getenv("CTP_USER_ID", "266139")
PASSWORD = os.getenv("CTP_PASSWORD", "")
PUSH_URL = os.getenv("CTP_PUSH_URL", "")  # 本地 Web 服务器地址
PUSH_INTERVAL = int(os.getenv("CTP_PUSH_INTERVAL", "10"))  # 推送间隔秒


# ── 动态查询全市场期货合约 ──────────────────────────
def load_all_futures() -> List[str]:
    """
    通过 TD ReqQryInstrument 查询所有交易所的期货合约 (ProductClass='1')。
    连接 TD → 登录 → 查询6个交易所 → 收集期货 → 返回列表。
    """
    all_codes = []
    done = threading.Event()

    class TdSpi(tdapi.CThostFtdcTraderSpi):
        def __init__(s):
            tdapi.CThostFtdcTraderSpi.__init__(s)
        def OnFrontConnected(s):
            auth = tdapi.CThostFtdcReqAuthenticateField()
            auth.BrokerID = BROKER_ID; auth.UserID = USER_ID
            auth.AppID = 'simnow_client_test'; auth.AuthCode = '0000000000000000'
            auth.UserProductInfo = '@openctp'
            s.api.ReqAuthenticate(auth, 0)
        def OnRspAuthenticate(s, d, e, r, l):
            req = tdapi.CThostFtdcReqUserLoginField()
            req.BrokerID = BROKER_ID; req.UserID = USER_ID; req.Password = PASSWORD
            req.UserProductInfo = '@openctp'
            s.api.ReqUserLogin(req, 0, 0, "")
        def OnRspUserLogin(s, d, e, r, l):
            logger.info("[TD] 登录成功: Day=%s, 查询全市场合约...", d.TradingDay if d else "?")
            for ex in ['SHFE', 'DCE', 'CZCE', 'CFFEX', 'INE', 'GFEX']:
                q = tdapi.CThostFtdcQryInstrumentField(); q.ExchangeID = ex
                s.api.ReqQryInstrument(q, 0)
        def OnRspQryInstrument(s, d, e, r, l):
            if d and d.InstrumentID and d.ProductClass == '1':
                all_codes.append(d.InstrumentID)
            if l:
                logger.info("[TD] 查询完成: 共 %d 个期货合约", len(all_codes))
                done.set()

    flow = os.path.join(ENGINE_DIR, "flow_td")
    os.makedirs(flow, exist_ok=True)
    spi = TdSpi()
    api = tdapi.CThostFtdcTraderApi.CreateFtdcTraderApi(os.path.join(flow, "td_query"))
    spi.api = api
    api.RegisterFront(TD_FRONT)
    api.RegisterSpi(spi)
    api.Init()

    if not done.wait(timeout=30):
        logger.error("[TD] 查询合约超时，使用空列表")
        return []

    api.Release()
    logger.info("动态获取 %d 个期货合约", len(all_codes))
    return sorted(all_codes)

# ── 订阅合约（启动时从 TD API 动态查询，不写死）─────
DEFAULT_CODES: List[str] = []  # 启动后由 _load_instruments() 填充

# ── 目录初始化 ──────────────────────────────────────
os.makedirs(DATA_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# ── 日志 ────────────────────────────────────────────
logger = logging.getLogger("ctp_engine")
logger.setLevel(logging.DEBUG)

# 控制台
console = logging.StreamHandler(sys.stdout)
console.setLevel(logging.INFO)
console.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s', '%H:%M:%S'))
logger.addHandler(console)

# 文件（10MB 滚动，保留 7 天）
file_handler = RotatingFileHandler(
    os.path.join(LOG_DIR, "ctp_engine.log"), maxBytes=10*1024*1024, backupCount=7, encoding='utf-8'
)
file_handler.setLevel(logging.DEBUG)
file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
logger.addHandler(file_handler)


# ── 全局状态 ────────────────────────────────────────
class EngineState:
    """引擎全局状态（线程安全）"""
    def __init__(self):
        self.codes: List[str] = list(DEFAULT_CODES)
        self.tick_count = 0
        self.push_count = 0
        self.connected = False
        self.logged_in = False
        self.trading_day = ""
        self.lock = threading.Lock()
        self._pending_push: List[dict] = []
        self._push_lock = threading.Lock()

    def add_tick(self, tick: dict):
        with self.lock:
            self.tick_count += 1
        with self._push_lock:
            if len(self._pending_push) < MAX_PENDING_PUSH:
                self._pending_push.append(tick)

    def pop_pending(self) -> List[dict]:
        with self._push_lock:
            batch = self._pending_push
            self._pending_push = []
            return batch

state = EngineState()
tick_queue: Queue = Queue(maxsize=1000000)  # 100万tick ≈ 4小时缓冲
_dropped_ticks = 0
_drop_lock = threading.Lock()


# ── 按天 SQLite ─────────────────────────────────────
def get_daily_db(d: Optional[date] = None) -> str:
    """获取当天的 SQLite 数据库路径，自动创建表。"""
    d = d or date.today()
    db_path = os.path.join(DATA_DIR, f"{d.strftime('%Y%m%d')}.db")
    if not os.path.exists(db_path):
        conn = sqlite3.connect(db_path)
        conn.execute("""CREATE TABLE IF NOT EXISTS ctp_tick (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            trade_time TEXT NOT NULL,
            price REAL, volume REAL, open_interest REAL,
            bid1 REAL, ask1 REAL,
            high REAL, low REAL, open REAL, prev_close REAL
        )""")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_code_time ON ctp_tick(code, trade_time)")
        conn.commit()
        conn.close()
        logger.info("新建日库: %s", os.path.basename(db_path))
    return db_path


# ── MD SPI ──────────────────────────────────────────
class MdSpi(mdapi.CThostFtdcMdSpi):
    def __init__(self):
        mdapi.CThostFtdcMdSpi.__init__(self)
        self.api: Optional[mdapi.CThostFtdcMdApi] = None
        self.logged_in = threading.Event()

    def OnFrontConnected(self):
        state.connected = True
        logger.info("MD 连接成功，登录中...")
        req = mdapi.CThostFtdcReqUserLoginField()
        req.BrokerID = BROKER_ID; req.UserID = USER_ID; req.Password = PASSWORD
        req.UserProductInfo = '@openctp'
        self.api.ReqUserLogin(req, 0)

    def OnFrontDisconnected(self, reason: int):
        state.connected = False
        logger.warning("MD 断开: reason=%d, 10s 后自动重连...", reason)
        # 异步重连（避免在 CTP 回调中阻塞）
        def _reconnect():
            time.sleep(10)
            self.api.RegisterFront(MD_FRONT)
            self.api.Init()
            logger.info("MD 重连已发起")
        threading.Thread(target=_reconnect, daemon=True).start()

    def OnRspUserLogin(self, pRsp, pErr, nReq, bLast):
        if pErr and pErr.ErrorID != 0:
            logger.error("登录失败: [%d] %s", pErr.ErrorID, pErr.ErrorMsg)
            return
        state.logged_in = True
        state.trading_day = pRsp.TradingDay if pRsp else ""
        logger.info("登录成功: Day=%s", state.trading_day)
        self._subscribe()

    def _subscribe(self):
        codes = [c.encode() for c in state.codes]
        ret = self.api.SubscribeMarketData(codes, len(codes))
        logger.info("订阅 %d 个合约, ret=%d", len(codes), ret)
        self.logged_in.set()

    def subscribe_codes(self, new_codes: List[str]):
        encoded = [c.encode() for c in new_codes]
        self.api.SubscribeMarketData(encoded, len(encoded))

    def unsubscribe_codes(self, codes: List[str]):
        encoded = [c.encode() for c in codes]
        self.api.UnSubscribeMarketData(encoded, len(encoded))

    def OnRtnDepthMarketData(self, pData):
        if not pData or pData.LastPrice <= 0: return
        tick = {
            "code": pData.InstrumentID,
            "time": datetime.now(TZ).isoformat(),
            "price": pData.LastPrice,
            "volume": pData.Volume, "open_interest": pData.OpenInterest,
            "bid1": pData.BidPrice1 if 0 < pData.BidPrice1 < 1e100 else None,
            "ask1": pData.AskPrice1 if 0 < pData.AskPrice1 < 1e100 else None,
            "high": pData.HighestPrice if pData.HighestPrice > 0 else None,
            "low": pData.LowestPrice if pData.LowestPrice > 0 else None,
            "open": pData.OpenPrice if pData.OpenPrice > 0 else None,
            "prev_close": pData.PreSettlementPrice if pData.PreSettlementPrice > 0 else None,
        }
        try:
            tick_queue.put_nowait(tick)
        except Exception:
            global _dropped_ticks
            with _drop_lock:
                _dropped_ticks += 1
                if _dropped_ticks % 1000 == 0:
                    logger.warning("Queue满! 丢弃 %d ticks", _dropped_ticks)


# ── 落库线程 ────────────────────────────────────────
def storage_worker():
    """批量写入当天 SQLite + 定期清理旧数据（保留 30 天）"""
    logger.info("落库线程启动")
    batch: List[dict] = []
    last_flush = time.time()
    last_cleanup = date.today()

    while True:
        try:
            tick = tick_queue.get(timeout=2)
            batch.append(tick)
        except Exception:
            pass

        if batch and (len(batch) >= 500 or time.time() - last_flush > 2):
            try:
                db_path = get_daily_db()
                conn = sqlite3.connect(db_path)
                conn.execute("BEGIN")
                for t in batch:
                    conn.execute(
                        "INSERT INTO ctp_tick(code,trade_time,price,volume,open_interest,bid1,ask1,high,low,open,prev_close) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                        (t["code"], t["time"], t["price"], t["volume"], t["open_interest"],
                         t["bid1"], t["ask1"], t["high"], t["low"], t["open"], t["prev_close"])
                    )
                    state.add_tick(t)
                conn.commit()
                conn.close()
                logger.debug("落库 %d ticks", len(batch))
            except Exception as exc:
                logger.error("落库失败: %s", exc)
            batch.clear()
            last_flush = time.time()

            # 每天检查一次，清理 30 天前的数据
            today = date.today()
            if today > last_cleanup:
                last_cleanup = today
                cutoff = today - timedelta(days=DATA_RETENTION_DAYS)
                for fname in os.listdir(DATA_DIR):
                    if not fname.endswith('.db'): continue
                    try:
                        fdate = datetime.strptime(fname.replace('.db', ''), "%Y%m%d").date()
                        if fdate < cutoff:
                            os.remove(os.path.join(DATA_DIR, fname))
                            logger.info("清理旧日库: %s", fname)
                    except ValueError: pass


# ── 每日合约刷新 ────────────────────────────────────
def daily_refresh_worker(spi: MdSpi):
    """每天凌晨 0 点检查新合约并自动订阅/取消"""
    last_date = date.today()
    while True:
        time.sleep(60)
        today = date.today()
        if today == last_date:
            continue
        last_date = today
        logger.info("=== 每日合约刷新 (%s) ===", today)
        try:
            new_codes = load_all_futures()
            added = [c for c in new_codes if c not in state.codes]
            removed = [c for c in state.codes if c not in new_codes]
            if added:
                spi.subscribe_codes(added)
                state.codes.extend(added)
                logger.info("新增 %d 个合约: %s", len(added), added[:10])
            if removed:
                spi.unsubscribe_codes(removed)
                for c in removed: state.codes.remove(c)
                logger.info("移除 %d 个过期合约: %s", len(removed), removed[:10])
            if not added and not removed:
                logger.info("合约无变化 (%d 个)", len(state.codes))
        except Exception as exc:
            logger.error("每日合约刷新失败: %s", exc)


# ── 推送线程 ────────────────────────────────────────
def push_worker():
    """定时向本地服务器推送增量 tick（异步非阻塞）"""
    if not PUSH_URL:
        logger.info("未配置 PUSH_URL，跳过推送")
        return
    logger.info("推送线程启动: %s, 间隔 %ds", PUSH_URL, PUSH_INTERVAL)
    import requests
    from concurrent.futures import ThreadPoolExecutor
    executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="push")

    def do_push(batch):
        try:
            resp = requests.post(
                f"{PUSH_URL}/api/v1/ctp/sync",
                json={"ticks": batch[-2000:]},
                timeout=10,
            )
            if resp.status_code == 200:
                state.push_count += len(batch)
            else:
                logger.warning("推送失败: HTTP %d", resp.status_code)
        except Exception as exc:
            logger.warning("推送异常: %s", exc)

    while True:
        time.sleep(PUSH_INTERVAL)
        batch = state.pop_pending()
        if not batch: continue
        executor.submit(do_push, batch)  # 异步提交，不阻塞循环


# ── Telnet Console (TCP 远程访问) ───────────────────
CONSOLE_PORT = int(os.getenv("CTP_CONSOLE_PORT", "9999"))
CONSOLE_BIND = os.getenv("CTP_CONSOLE_BIND", "127.0.0.1")  # 默认仅本地，远端部署设为 0.0.0.0 时需配合防火墙
MAX_CONSOLE_CONNS = 5  # 最大并发 Console 连接数
MAX_PENDING_PUSH = 50000  # 推送队列最大积压（约 30 分钟数据）
DATA_RETENTION_DAYS = 120  # 默认保留 120 天


class CtpConsole(cmd.Cmd):
    """可通过 telnet/nc 远程连接的 Console"""
    intro = "\nCTP 行情引擎 v2.0\n输入 help 查看命令\n"
    prompt = "ctp> "

    def __init__(self, spi: MdSpi, stdin=None, stdout=None):
        super().__init__(stdin=stdin or sys.stdin, stdout=stdout or sys.stdout)
        self.spi = spi
        self.use_rawinput = False

    def do_status(self, _):
        """查看引擎状态"""
        with state.lock:
            tc = state.tick_count
        print(f"  连接: {'✅' if state.connected else '❌'} | 登录: {'✅' if state.logged_in else '❌'}", file=self.stdout, flush=True)
        print(f"  交易日: {state.trading_day}", file=self.stdout, flush=True)
        print(f"  Tick 总数: {tc} | 推送: {state.push_count}", file=self.stdout, flush=True)
        print(f"  Queue: {tick_queue.qsize()} | 订阅: {len(state.codes)}", file=self.stdout, flush=True)

    def do_contracts(self, _):
        """列出所有订阅合约"""
        for i, c in enumerate(state.codes):
            print(f"  {i+1:3d}. {c}", end="", file=self.stdout, flush=True)
            if (i + 1) % 6 == 0: print(file=self.stdout, flush=True)
        print(file=self.stdout, flush=True)

    def do_sub(self, arg):
        """增加订阅: sub CU2507,RB2510"""
        codes = [c.strip() for c in arg.split(",") if c.strip()]
        new_codes = [c for c in codes if c not in state.codes]
        already = [c for c in codes if c in state.codes]
        if new_codes:
            state.codes.extend(new_codes)
            self.spi.subscribe_codes(new_codes)
            print(f"已增加: {new_codes}", file=self.stdout, flush=True)
        if already:
            print(f"已在列表: {already}", file=self.stdout, flush=True)
        if not new_codes and not already:
            print("无匹配合约", file=self.stdout, flush=True)

    def do_unsub(self, arg):
        """取消订阅: unsub AU2508"""
        codes = [c.strip() for c in arg.split(",") if c.strip()]
        for c in codes:
            if c in state.codes:
                state.codes.remove(c)
        self.spi.unsubscribe_codes(codes)
        print(f"已取消: {codes}", file=self.stdout, flush=True)

    def do_push(self, arg):
        """推送状态: push status"""
        if arg == "status":
            print(f"  PUSH_URL: {PUSH_URL or '未配置'}", file=self.stdout, flush=True)
            print(f"  间隔: {PUSH_INTERVAL}s | 累计推送: {state.push_count}", file=self.stdout, flush=True)

    def do_look(self, arg):
        """查看合约历史数据: look fu2609 [20260611] [-n 100]"""
        import sqlite3 as _sqlite
        parts = arg.strip().split()
        if not parts:
            print("用法: look <合约代码> [日期] [-n 条数]", file=self.stdout, flush=True)
            return
        code = parts[0]
        day = date.today().strftime("%Y%m%d")
        limit = 50
        i = 1
        while i < len(parts):
            if parts[i].startswith("-n") and i + 1 < len(parts):
                limit = int(parts[i+1]); i += 2
            elif len(parts[i]) == 8 and parts[i].isdigit():
                day = parts[i]; i += 1
            else:
                i += 1

        db_path = os.path.join(DATA_DIR, f"{day}.db")
        if not os.path.exists(db_path):
            print(f"数据文件不存在: {day}.db", file=self.stdout, flush=True)
            return

        conn = _sqlite.connect(db_path)
        total = conn.execute(
            "SELECT COUNT(*) FROM ctp_tick WHERE code=?", (code,)
        ).fetchone()[0]
        if total == 0:
            print(f"{code} 在 {day} 无数据", file=self.stdout, flush=True)
            conn.close(); return

        offset = 0
        page_size = min(limit, 20)  # 每页 20 条
        total_pages = (total + page_size - 1) // page_size

        while offset < total:
            rows = conn.execute(
                "SELECT trade_time,price,volume,open_interest,bid1,ask1 FROM ctp_tick WHERE code=? ORDER BY trade_time LIMIT ? OFFSET ?",
                (code, page_size, offset)
            ).fetchall()
            if not rows: break

            print(f"\n{'='*80}", file=self.stdout, flush=True)
            print(f"  {code} | {day} | 第 {offset//page_size + 1}/{total_pages} 页 | 共 {total} 条", file=self.stdout, flush=True)
            print(f"  {'时间':<22s} {'价格':>10s} {'成交量':>12s} {'持仓':>10s} {'买一':>10s} {'卖一':>10s}", file=self.stdout, flush=True)
            print(f"  {'-'*76}", file=self.stdout, flush=True)
            for r in rows:
                print(f"  {r[0]:<22s} {r[1]:>10.2f} {int(r[2] or 0):>12,d} {int(r[3] or 0):>10,d} {r[4] or '':>10s} {r[5] or '':>10s}",
                      file=self.stdout, flush=True)

            offset += page_size
            if offset >= total: break

            print(f"\n  [Enter 下一页 | b 上一页 | q 退出 | 第{offset//page_size+1}/{total_pages}页]",
                  file=self.stdout, flush=True)
            try:
                line = self.stdin.readline()
                if not line:
                    break
                cmd = line.strip().lower()
                if cmd == 'q':
                    print("已退出", file=self.stdout, flush=True)
                    conn.close(); return
                elif cmd == 'b':
                    offset = max(0, offset - page_size * 2)
            except Exception:
                break

        conn.close()
        print(f"\n -- 完 --", file=self.stdout, flush=True)

    def do_size(self, arg):
        """查看数据大小: size [合约代码]"""
        code = arg.strip() if arg else None
        total_size = 0
        total_ticks = 0
        files = sorted([f for f in os.listdir(DATA_DIR) if f.endswith('.db')], reverse=True)

        if code:
            # 查单个合约在每个日库中的条数
            print(f"\n  {code} 数据统计:", file=self.stdout, flush=True)
            print(f"  {'日期':<12s} {'Tick数':>10s} {'文件大小':>12s}", file=self.stdout, flush=True)
            print(f"  {'-'*38}", file=self.stdout, flush=True)
            for fname in files:
                db_path = os.path.join(DATA_DIR, fname)
                fsize = os.path.getsize(db_path)
                conn = sqlite3.connect(db_path)
                cnt = conn.execute("SELECT COUNT(*) FROM ctp_tick WHERE code=?", (code,)).fetchone()[0]
                conn.close()
                if cnt > 0:
                    total_ticks += cnt
                    total_size += fsize
                    print(f"  {fname.replace('.db',''):<12s} {cnt:>10,d} {fsize:>11,d}B", file=self.stdout, flush=True)
            print(f"  {'─'*38}", file=self.stdout, flush=True)
            print(f"  合计: {total_ticks:,d} ticks, {total_size/1024:.1f}KB ({total_size/1024/1024:.1f}MB)", file=self.stdout, flush=True)
        else:
            # 总览
            print(f"\n  {'日期':<12s} {'Tick总数':>10s} {'文件大小':>12s}", file=self.stdout, flush=True)
            print(f"  {'-'*38}", file=self.stdout, flush=True)
            import sqlite3 as _sqlite
            for fname in files[-10:]:  # 最近 10 天
                db_path = os.path.join(DATA_DIR, fname)
                fsize = os.path.getsize(db_path)
                conn = _sqlite.connect(db_path)
                cnt = conn.execute("SELECT COUNT(*) FROM ctp_tick").fetchone()[0]
                conn.close()
                total_ticks += cnt
                total_size += fsize
                print(f"  {fname.replace('.db',''):<12s} {cnt:>10,d} {fsize:>11,d}B" if cnt > 0 else f"  {fname.replace('.db',''):<12s} (空)", file=self.stdout, flush=True)
            print(f"  {'─'*38}", file=self.stdout, flush=True)
            print(f"  总计: {total_ticks:,d} ticks, {total_size/1024/1024:.1f}MB", file=self.stdout, flush=True)

    def do_expire(self, arg):
        """查看/设置数据过期时间: expire [天数，默认120]"""
        global DATA_RETENTION_DAYS
        arg = arg.strip()
        if arg:
            try:
                days = int(arg)
                if days < 7:
                    print("最少保留 7 天", file=self.stdout, flush=True)
                    return
                DATA_RETENTION_DAYS = days
                print(f"数据保留时间已设为 {days} 天（旧数据将在下次清理时删除）", file=self.stdout, flush=True)
            except ValueError:
                print("请输入有效天数，如: expire 60", file=self.stdout, flush=True)
        else:
            print(f"当前数据保留: {DATA_RETENTION_DAYS} 天", file=self.stdout, flush=True)

    def do_log(self, _):
        """查看最近日志 (最后10行)"""
        try:
            with open(os.path.join(LOG_DIR, "ctp_engine.log"), 'r') as f:
                lines = f.readlines()
                for l in lines[-10:]:
                    print(l.rstrip(), file=self.stdout, flush=True)
        except Exception as e:
            print(f"读取日志失败: {e}", file=self.stdout, flush=True)

    def do_quit(self, _):
        """退出引擎"""
        print("正在关闭...", file=self.stdout, flush=True)
        return True

    def do_EOF(self, _):
        return True

    def default(self, line):
        print(f"未知命令: {line}，输入 help 查看帮助", file=self.stdout, flush=True)

    def cmdloop(self, intro=None):
        """自定义命令循环：用 self.stdin.readline() 替代 sys.stdin"""
        if intro is not None:
            self.intro = intro
        if self.intro:
            self.stdout.write(self.intro + "\n")
            self.stdout.flush()
        stop = None
        while not stop:
            if self.cmdqueue:
                line = self.cmdqueue.pop(0)
            else:
                self.stdout.write(self.prompt)
                self.stdout.flush()
                line = self.stdin.readline()
                if not line:
                    break
                line = line.rstrip('\r\n')
            line = self.precmd(line)
            stop = self.onecmd(line)
            stop = self.postcmd(stop, line)
        return stop


# ── 主入口 ──────────────────────────────────────────
def main():
    print("=" * 60)
    print("CTP 行情引擎 v2.0")
    print(f"TD: {TD_FRONT} | MD: {MD_FRONT}")
    print(f"账号: {USER_ID}")
    print(f"数据目录: {DATA_DIR} | 日志: {LOG_DIR}")

    # Step 1: 从 TD 动态查询全市场期货合约列表
    global DEFAULT_CODES
    print("查询全市场期货合约...")
    DEFAULT_CODES = load_all_futures()
    if not DEFAULT_CODES:
        print("❌ 无法获取期货合约列表，退出")
        return 1
    print(f"✅ 获取 {len(DEFAULT_CODES)} 个期货合约")
    state.codes = list(DEFAULT_CODES)

    # Step 2: 初始化当天 DB
    ds = get_daily_db()
    print(f"今日 DB: {os.path.basename(ds)}")
    print("=" * 60)

    # 启动后台线程
    threading.Thread(target=storage_worker, daemon=True, name="storage").start()
    threading.Thread(target=push_worker, daemon=True, name="push").start()

    # Step 3: 启动 MD API 订阅全部期货
    spi = MdSpi()
    flow = os.path.join(ENGINE_DIR, "flow_md")
    os.makedirs(flow, exist_ok=True)
    api = mdapi.CThostFtdcMdApi.CreateFtdcMdApi(os.path.join(flow, "md_flow"))
    spi.api = api
    api.RegisterFront(MD_FRONT)
    api.RegisterSpi(spi)
    api.Init()

    if not spi.logged_in.wait(timeout=30):
        logger.error("登录超时")
        return 1

    # 启动每日合约刷新
    threading.Thread(target=daily_refresh_worker, args=(spi,), daemon=True, name="daily").start()

    logger.info("引擎就绪，守护进程模式")
    logger.info("远程 Console: telnet localhost %d  (或 nc localhost %d)", CONSOLE_PORT, CONSOLE_PORT)

    # Telnet Console Server（后台线程监听 TCP，支持多次连接断开）
    def handle_client(conn, addr):
        logger.info("Console 连接: %s", addr)
        try:
            # 包装 socket 为文件对象供 cmd.Cmd 使用
            rfile = conn.makefile('r', encoding='utf-8')
            wfile = conn.makefile('w', encoding='utf-8')
            CtpConsole(spi, stdin=rfile, stdout=wfile).cmdloop()
            rfile.close(); wfile.close()
        except Exception as exc:
            logger.debug("Console 断开 %s: %s", addr, exc)
        finally:
            conn.close()
            logger.info("Console 断开: %s", addr)

    def console_server():
        import socket as _socket
        srv = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
        srv.setsockopt(_socket.SOL_SOCKET, _socket.SO_REUSEADDR, 1)
        srv.bind((CONSOLE_BIND, CONSOLE_PORT))
        srv.listen(MAX_CONSOLE_CONNS)
        logger.info("Console %s:%d 已监听 (max %d 连接)", CONSOLE_BIND, CONSOLE_PORT, MAX_CONSOLE_CONNS)

        active_conns = 0
        conn_lock = threading.Lock()

        while True:
            conn, addr = srv.accept()
            with conn_lock:
                if active_conns >= MAX_CONSOLE_CONNS:
                    conn.close()
                    logger.warning("Console 连接数已满，拒绝 %s", addr)
                    continue
                active_conns += 1
            def _handle():
                nonlocal active_conns
                try:
                    handle_client(conn, addr)
                finally:
                    with conn_lock:
                        active_conns -= 1
            threading.Thread(target=_handle, daemon=True).start()

    threading.Thread(target=console_server, daemon=True, name="console").start()

    try:
        while True:
            time.sleep(60)
            logger.debug("心跳: ticks=%d queue=%d", state.tick_count, tick_queue.qsize())
    except KeyboardInterrupt:
        print("\n收到中断信号")
    finally:
        api.Release()
        logger.info("引擎已停止")

    return 0


if __name__ == '__main__':
    sys.exit(main())
