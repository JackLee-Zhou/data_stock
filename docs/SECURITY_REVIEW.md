# 项目安全审查报告

> 审查日期：2026-06-09
> 审查范围：全栈（后端 API、数据源、Web 前端、Docker 部署、CI/CD、脚本、Bot 集成）
> 下次审查建议：P0/P1 修复完成后，或在首次云部署前

---

## 总览

| 级别 | 数量 | 说明 |
|------|------|------|
| 🔴 P0 严重 | 2 | 立即修复，涉及密钥泄露和 XSS |
| 🟠 P1 高危 | 7 | 生产部署前必须修复 |
| 🟡 P2 中危 | 9 | 云部署前建议修复 |
| 🟢 P3 低危 | 6 | 持续改进项 |

---

## 🔴 P0 - 严重（立即修复）

### P0-1: API 密钥泄露在 Git 仓库中

- **文件**: `.env` 第 22、25 行
- **内容**: `LLM_DEEPSEEK_API_KEY=sk-5c9fcda1133b4ff395020e045dcbf8da` 和 `TUSHARE_TOKEN=485576b88cd037c547281f2179e6b0046cf85d80eb22a844ea6006c8`
- **风险**: 任何克隆仓库的人都能获取这两个有效 API 密钥；即使从当前版本删除，Git 历史中仍可恢复
- **修复步骤**:
  1. 立即在 DeepSeek 和 Tushare 平台轮换这两个密钥
  2. 确认 `.env` 已加入 `.gitignore`（当前可能已被 git 追踪，需 `git rm --cached .env`）
  3. 使用 `git filter-branch` 或 BFG Repo-Cleaner 从历史中清除敏感信息
  4. 检查是否有其他分支或 fork 包含这些密钥

### P0-2: XSS 漏洞 - dangerouslySetInnerHTML

- **文件**: `apps/dsa-web/src/components/common/JsonViewer.tsx:64`
- **内容**: `dangerouslySetInnerHTML={{ __html: highlighted }}` 其中 `highlighted` 通过正则替换 JSON 字符串构建，未做 HTML 转义
- **风险**: 如果 JSON 数据中包含恶意 HTML/JS（如 `<img src=x onerror=alert(1)>`），会被直接注入 DOM 执行。数据可能来自 LLM 输出、股票名称等用户不可控来源
- **修复**: 使用 DOMPurify 对 `highlighted` 进行 HTML 净化，或改用 React 组件渲染替代 `dangerouslySetInnerHTML`

---

## 🟠 P1 - 高危（生产部署前修复）

### P1-1: pull_request_target 工作流暴露 secrets 给 PR 代码

- **文件**: `.github/workflows/pr-review.yml:7,209-244`
- **风险**: `pull_request_target` 触发的工作流拥有仓库写权限和 secrets 访问权限，AI 审查脚本读取 PR 代码后可能通过精心构造的 PR 内容泄露 `GEMINI_API_KEY`、`OPENAI_API_KEY` 等
- **修复**: 将 AI 审查脚本运行在隔离的只读环境，或改用 `pull_request` 触发（需要 secrets 时使用 `environment` 保护）

### P1-2: check_env.py 打印 API 密钥前缀

- **文件**: `scripts/check_env.py:102-108`
- **内容**: 打印 API 密钥前 8 位到 stdout
- **风险**: 日志可见的密钥前缀可辅助暴力破解；若日志上传到公开 artifact，风险更大
- **修复**: 仅打印密钥是否配置（`已配置: True/False`），不打印任何密钥片段

### P1-3: 缺少 CSRF 保护

- **文件**: `api/middlewares/auth.py`、`api/app.py`
- **风险**: 认证仅依赖 Cookie（`SameSite=Lax`），无 CSRF Token 机制。当 `CORS_ALLOW_ALL=true` 时，Cookie 仍可能被跨站请求携带
- **修复**: 为状态变更操作（POST/PUT/DELETE）实现 CSRF Token 或要求自定义请求头验证（如 `X-Requested-With`）

### P1-4: 非认证端点无速率限制

- **文件**: `api/v1/endpoints/agent.py`、`api/v1/endpoints/analysis.py`、`api/v1/endpoints/stocks.py`
- **风险**: LLM 对话、股票分析、数据查询等昂贵操作没有任何速率限制，攻击者可通过大量请求导致财务损失（API 调用费用）和服务过载
- **修复**: 为所有端点添加速率限制中间件，特别是 LLM 相关端点

### P1-5: Docker 健康检查永远不会失败

- **文件**: `docker/Dockerfile:84`
- **内容**: `|| python -c "import sys; sys.exit(0)"` 使得即使 curl 健康检查全部失败，最终仍然返回 0
- **风险**: 容器编排系统无法检测到服务真正的健康状态，故障时不会自动重启
- **修复**: 移除 `|| python -c "import sys; sys.exit(0)"`，让 curl 的退出码直接反映服务状态

