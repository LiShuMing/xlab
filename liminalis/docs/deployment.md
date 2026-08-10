# Liminalis Local Deployment Runbook

本文档记录当前 Liminalis 本地开发环境依赖的进程、启动方式和排查入口。

## 进程总览

| 进程 | 端口/入口 | 路径 | 用途 |
| --- | --- | --- | --- |
| Liminalis client | 5173 | 当前项目根目录 | Vite 前端开发入口，可在单端口模式关闭 |
| Liminalis API | 8010 | 当前项目根目录 | 统一 Python API，提供 health、radar、admin、invest、ego、wechat 和 `/llm-wiki/` 代理 |
| llm-wiki | Unix socket | `./llm-wiki` | 当前项目内的 Context Social Go Web 控制台，由 FastAPI 同源代理，不再暴露浏览器侧 TCP 端口 |
| PostgreSQL / Supabase | 5433 或远端 | Docker compose、外部 PG 或 Supabase | 业务数据存储，开发 compose 使用 pgvector 镜像 |
| Redis | 6380 | Docker compose 或外部 Redis | arq 后台任务队列 |

当前 Vite 代理关系：

```text
Liminalis /api/radar  -> http://localhost:8010/api/radar
Liminalis /api/admin  -> http://localhost:8010/api/admin
Liminalis /api/invest -> http://localhost:8010/api/invest
Liminalis /api/ego    -> http://localhost:8010/api/ego
Liminalis /api/wechat -> http://localhost:8010/api/wechat
Liminalis /llm-wiki  -> Unix socket -> llm-wiki Go Web
```

旧的独立 radar/invest Python 项目已经被吸收到 `backend/radar` 与 `backend/invest`，不再作为单独服务启动。

## 环境配置

本地开发服务可通过 compose 启动：

```bash
docker compose up -d postgres redis
```

匹配 compose 的本地环境变量：

```bash
PGSQL_HOST=localhost
PGSQL_PORT=5433
PGSQL_USER=liminalis
PGSQL_PASSWORD=liminalis
PGSQL_DATABASE=liminalis_db
REDIS_URL=redis://localhost:6380/0
```

远端 Supabase/Postgres 可以使用完整 DSN：

```bash
SUPABASE_DB_URL=postgresql://user:password@host:6543/postgres?sslmode=require
REDIS_URL=redis://...
```

共享 `~/.env` 中的 RDS/Supabase 风格配置也可以直接使用：

```bash
PSQL_URL=host-or-postgresql-dsn
PSQL_PORT=5432
PSQL_USER=...
PSQL_PASSWORD=...
PSQL_DEFAULT_DB=liminalis_db
```

当数据库已经被其他应用使用时，Liminalis 自有身份表使用 `liminalis_` 前缀，避免和既有 `users` 等通用表名冲突。

当前存储边界分三类：

- 业务数据库：统一通过 SQLAlchemy async session 访问 PostgreSQL/Supabase。
- 运行缓存：本地 HTTP/feed/cache 文件，只用于加速和重试，不作为业务事实来源。
- 静态快照：打包在前端中的只读数据，用于 Radar 无数据库数据时的降级展示。

旧 SQLite/DuckDB 文件仍保留为 CLI、导入导出和离线同步的 legacy compatibility，不再是 HTTP 主链路业务存储。

通用 LLM 配置优先放在 `~/.env`：

```bash
LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o
LLM_TIMEOUT=120
```

公众号 H5 登录需要配置公众号 AppID、Secret 和网页授权回调地址。线上应使用 HTTPS 域名：

```bash
WECHAT_OFFICIAL_APP_ID=wx...
WECHAT_OFFICIAL_APP_SECRET=...
WECHAT_OFFICIAL_OAUTH_REDIRECT_URI=https://your-domain.example/api/wechat/official/oauth/callback
WECHAT_OFFICIAL_OAUTH_SCOPE=snsapi_base
```

本地联调不访问微信接口时可使用 mock openid：

```bash
WECHAT_OFFICIAL_APP_ID=wx_local
WECHAT_OFFICIAL_OAUTH_REDIRECT_URI=http://localhost:8010/api/wechat/official/oauth/callback
WECHAT_OFFICIAL_MOCK_OPENID=local_openid_001
```

## 启动

推荐一键启动：

```bash
npm run start
```

脚本默认启动：

- Liminalis API: `http://localhost:8010/health`
- llm-wiki: `http://localhost:8010/llm-wiki/`，内部使用 Unix socket
- Liminalis client: `http://localhost:5173/`

只保留 8010 一个浏览器可访问端口：

```bash
npm run start:one-port
```

该模式会关闭 Vite dev server，只启动 FastAPI 8010 与不暴露 TCP 端口的 llm-wiki
Unix socket 进程。访问入口是 `http://localhost:8010/`。

需要前端热更新时使用：

```bash
npm run start:dev
```

只启动统一 API：

```bash
npm run api
```

构建后的单进程模式：

```bash
./scripts/serve.sh
# or, after dependencies are already installed
npm run serve
```

该模式由 FastAPI 同时服务 `/api/*` 与 `dist/index.html`，无需 Vite dev server。`/ai-chat`
通过 FastAPI 的 `/llm-wiki/` 同源入口访问 llm-wiki。当前 llm-wiki 仍是独立 Go
进程，但可以通过 Unix socket 接入，不需要额外 TCP 端口；后续若要真正单进程，需要把
llm-wiki 的 Go Web/API 迁移到统一后端。

单独启动 llm-wiki：

```bash
cd llm-wiki
CTX_WEB_UNIX_SOCKET=../.dev/llm-wiki.sock make web WEB_PROVIDER=llm DEMO_DATA=.demo-data
```

## 检查与停止

查看状态：

```bash
npm run check
npm run check:one-port
```

停止脚本启动的进程：

```bash
npm run stop
```

查看端口占用：

```bash
lsof -nP -iTCP -sTCP:LISTEN | rg ':(5173|8010|8787|5433|6380)'
```

健康检查：

```bash
curl http://localhost:8010/health
curl http://localhost:8010/health/deep
```

`/health` 是轻量进程检查；`/health/deep` 会报告数据库、LLM 配置和 llm-wiki 接入模式，
适合排查依赖状态。

## 常见问题

| 现象 | 检查 |
| --- | --- |
| `/radar` 没数据 | 确认统一后端 8010 正常，PostgreSQL 已迁移数据；无 PG 数据时会读取内置静态快照 |
| 后台添加链接失败 | 确认 PostgreSQL、Redis、管理员密码、LLM 配置可用 |
| `/invest` 分析很慢 | 深度分析会调用多个 agent、LLM 和外部行情源；先用快速分析验证链路 |
| `/ego` 登录/记录失败 | 确认 PostgreSQL 配置、迁移和 `SESSION_SECRET` |
| `/ai-chat` 未加载 | 确认 `llm-wiki` socket 正常，并检查 `http://localhost:8010/llm-wiki/` 代理入口 |
