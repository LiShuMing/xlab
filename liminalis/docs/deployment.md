# Liminalis Local Deployment Runbook

本文档记录当前 Liminalis 本地开发环境依赖的每个进程，以及它们的启动、检查与停止方式。

## 进程总览

| 进程 | 端口 | 路径 | 用途 |
| --- | --- | --- | --- |
| Liminalis client | 5173 | `/Users/lism/work/xlab/dbradar` | 主站、Logos/Praxis 页面、统一入口 |
| py-radar server | 5000 | `/Users/lism/work/xlab/python/projects/py-radar` | 《数据库动态》feed、后台添加链接、DuckDB 数据 |
| py-invest server | 8080 | `/Users/lism/work/xlab/python/projects/py-invest` | 价值投资报告 API |
| py-ego backend | 8000 | `/Users/lism/work/xlab/python/projects/py-ego/py-ego-miniapp` | py-ego H5 直接访问的 API |
| py-ego backend for Liminalis proxy | 8090 | `/Users/lism/work/xlab/python/projects/py-ego/py-ego-miniapp` | Liminalis `/ego-api` 代理读取角色等能力 |
| py-ego H5 | 5174 | `/Users/lism/work/xlab/python/projects/py-ego/miniprogram` | Ego 原生角色与对话页面 |

当前 Vite 代理关系：

```text
Liminalis /api        -> http://localhost:5000
Liminalis /invest-api -> http://localhost:8080/api
Liminalis /ego-api    -> http://localhost:8090/api
py-ego H5 API         -> http://localhost:8000/api
```

如果只希望启动一个 py-ego backend，可以把 `dbradar/vite.config.js` 的 `/ego-api` target 改为 `http://localhost:8000`，或把 `py-ego/miniprogram/src/api/request.js` 的 `BASE_URL` 改为 `http://localhost:8090/api`。

## 环境配置

通用 LLM 配置优先放在 `~/.env`：

```bash
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_TIMEOUT=120
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

建议按后端到前端启动：py-radar、py-invest、py-ego backend、py-ego H5、Liminalis。

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

Liminalis 通过 `/invest-api` 调用该服务，例如 `/invest-api/status` 会转发到 `http://localhost:8080/api/status`。

### 3. py-ego backend

py-ego H5 默认直连 `http://localhost:8000/api`：

```bash
cd /Users/lism/work/xlab/python/projects/py-ego/py-ego-miniapp
. .venv/bin/activate
DATABASE_URL=sqlite+aiosqlite:///./pyego_local.db \
REDIS_URL=memory:// \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Liminalis 当前 `/ego-api` 代理到 `8090`。如果不改代理，需要再启动一个同代码服务：

```bash
cd /Users/lism/work/xlab/python/projects/py-ego/py-ego-miniapp
. .venv/bin/activate
DATABASE_URL=sqlite+aiosqlite:///./pyego_local.db \
REDIS_URL=memory:// \
python -m uvicorn app.main:app --host 127.0.0.1 --port 8090
```

检查：

```bash
curl http://localhost:8000/health
curl http://localhost:8090/health
curl http://localhost:8090/api/roles
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
lsof -nP -iTCP -sTCP:LISTEN | rg ':(5000|5173|5174|8000|8080|8090)'
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
| `/radar` 没数据 | 确认 `py-radar` 5000 已启动，`data/items.duckdb` 存在 |
| 后台添加链接失败 | 确认 `cache/` 目录存在，`RADAR_ADMIN_PASSWORD` 已配置，LLM 配置可用 |
| `/invest` 分析很慢 | 深度分析会调用多个 agent 和外部数据源；先用快速分析验证链路 |
| `/ego` 角色加载失败 | 确认 `8090 /api/roles` 正常，或把 `/ego-api` 代理改到 8000 |
| py-ego H5 登录后无响应 | 确认 `8000 /health` 正常，且 `src/api/request.js` 的 `BASE_URL` 指向正确后端 |

## 推荐后续整理

当前本地环境已经可以跑通，但进程数量偏多。后续可以把这些命令沉淀为：

1. `scripts/dev/start-all.sh`
2. `scripts/dev/stop-all.sh`
3. `scripts/dev/status.sh`
4. 一个统一的 `.env.local`，集中配置端口和后端 URL