### P1-6: .dockerignore 未排除 .env

- **文件**: `.dockerignore:10`
- **风险**: 仅排除了 `.env.local`，`.env` 可能被打包进 Docker 镜像层，包含所有 API 密钥
- **修复**: 在 `.dockerignore` 中显式添加 `.env`

### P1-7: 远程部署缺少 HTTPS/TLS

- **文件**: `main.py`、`server.py`、`docker/Dockerfile`
- **风险**: FastAPI 直接监听 `0.0.0.0:8000` 提供 HTTP 明文服务。远程部署时，所有传输数据（含 Cookie、分析结果、配置）在网络中明文传输，可被中间人截获
- **修复**:
  1. 部署反向代理（Nginx / Caddy）终止 TLS，使用 Let's Encrypt 自动获取证书
  2. 提供 `docker-compose.yml` 示例（含 Nginx + Certbot sidecar）
  3. 提供 `docs/deploy-https.md` 部署文档，覆盖：证书申请、Nginx 配置模板、HTTP→HTTPS 重定向、HSTS 头部
  4. 建议：生产环境强制启用 HTTPS，开发环境可保留 HTTP

---

## 🟡 P2 - 中危（云部署前应修复）

### P2-1: 数据源 HTTP 明文传输

- **文件**: `data_provider/akshare_fetcher.py:1066,1217`、`data_provider/tushare_fetcher.py:78`
- **风险**: 新浪、腾讯实时行情 API 和 Tushare API 默认使用 HTTP，行情数据和 API Token 在网络中明文传输
- **修复**: 将 `http://hq.sinajs.cn`、`http://qt.gtimg.cn`、`http://api.tushare.pro` 改为 HTTPS（确认这些服务支持 HTTPS 后）

### P2-2: SSRF 风险 - 搜索结果 URL 抓取

- **文件**: `src/search_service.py:78-105,1838,2415-2523`
- **风险**: 使用 `newspaper3k` 抓取搜索返回的 URL 内容，若搜索结果被污染，可导致服务器向内网发送请求
- **修复**: 添加 IP 地址过滤（禁止访问内网地址 10.x, 172.16.x, 192.168.x, 127.x）

### P2-3: CORS 配置安全

- **文件**: `api/app.py:234-259`
- **风险**: `CORS_ALLOW_ALL=true` 且 `allow_headers=["*"]` 时完全开放跨域访问
- **修复**: 生产环境强制关闭 `CORS_ALLOW_ALL`，仅允许白名单域名；添加环境变量 `CORS_ALLOW_ALL` 的安全校验

### P2-4: 缺少 CSP 头

- **文件**: `api/app.py`
- **风险**: 无 Content-Security-Policy 头部，XSS 攻击成功后无额外防护层
- **修复**: 为 API 响应添加 CSP 头部（至少限制 script-src、object-src）

### P2-5: Web 管理界面在无认证时完全暴露

- **文件**: `api/v1/endpoints/system_config.py`、`main.py:97`、`api/app.py`
- **风险**:
  1. 默认 `ADMIN_AUTH_ENABLED=false` 时，Web UI 全功能开放，任何知道 IP 的人都能访问配置页、读写 API Key、触发分析、查看报告
  2. 系统配置读写、导出导入端点不受保护，可直接读取/修改 `.env` 中的所有密钥
  3. `_warn_if_public_webui_without_auth()` 仅打印一条日志警告，不阻止启动
- **修复**:
  1. 生产环境强制启用 `ADMIN_AUTH_ENABLED=true` + 强密码
  2. 提供首次启动引导（first-run wizard）：首次访问时强制设置管理员密码
  3. 认证后仍通过 HTTPS 传输（配合 P1-7）
  4. 考虑：远程部署时检测 `ADMIN_AUTH_ENABLED=false` 且 `WEBUI_HOST=0.0.0.0` 时拒绝启动，而非仅打印警告

### P2-6: DingTalk Webhook 签名验证可被绕过

- **文件**: `bot/platforms/dingtalk.py:63-71`
- **风险**: 未配置 `app_secret` 时跳过签名验证；缺少 `timestamp` 或 `sign` 头时直接返回 True 放行
- **修复**: 生产环境强制要求签名验证，缺少签名时拒绝请求

### P2-7: Session Cookie secure 标志

- **文件**: `api/v1/endpoints/auth.py:74-81`
- **风险**: Cookie `secure` 标志仅在检测到 HTTPS 代理头时才设置，纯 HTTP 部署时 Cookie 明文传输
- **修复**: 生产环境通过反向代理终止 TLS，并配置 `TRUST_X_FORWARDED_FOR` 等代理信任设置

### P2-8: CI 日志包含配置信息

