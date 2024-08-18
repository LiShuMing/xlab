# WeChat Official Account H5 Deployment Guide

本文档说明如何把 Liminalis 部署到公网服务器，并接入微信公众号菜单与网页授权登录。

## 目标架构

```text
WeChat Official Account menu
  -> https://your-domain.example/api/wechat/official/entry/<tab>
  -> WeChat OAuth
  -> https://your-domain.example/api/wechat/official/oauth/callback
  -> /wechat/callback
  -> target H5 page
```

线上进程建议保持简单：

```text
Nginx 443/80
  -> 127.0.0.1:8010
  -> Liminalis FastAPI
     - /api/*
     - dist/index.html
PostgreSQL
Redis
```

## 前置要求

- 一台 Linux 服务器，建议 Ubuntu 22.04/24.04。
- 一个公网域名，例如 `liminalis.example.com`。
- 域名 DNS A 记录已经指向服务器公网 IP。
- 服务器安全组开放 `80/tcp` 和 `443/tcp`。
- 公众号后台可以配置网页授权域名。
- 如果服务器在中国大陆，域名通常需要完成 ICP 备案。

## 安装系统依赖

```bash
sudo apt update
sudo apt install -y git nginx python3.11 python3.11-venv nodejs npm postgresql redis-server
```

Vite 7 对 Node 版本有要求；如果系统 Node 过旧，建议安装 Node 20 或 22。

## 拉取代码

```bash
sudo mkdir -p /opt
sudo chown "$USER":"$USER" /opt
cd /opt
git clone https://github.com/LiShuMing/xlab.git
cd /opt/xlab/liminalis
```

## 安装应用依赖

```bash
cd /opt/xlab/liminalis
python3.11 -m venv .venv
. .venv/bin/activate
pip install -e .
pip install faiss-cpu

npm ci
npm run build
```

`faiss-cpu` 是当前 Ego import 链需要的依赖。

## 配置数据库

```bash
sudo -u postgres createuser liminalis
sudo -u postgres createdb liminalis_db -O liminalis
sudo -u postgres psql -c "ALTER USER liminalis WITH PASSWORD 'replace-with-db-password';"
```

## 配置环境变量

创建 `/opt/xlab/liminalis/.env.local`：

```bash
ENVIRONMENT=production
HOST=127.0.0.1
PORT=8010

SESSION_SECRET=replace-with-32-plus-random-chars

PGSQL_HOST=127.0.0.1
PGSQL_PORT=5432
PGSQL_USER=liminalis
PGSQL_PASSWORD=replace-with-db-password
PGSQL_DATABASE=liminalis_db

REDIS_URL=redis://127.0.0.1:6379/0

RADAR_ADMIN_USER=admin
RADAR_ADMIN_PASSWORD=replace-with-strong-password

LLM_API_KEY=your_api_key
LLM_BASE_URL=https://api.openai.com/v1
LLM_MODEL=gpt-4o

WECHAT_OFFICIAL_APP_ID=wx...
WECHAT_OFFICIAL_APP_SECRET=...
WECHAT_OFFICIAL_OAUTH_REDIRECT_URI=https://your-domain.example/api/wechat/official/oauth/callback
WECHAT_OFFICIAL_OAUTH_SCOPE=snsapi_base
```

线上不要设置 `WECHAT_OFFICIAL_MOCK_OPENID`。这个变量只用于本地联调。

## 运行数据库迁移

```bash
cd /opt/xlab/liminalis
. .venv/bin/activate
liminalis db upgrade
```

## 创建 systemd 服务

创建 `/etc/systemd/system/liminalis.service`：

```ini
[Unit]
Description=Liminalis FastAPI
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
WorkingDirectory=/opt/xlab/liminalis
EnvironmentFile=/opt/xlab/liminalis/.env.local
ExecStart=/opt/xlab/liminalis/.venv/bin/python -m backend.app
Restart=always
RestartSec=3
User=YOUR_LINUX_USER

[Install]
WantedBy=multi-user.target
```

