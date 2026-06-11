# CTP 行情引擎 (ctp_engine)

CTP 独立行情订阅引擎，部署在远端 Linux 服务器上，通过 CTP API 实时订阅全市场期货行情，按天 SQLite 归档，并提供 Telnet 远程 Console 供运维排查。

## 启动

```bash
cd /path/to/daily_stock_analysis
.venv/bin/python ctp_engine/main.py
```

建议配合 systemd 或 supervisor 守护。

## 环境变量

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `CTP_MD_FRONT` | 行情前置地址 | `tcp://182.254.243.31:30012` |
| `CTP_TRADE_FRONT` | 交易前置地址（仅启动时查询合约用） | `tcp://182.254.243.31:30002` |
| `CTP_BROKER_ID` | 经纪商 ID | `9999` |
| `CTP_USER_ID` | 用户 ID | — |
| `CTP_PASSWORD` | 密码 | — |
| `CTP_CONSOLE_PORT` | Console TCP 端口 | `9999` |
| `CTP_CONSOLE_BIND` | Console 绑定地址（远端部署设 `0.0.0.0` 需配合防火墙） | `127.0.0.1` |
| `CTP_PUSH_URL` | 增量推送到本地 Web 服务器的地址，为空则跳过推送 | — |
| `CTP_PUSH_INTERVAL` | 推送间隔（秒） | `10` |

## 远程 Console

```bash
nc <host> 9999
# 或
telnet <host> 9999
```

> 最大并发连接数：5。远端部署时建议绑定 `127.0.0.1` 并通过 SSH 隧道访问。

### 命令列表

| 命令 | 用法 | 说明 |
|------|------|------|
| `status` | — | 查看引擎状态（连接、登录、Tick 总数、Queue 深度、订阅数） |
| `contracts` | — | 列出全部订阅合约 |
| `sub` | `sub CU2507,RB2510` | 增加订阅合约 |
| `unsub` | `unsub AU2508` | 取消订阅 |
| `look` | `look fu2609 [20260611] [-n 100]` | 查看合约历史数据，默认显示最新 100 条 |
| `tail` | `tail fu2609 [-n 50] [-f [100]]` | 实时监控最新行情。`-f` 持续监控，可选跟数字控制条数（如 `-f 100`）；默认显示 50 条。监控中按 `q` 回车退出 |
| `size` | `size [合约代码]` | 查看数据文件大小 / 统计 |
| `expire` | `expire [天数]` | 查看/设置数据保留时间（最少 7 天，默认 120 天） |
| `push` | `push status` | 查看推送状态 |
| `log` | — | 查看最近 10 条日志 |
| `quit` | — | 退出 Console 连接 |

### look / tail 输出格式

```
  fu2609 | 20260611 | 共 3758 条，显示最新 3 条
  时间                       最新   成交量     持仓       买五       买四       买三       买二       买一       卖一       卖二       卖三       卖四       卖五
-----------------------------------------------------------------------------------------------------------------------------------------------------------------
  22:00:12.705             3742.0   79,158  204,313      -          -          -          -      3742/44    3743/14        -          -          -          -
  22:00:13.108             3743.0   79,174  204,311      -          -          -          -      3743/25    3744/36        -          -          -          -
```

- 每档格式：`价格/量`，无数据档位显示 `-`
- `tail -f` 模式下表头仅打印一次，后续数据持续追加

## 5 档深度说明

CTP 行情结构体本身包含全部 5 档数据：

| 档位 | 买盘 | 卖盘 |
|------|------|------|
| 1 | `BidPrice1` / `BidVolume1` | `AskPrice1` / `AskVolume1` |
| 2 | `BidPrice2` / `BidVolume2` | `AskPrice2` / `AskVolume2` |
| 3 | `BidPrice3` / `BidVolume3` | `AskPrice3` / `AskVolume3` |
| 4 | `BidPrice4` / `BidVolume4` | `AskPrice4` / `AskVolume4` |
| 5 | `BidPrice5` / `BidVolume5` | `AskPrice5` / `AskVolume5` |

- **SimNow 模拟环境**：仅推送 1 档深度（买一/卖一），其余档位为空，显示 `-`
- **实盘 CTP 环境**：推送完整 5 档深度，look / tail 自动展示全部档位

代码已完整提取并落库全部 20 个档位字段，切换到实盘环境无需改动。

## 数据存储

- 按天 SQLite 分库：`data/YYYYMMDD.db`
- 表 `ctp_tick`：
  - 基础：`code`, `trade_time`, `price`, `volume`, `open_interest`
  - 盘口：`bid1-5`, `bid_vol1-5`, `ask1-5`, `ask_vol1-5`
  - OHLC：`high`, `low`, `open`, `prev_close`
- 索引：`(code, trade_time)`
- 旧库遇到新列会自动 `ALTER TABLE` 补齐（同进程仅首次）
- 默认保留 120 天，可通过 `expire` 命令调整
- 日志：`logs/ctp_engine.log`，10MB × 7 滚动

## 架构

```
OnRtnDepthMarketData (CTP 回调)
       │
       ▼ tick dict
  tick_queue (Queue, 100万缓冲)
       │
       ├── storage_worker: 500条/批 → SQLite (当天库)
       │   └── 内部 state.add_tick → 推送到 _pending_push
       │
       └── push_worker: 每 N 秒 → POST /api/v1/ctp/sync
           
Console Server (TCP 9999)
  └── handle_client → CtpConsole.cmdloop (每连接独立线程)
```

- daily_refresh_worker：每天 0 点通过 TD API 查询新上市/摘牌合约，自动增减订阅
- MD 断线自动重连（10 秒后重试）

## 常见问题

**Q: 落库报 `database is locked`？**
A: 确认没有多个进程同时运行。`ps aux | grep ctp_engine` 检查。

**Q: 为什么没有买二～买五数据？**
A: SimNow 仅推送 1 档。切换实盘 CTP 后自动出现 5 档。

**Q: nc 连接后中文乱码？**
A: 客户端需支持 UTF-8。macOS 终端直接 `nc` 正常；Windows 建议用 `telnet` 或支持 UTF-8 的终端。

**Q: 如何修改数据保留天数？**
A: Console 内执行 `expire 30`（最少 7 天）。旧日库在下次清理周期自动删除。