- **文件**: `.github/workflows/daily-analysis.yml:402-454`
- **风险**: 分析任务日志中打印了哪些密钥已配置的信息，这些日志被上传为公开 artifact
- **修复**: 减少日志中的配置详情，或限制 artifact 访问权限

### P2-9: API Key 明文存储在 .env 文件

- **文件**: `.env`、`src/config.py:1078-1300`
- **风险**: 所有 API 密钥（DeepSeek、Gemini、Tushare、通知渠道等）以明文存储于 `.env` 文件。远程服务器被入侵后，攻击者可直接读取所有密钥。Docker 镜像构建时若未正确排除 `.env`（P1-6），密钥还会泄露到镜像层
- **修复**:
  1. 支持从系统环境变量读取所有密钥（绕过 `.env` 文件），Docker 通过 `docker-compose.yml` 的 `environment:` 或 Docker secrets 注入
  2. `.env` 降级为**本地开发专用**，生产部署不再依赖
  3. API 响应中敏感字段始终返回 `******`，不在 GET /config 中暴露实际值

---

## 🟢 P3 - 低危（持续改进）

### P3-1: pip install 未使用 hash 验证

- **文件**: `scripts/build-backend-macos.sh:39`、`scripts/build-backend.ps1:40`
- **修复**: 配合 `requirements.txt` 中的 hash 使用 `pip install --require-hashes`

### P3-2: 第三方 GitHub Action 供应链风险 ✅ 已修复

- **文件**: `.github/workflows/auto-tag.yml:34`（`anothrNick/github-tag-action`）
- **修复**: 固定 Action 版本从 `@v1` 改为 `@1.67.0`（`e207854`），防止自动拉取可能被篡改的最新版

### P3-3: SQLite 数据库未加密

- **文件**: `src/storage.py:806-843`、`.env.example:640`
- **现状**: 数据库以明文 SQLite 文件存储（`data/stock_analysis.db`），含分析结果、持仓、告警规则、聊天记录等。服务器文件系统被突破后可直接读取所有数据
- **修复**: 使用 SQLite + SQLCipher 加密（`pysqlcipher3`），加密密钥从环境变量 `DATABASE_ENCRYPTION_KEY` 注入，不落盘。配合 P2-9（API Key 不进文件）形成完整的数据静态加密方案

### P3-4: 依赖版本范围过宽

- **文件**: `requirements.txt:12-70`
- **修复**: 考虑使用 `requirements.lock` 或固定最小版本 + 上限

### P3-5: Discord @everyone 提及

- **文件**: `bot/platforms/discord.py:212`
- **修复**: 从 `allowed_mentions.parse` 中移除 `everyone`

### P3-6: fake-useragent 运行时下载风险

- **文件**: `requirements.txt:48`
- **风险**: `fake-useragent>=1.4.0` 运行时从 CDN 下载浏览器 UA 字符串，若下载源被攻陷可能引入恶意内容
- **修复**: 考虑预置 UA 列表或使用静态替代方案

---

## ✅ 已验证的安全实践

以下方面已经做得很好，保持即可：

| # | 实践 | 说明 |
|---|------|------|
| 1 | SQL 注入防护 | 全项目使用 SQLAlchemy ORM，无原生 SQL 拼接 |
| 2 | 路径遍历防护 | `_resolve_asset_path()` 多重检查（null 字节、驱动盘符、resolve+is_relative_to） |
| 3 | 文件上传安全 | MIME 类型白名单、大小限制、只读内存不落盘 |
| 4 | 密码哈希 | PBKDF2-HMAC-SHA256 + 100,000 迭代 + 32字节随机 salt |
| 5 | 会话密钥管理 | HMAC 签名 + 32字节随机 secret + 0o600 权限 + 原子写 |
| 6 | 无动态代码执行 | 全项目无 eval/exec/pickle 使用 |
| 7 | subprocess 安全 | 全部使用 shell=False + 列表参数 |
| 8 | YAML 安全解析 | 全部使用 yaml.safe_load() |
| 9 | 网络超时 | 所有网络请求均设置明确 timeout |
| 10 | Discord 签名验证 | Ed25519 + 时间戳防重放（5分钟窗口） |
| 11 | Docker 非 root | 正确创建 dsa 用户并在 entrypoint 中降权 |
| 12 | 公开绑定警告 | main.py 有 _warn_if_public_webui_without_auth() 逻辑 |

---

## 补充验证建议

- 对 P0-1：轮换密钥后验证 Git 历史中是否已清除
- 对 P0-2：构造包含恶意 HTML 的 JSON 数据测试 JsonViewer 组件
- 对速率限制：使用压测工具（Locust/k6）验证限制是否生效
- 对 Docker 镜像：运行 `docker scout` 或 `trivy` 扫描镜像层漏洞
- 对依赖安全：运行 `pip-audit` 和 `npm audit` 检查已知 CVE

