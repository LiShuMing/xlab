# Liminalis Local Deployment Runbook

本文档记录当前 Liminalis 本地开发环境依赖的每个进程，以及它们的启动、检查与停止方式。

## 进程总览

| 进程 | 端口 | 路径 | 用途 |
| --- | --- | --- | --- |
| Liminalis client | 5173 | `/Users/lism/work/xlab/dbradar` | 主站、Logos/Praxis 页面、统一入口 |
| Liminalis API | 8010 | `/Users/lism/work/xlab/liminalis` | 统一 Python API 入口；当前提供 health、radar、admin、invest API |
| py-radar server | 5000 | `/Users/lism/work/xlab/python/projects/py-radar` | 旧《数据库动态》HTTP 服务；默认不再启动 |
| py-invest server | 8080 | `/Users/lism/work/xlab/python/projects/py-invest` | 旧价值投资 HTTP 服务；默认不再启动 |
| py-ego backend | 8000 | `/Users/lism/work/xlab/python/projects/py-ego/py-ego-miniapp` | py-ego H5 直接访问的 API |
| py-ego H5 | 5174 | `/Users/lism/work/xlab/python/projects/py-ego/miniprogram` | Ego 原生角色与对话页面 |

当前 Vite 代理关系：

```text
Liminalis /api/radar  -> http://localhost:8010/api/radar
Liminalis /api/admin  -> http://localhost:8010/api/admin
Liminalis /api/invest -> http://localhost:8010/api/invest
Liminalis /api/ego    -> http://localhost:8010/api/ego
Liminalis /api        -> http://localhost:5000
py-ego H5 API         -> http://localhost:8000/api
```

`Liminalis API` 是统一后端重构的目标入口。当前已接管 radar 只读 API、admin link ingestion、invest analysis、ego role list；ego chat 仍保留在原有 H5/backend 进程。可通过下面命令单独启动：

```bash
cd /Users/lism/work/xlab/liminalis
npm run api
# or
START_LIMINALIS_API=1 START_RADAR=0 START_INVEST=0 START_EGO_API=0 START_EGO_H5=0 npm run start
```

`START_RADAR` 默认已经关闭；如需启动旧 py-radar Flask 服务，可显式设置 `START_RADAR=1`。

`START_INVEST` 默认已经关闭；如需启动旧 py-invest Flask 服务，可显式设置 `START_INVEST=1`。当前 `/invest` 页面直接调用统一后端的 `/api/invest/analyze-stock`。

Phase 1 默认使用 `8010`，避免与现有 py-ego H5 API 的 `8000` 端口冲突。后续统一 API 接管更多能力后，可以通过 `LIMINALIS_API_PORT=8000` 切换。

构建后的单进程模式可直接运行：

```bash
cd /Users/lism/work/xlab/liminalis
./scripts/serve.sh
# or, after dependencies are already installed
npm run serve
```

该模式会由 FastAPI 同时服务 `/api/*` 与 `dist/index.html`，无需 Vite dev server。

## 环境配置

通用 LLM 配置优先放在 `~/.env`：

```bash
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_TIMEOUT=120
```

公众号 H5 登录需要配置公众号 AppID、Secret 和网页授权回调地址。回调地址必须与公众号后台“网页授权域名”匹配，线上应使用 HTTPS 域名：

```bash
WECHAT_OFFICIAL_APP_ID=wx...
WECHAT_OFFICIAL_APP_SECRET=...
WECHAT_OFFICIAL_OAUTH_REDIRECT_URI=https://your-domain.example/api/wechat/official/oauth/callback
WECHAT_OFFICIAL_OAUTH_SCOPE=snsapi_base
```

公众号菜单可指向命名 tab 入口：

```text
https://your-domain.example/api/wechat/official/entry/code-lab
https://your-domain.example/api/wechat/official/entry/blogs
https://your-domain.example/api/wechat/official/entry/database-radar
https://your-domain.example/api/wechat/official/entry/value-invest
https://your-domain.example/api/wechat/official/entry/ai-chat
https://your-domain.example/api/wechat/official/entry/ego-chat
```

也可以直接传前端目标页：`/api/wechat/official/oauth/start?target=/ego/chat`。

本地联调不访问微信接口时可使用 mock openid：

```bash
WECHAT_OFFICIAL_APP_ID=wx_local
WECHAT_OFFICIAL_OAUTH_REDIRECT_URI=http://localhost:8010/api/wechat/official/oauth/callback
WECHAT_OFFICIAL_MOCK_OPENID=local_openid_001
```

py-radar 也兼容这些变量：

```bash
DB_RADAR_API_KEY=your_api_key
DB_RADAR_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
DB_RADAR_MODEL=qwen-max
RADAR_ADMIN_USER=admin
RADAR_ADMIN_PASSWORD=change-me
RADAR_SESSION_SECRET=local-dev-radar-session-secret
```