替换 `YOUR_LINUX_USER` 为实际部署用户。

启动服务：

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now liminalis
sudo systemctl status liminalis
curl http://127.0.0.1:8010/health
```

查看日志：

```bash
sudo journalctl -u liminalis -f
```

## 配置 Nginx HTTP 反代

创建 `/etc/nginx/sites-available/liminalis`：

```nginx
server {
    listen 80;
    server_name your-domain.example;

    location / {
        proxy_pass http://127.0.0.1:8010;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

启用配置：

```bash
sudo ln -s /etc/nginx/sites-available/liminalis /etc/nginx/sites-enabled/liminalis
sudo nginx -t
sudo systemctl reload nginx
```

验证：

```bash
curl http://your-domain.example/health
```

## 申请 HTTPS 证书

使用 Let's Encrypt + Certbot：

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.example
```

验证 HTTPS：

```bash
curl https://your-domain.example/health
sudo certbot renew --dry-run
```

应用端口 `8010` 不需要对公网开放，只给本机 Nginx 访问。

## 配置微信公众号后台

进入公众号后台：

```text
设置与开发 -> 公众号设置 -> 功能设置
```

配置：

```text
网页授权域名：your-domain.example
```

如果后续要使用微信 JS-SDK 的分享、录音、拍照、上传图片等能力，再配置：

```text
JS接口安全域名：your-domain.example
```

当前 H5 登录和菜单访问主要依赖“网页授权域名”。

## 配置公众号菜单

公众号菜单选择“跳转网页”，URL 可以使用命名 tab 入口：

```text
代码实验室：
https://your-domain.example/api/wechat/official/entry/code-lab

博客：
https://your-domain.example/api/wechat/official/entry/blogs

数据库动态：
https://your-domain.example/api/wechat/official/entry/database-radar

价值投资：
https://your-domain.example/api/wechat/official/entry/value-invest

AI+Chat：
https://your-domain.example/api/wechat/official/entry/ai-chat

Ego Chat：
https://your-domain.example/api/wechat/official/entry/ego-chat
```

也可以直接传前端目标页：

```text
https://your-domain.example/api/wechat/official/oauth/start?target=/ego/chat
```

## 部署后验证

基础检查：

```bash
curl https://your-domain.example/health
curl -I https://your-domain.example/api/wechat/official/entry/ai-chat
```

第二个请求应返回 `307`，并跳转到微信 OAuth 地址。

在微信内打开菜单后，正常链路是：

```text
/api/wechat/official/entry/<tab>
  -> open.weixin.qq.com/connect/oauth2/authorize
  -> /api/wechat/official/oauth/callback
  -> /wechat/callback#?token=...
  -> target page
```

## 更新发布

```bash
cd /opt/xlab
git pull
cd /opt/xlab/liminalis

. .venv/bin/activate
pip install -e .
npm ci
npm run build
liminalis db upgrade

sudo systemctl restart liminalis
sudo journalctl -u liminalis -n 100 --no-pager
```

## 常见问题

### OAuth 回调失败

检查：

- `WECHAT_OFFICIAL_OAUTH_REDIRECT_URI` 是否为 HTTPS。
- 回调域名是否和公众号后台“网页授权域名”一致。
- 公众号 AppID/Secret 是否正确。
- 服务器是否可以访问 `api.weixin.qq.com`。

### 公众号菜单打开空白

检查：

- `npm run build` 是否已经生成 `dist/`。
- `https://your-domain.example/` 是否能返回页面。
- `https://your-domain.example/wechat/callback` 是否能返回前端页面。

### 登录成功后 API 返回 401

检查：

- `SESSION_SECRET` 是否在重启前后保持一致。
- 浏览器是否禁用了 localStorage。
- 回调 URL 是否包含 `/wechat/callback#?token=...`。

### 数据库表不存在

执行：

```bash
cd /opt/xlab/liminalis
. .venv/bin/activate
liminalis db upgrade
sudo systemctl restart liminalis
```