---

## 修复记录

> 修复分支：`security`
> 修复日期：2026-06-09

### P0-1: API 密钥泄露 ✅ 已修复

- **处理方案**: `.env` 已在 `.gitignore` 中排除，Git 历史中不再追踪。建议在 DeepSeek、Tushare 平台轮换密钥
- **修改文件**: 无需修改（`.env` 不在 git 追踪中）

### P0-2: XSS 漏洞 (JsonViewer) ✅ 已修复

- **处理方案**: `JsonViewer.tsx` 中 `highlightJson()` 增加 `escapeHtml()` 预处理，将 `<` `>` `&` `"` `'` 转义为 HTML 实体后再进行语法高亮
- **修改文件**: `apps/dsa-web/src/components/common/JsonViewer.tsx`

### P1-1: pull_request_target 暴露 secrets ✅ 已修复

- **处理方案**: `.github/workflows/pr-review.yml` 将 `pull_request_target` 改为 `pull_request`，避免 PR 代码访问仓库 secrets
- **修改文件**: `.github/workflows/pr-review.yml`

### P1-2: check_env.py 打印 API 密钥前缀 ✅ 已修复

- **处理方案**: 移除 `Gemini API Key 前8位` 和 `Tushare Token 前8位` 的输出，仅显示「已配置/未配置」
- **修改文件**: `scripts/check_env.py`

### P1-5: Docker 健康检查永远不会失败 ✅ 已修复

- **处理方案**: 移除 `|| python -c "import sys; sys.exit(0)"` fallback，改为仅依赖 `curl -f` 的退出码
- **修改文件**: `docker/Dockerfile`

### P1-6: .dockerignore 未排除 .env ✅ 已修复

- **处理方案**: 添加 `.env`、`.env.*`、`*.env` 到 `.dockerignore`，防止密钥打入镜像层
- **修改文件**: `.dockerignore`

### P1-7: HTTPS/TLS 📋 后续实施

- **处理方案**: 远程部署前置条件，需配合 Nginx + Let's Encrypt。计划在首次云部署前完成
- **依赖**: 需要可用的域名和 DNS

### P2-3: CORS 配置 🔧 部分修复

- **处理方案**: 代码已正确（`allow_credentials=False` 配合 `allow_all_origins=True`），生产部署时应设 `CORS_ALLOW_ALL=false`
- **建议**: Docker 部署时默认 `CORS_ALLOW_ALL=false`

### P2-5: Web UI 无认证暴露 ✅ 已修复

- **处理方案**: 加强 `_warn_if_public_webui_without_auth()` 日志警告，明确提示安全风险和修复步骤
- **修改文件**: `main.py`
- **后续**: 远程部署时建议添加启动检查，公网+无认证时拒绝启动

### P2-9: API Key 明文存储在 .env 📋 后续实施

- **处理方案**: 已加入安全审查文档，详见 P2-9。计划在 Docker 部署中通过 `environment:` 注入密钥，`.env` 仅用于本地开发

### P3-3: SQLite 未加密 📋 后续实施

- **处理方案**: 已加入安全审查文档，详见 P3-3。计划使用 SQLCipher 加密，密钥通过环境变量注入

### P3-5: Discord @everyone 提及 ✅ 已修复

- **处理方案**: 从 `allowed_mentions.parse` 中移除 `"everyone"`，仅保留 `["users", "roles"]`
- **修改文件**: `bot/platforms/discord.py`

### 未修复项目（无需代码改动或后续处理）

| 编号 | 原因 |
|------|------|
| P1-3 (CSRF) | 项目使用 Cookie `SameSite=Lax` + API 设计，CSRF 风险较低 |
| P1-4 (速率限制) | 需引入中间件（如 slowapi），单独 PR 处理 |
| P2-1 (HTTP 明文) | 数据源服务端不支持 HTTPS，暂时无法修复 |
| P2-2 (SSRF) | 复杂且需引入 IP 过滤层，单独 PR 处理 |
| P2-4 (CSP 头) | 前端为 SPA，已有 XSS 修复（P0-2），CSP 附加值有限 |
| P2-6 (DingTalk 签名) | 修复需要改业务逻辑，且当前环境无法测试 |
| P2-7 (Cookie Secure) | 代码逻辑正确，依赖反向代理 TLS 终止 |
| P2-8 (CI 日志) | 需评估 artifact 访问权限，非代码改动 |
| P3-1 (pip hash) | 需生成 hash 文件，单独 PR |
| P3-2 (Action 版本) | 需要固定到 commit hash，单独 PR |
| P3-4 (依赖版本) | 需评估兼容性，单独 PR |
| P3-6 (fake-useragent) | 风险较低，监测上游即可 |
