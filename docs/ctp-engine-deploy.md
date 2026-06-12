# CTP 行情引擎 — 部署指南

## 1. 文件位置

```
daily_stock_analysis/
├── ctp_engine/
│   ├── main.py              # 入口
│   ├── Dockerfile            # Docker 构建文件
│   ├── ctp_engine.spec       # PyInstaller 打包 spec（可选）
│   ├── .env.example          # 环境变量模板
│   ├── .env                  # 实际配置（不入库）
│   ├── data/                 # SQLite 日库（按天：20260612.db）
│   ├── logs/                 # 日志（ctp_engine.log，10MB×7 滚动）
│   ├── flow_md/              # CTP 行情 API 运行时流文件
│   └── flow_td/              # CTP 交易 API 运行时流文件
└── docs/
    ├── ctp-engine.md         # 使用文档
    └── ctp-engine-deploy.md  # 本文档
```

关键文件说明：

| 路径 | 作用 | 是否需要备份 |
|------|------|:----:|
| `ctp_engine/.env` | CTP 账号、密码、行情地址 | ✅ |
| `ctp_engine/data/*.db` | 历史行情数据（单日几十 MB） | 视需求 |
| `ctp_engine/logs/*.log` | 运行日志 | 否 |

---

## 2. 部署方式对比

| 方式 | 适合场景 | 资源占用 |
|------|----------|----------|
| **Docker（推荐）** | 生产环境、云服务器 | ~120MB 内存，镜像 ~150MB |
| 直接运行 | 本地开发、测试 | ~100MB 内存 |
| PyInstaller 打包 | 无 Python 环境的裸机 | ~20MB 单文件 + CTP .so |

---

## 3. Docker 部署（推荐）

### 3.1 首次部署

```bash
# 1. 拉代码
cd /opt/daily_stock_analysis
git pull

# 2. 配置环境变量
cp ctp_engine/.env.example ctp_engine/.env
vim ctp_engine/.env
```

`.env` 最少需要填的项：

```ini
CTP_USER_ID=你的CTP账号
CTP_PASSWORD=你的CTP密码
CTP_MD_FRONT=tcp://182.254.243.31:30012
CTP_TRADE_FRONT=tcp://182.254.243.31:30002
CTP_BROKER_ID=9999
CTP_CONSOLE_PORT=9999
CTP_CONSOLE_BIND=0.0.0.0
```

> **注意**：容器内 `CONSOLE_BIND=0.0.0.0`，但 Docker 端口映射到 `127.0.0.1`，公网不会暴露。

```bash
# 3. 构建镜像（首次约 2-3 分钟）
docker build -f ctp_engine/Dockerfile -t ctp_engine .

# 4. 创建目录并启动
mkdir -p ctp_engine/data ctp_engine/logs

docker run -d --name ctp_engine \
  --restart unless-stopped \
  -v $(pwd)/ctp_engine/.env:/app/.env:ro \
  -v $(pwd)/ctp_engine/data:/app/data \
  -v $(pwd)/ctp_engine/logs:/app/logs \
  -p 127.0.0.1:9999:9999 \
  ctp_engine
```

### 3.2 日常运维

```bash
# 查看日志
docker logs -f --tail 50 ctp_engine

# 进入 Console
docker exec -it ctp_engine python -c "
import socket; s = socket.socket(); s.connect(('127.0.0.1', 9999))
" 
# 或者直接 nc（推荐）
nc localhost 9999

# 查看状态
docker ps --filter name=ctp_engine

# 重启
docker restart ctp_engine

# 停止
docker stop ctp_engine

# 升级（拉新代码后）
docker stop ctp_engine && docker rm ctp_engine
docker build -f ctp_engine/Dockerfile -t ctp_engine .
# 然后重新执行上面的 docker run 命令
```

### 3.3 docker-compose（可选）

```yaml
# docker-compose.yml
services:
  ctp_engine:
    build:
      context: .
      dockerfile: ctp_engine/Dockerfile
    container_name: ctp_engine
    restart: unless-stopped
    ports:
      - "127.0.0.1:9999:9999"
    volumes:
      - ./ctp_engine/.env:/app/.env:ro
      - ./ctp_engine/data:/app/data
      - ./ctp_engine/logs:/app/logs
```

---

## 4. 直接部署（无 Docker）

```bash
# 1. Python 3.12+
python3 --version

# 2. 安装依赖
pip install openctp-ctp tabulate python-dotenv

# 3. 配置 .env
cp ctp_engine/.env.example ctp_engine/.env
vim ctp_engine/.env

# 4. 前台运行
python ctp_engine/main.py

# 5. 后台运行（systemd 或 nohup）
nohup python ctp_engine/main.py > /dev/null 2>&1 &
```

---

## 5. 安全注意事项

| 项 | 说明 |
|------|------|
| **Console 端口** | Docker `-p 127.0.0.1:9999:9999` 仅监听本机。非 Docker 环境保持 `CTP_CONSOLE_BIND=127.0.0.1` |
| **远程访问** | 通过 SSH 登录服务器后 `nc localhost 9999`，或建 SSH 隧道 |
| **.env 文件** | 含明文密码，权限设为 `600`（`chmod 600 ctp_engine/.env`） |
| **防火墙** | 即使误配 `0.0.0.0`，云服务器安全组应阻止 9999 入站 |
| **日志** | 不记录密码，但可能含合约代码和行情数据，按需清理 |

### SSH 隧道连接 Console（从本地直连）

```bash
# 本地机器执行
ssh -L 9999:127.0.0.1:9999 user@your-server -N

# 本地另开终端
nc localhost 9999
```

---

## 6. 资源评估

| 指标 | 2C4G 云服务器实测 |
|------|:--:|
| **内存** | ~120MB（238 个合约全量订阅） |
| **CPU** | <5% 稳态 |
| **磁盘** | ~50-100MB/天（238 合约 × 全天 ticks），默认保留 120 天 ≈ 6-12GB |
| **网络** | CTP 行情 TCP 长连接，带宽极小 |

---

## 7. 监控与告警

### 进程存活

Docker 部署配了 `--restart unless-stopped` 和 `HEALTHCHECK`（每 30s 检查 9999 端口）。

进程内有断连重试保护：1 分钟内最多 3 次重连，超过则记录错误日志并退出，Docker 会自动重启容器。

### 日志关注

```bash
# 错误
docker logs ctp_engine 2>&1 | grep ERROR

# 断连
docker logs ctp_engine 2>&1 | grep "MD 断开"

# 落库速率
docker logs ctp_engine 2>&1 | grep "落库" | tail -5
```

### 磁盘

```bash
# 查看数据目录大小
du -sh ctp_engine/data/

# 清理过期数据（也可以在 Console 内用 expire 命令调整保留天数）
```

---

## 8. 常见问题

**Q: 容器启动后立刻退出？**
A: 检查 `ctp_engine/.env` 是否正确挂载，账号密码是否填写，`docker logs ctp_engine` 看具体错误。

**Q: `look` 命令中文乱码？**
A: Docker 内 locale 默认 UTF-8，正常不会有问题。如果本地 nc 乱码，检查终端编码。

**Q: 数据文件太大怎么办？**
A: Console 内执行 `expire 30` 缩短保留天数。旧数据会在下次每日清理时自动删除。

**Q: SimNow 只有买一/卖一数据？**
A: 正常现象。SimNow 模拟环境仅推送 1 档深度，实盘 CTP 才有完整 5 档。代码已完整支持 5 档，切换实盘后自动生效。