## 启动顺序

建议按后端到前端启动：Liminalis API、py-ego backend、py-ego H5、Liminalis。

### 1. py-radar server

```bash
cd /Users/lism/work/xlab/python/projects/py-radar
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements.txt
python -m dbradar serve --host 127.0.0.1 --port 5000
```

检查：

```bash
curl http://localhost:5000/api/news
```

后台添加链接可走 UI，也可走 CLI：

```bash
cd /Users/lism/work/xlab/python/projects/py-radar
. .venv/bin/activate
python -m dbradar add-url "https://example.com/post" \
  --server-url http://localhost:5000 \
  --admin-user "$RADAR_ADMIN_USER" \
  --admin-password "$RADAR_ADMIN_PASSWORD"
```

### 2. py-invest server

```bash
cd /Users/lism/work/xlab/python/projects/py-invest
. .venv/bin/activate
python web/server.py 8080
```

检查：

```bash
curl http://localhost:8080/api/status
```

旧 py-invest HTTP 服务可按需启动；当前 Liminalis 默认通过统一后端 `/api/invest/*` 调用分析能力。

### 3. py-ego backend

py-ego H5 默认直连 `http://localhost:8000/api`：

```bash
cd /Users/lism/work/xlab/python/projects/py-ego/py-ego-miniapp
. .venv/bin/activate
DATABASE_URL=sqlite+aiosqlite:///./pyego_local.db \
REDIS_URL=memory:// \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Liminalis 当前通过统一后端 `/api/ego/roles` 读取角色列表；只有进入 py-ego H5 聊天时才需要这个 8000 后端。

检查：

```bash
curl http://localhost:8000/health
curl http://localhost:8000/api/roles
```

### 4. py-ego H5

```bash
cd /Users/lism/work/xlab/python/projects/py-ego/miniprogram
npm install
npm run dev:h5 -- --host 127.0.0.1 --port 5174
```

访问：

```text
http://127.0.0.1:5174/
http://127.0.0.1:5174/#/pages/chat/index?role_id=therapist
```

Liminalis `/ego` 页面点击角色后，会跳转到 `http://localhost:5174/#/pages/chat/index?role_id=<role>`。

### 5. Liminalis client

```bash
cd /Users/lism/work/xlab/dbradar
npm install
npm run dev
```

访问：

```text
http://localhost:5173/
http://localhost:5173/radar
http://localhost:5173/invest
http://localhost:5173/ego
```

构建检查：

```bash
cd /Users/lism/work/xlab/dbradar
npm run build
```

## 后台运行方式

本地长期运行时可以把日志和 PID 放到当前项目：

```bash
cd /Users/lism/work/xlab/dbradar
mkdir -p logs
```

示例：启动 Liminalis。

```bash
cd /Users/lism/work/xlab/dbradar
nohup npm run dev > logs/liminalis.log 2>&1 &
echo $! > logs/liminalis.pid
```

示例：启动 py-invest。

```bash
cd /Users/lism/work/xlab/python/projects/py-invest
nohup .venv/bin/python web/server.py 8080 > /Users/lism/work/xlab/dbradar/logs/py-invest.log 2>&1 &
echo $! > /Users/lism/work/xlab/dbradar/logs/py-invest.pid
```

同理可以为 py-radar、py-ego backend、py-ego H5 分别写入独立 log/pid 文件。

## 停止与排查

查看端口占用：

```bash
lsof -nP -iTCP -sTCP:LISTEN | rg ':(5000|5173|5174|8000|8080)'
```

按 PID 停止：

```bash
kill <pid>
```

如果使用上面的 PID 文件：

```bash
kill "$(cat logs/liminalis.pid)"
```

常见问题：

| 现象 | 检查 |
| --- | --- |
| `/radar` 没数据 | 确认统一后端 8010 正常，且 py-radar `data/items.duckdb` 或静态 feed 存在 |
| 后台添加链接失败 | 确认 `cache/` 目录存在，`RADAR_ADMIN_PASSWORD` 已配置，LLM 配置可用 |
| `/invest` 分析很慢 | 深度分析会调用多个 agent 和外部数据源；先用快速分析验证链路 |
| `/ego` 角色加载失败 | 确认统一后端 `8010 /api/ego/roles` 正常，且 py-ego role 定义可导入 |
| py-ego H5 登录后无响应 | 确认 `8000 /health` 正常，且 `src/api/request.js` 的 `BASE_URL` 指向正确后端 |

## 推荐后续整理

当前本地环境已经可以跑通，但进程数量偏多。后续可以把这些命令沉淀为：

1. `scripts/dev/start-all.sh`
2. `scripts/dev/stop-all.sh`
3. `scripts/dev/status.sh`
4. 一个统一的 `.env.local`，集中配置端口和后端 URL
