# 阿里云 ECS 部署指南

本文档介绍如何在阿里云 ECS 上部署 Daily DB Radar 服务。

## 目录

- [快速开始](#快速开始)
- [阶段 1：基础部署](#阶段-1基础部署)
- [阶段 2：HTTPS 配置](#阶段-2https-配置)
- [阶段 3：数据持久化](#阶段-3数据持久化)
- [阶段 4：异步队列](#阶段-4异步队列)
- [运维指南](#运维指南)

---

## 快速开始

### 1. 创建 ECS 实例

**推荐配置**（起步阶段）：
- **实例规格**：ecs.t6-c1m2.large（2核 4G）
- **操作系统**：Ubuntu 22.04 LTS 64位
- **存储**：40GB ESSD 云盘
- **带宽**：按流量计费 100Mbps（约 ¥80/月）
- **安全组**：开放 22(SSH), 80(HTTP), 443(HTTPS)

**购买链接**：[阿里云 ECS 控制台](https://ecs.console.aliyun.com/)

### 2. 环境准备

```bash
# SSH 登录服务器
ssh root@<your-ecs-ip>

# 更新系统
apt update && apt upgrade -y

# 安装 Docker
curl -fsSL https://get.docker.com | sh
systemctl enable docker && systemctl start docker

# 安装 Docker Compose
apt install -y docker-compose-plugin

# 验证安装
docker --version
docker compose version
```

### 3. 部署应用

```bash
# 创建工作目录
mkdir -p /opt/py-radar && cd /opt/py-radar

# 克隆代码
git clone <your-repo-url> .

# 配置环境变量
cat > .env << 'EOF'
LLM_API_KEY=your-dashscope-api-key
LLM_BASE_URL=https://dashscope.aliyuncs.com/compatible-mode/v1
LLM_MODEL=qwen-turbo
LLM_TIMEOUT=300
EOF

# 启动服务
docker compose up -d

# 查看日志
docker compose logs -f
```

### 4. 验证部署

```bash
# 检查服务状态
curl http://localhost:5000/api/news

# 查看 Web 界面
# 浏览器访问：http://<your-ecs-ip>:5000
```

---

## 阶段 1：基础部署

### 目录结构

```
/opt/py-radar/
├── docker-compose.yml      # Docker Compose 配置
├── Dockerfile              # 镜像构建文件
├── .env                    # 环境变量（保密）
├── data/                   # 数据持久化目录
│   ├── out/               # 报告输出
│   ├── cache/             # 缓存数据
│   └── logs/              # 日志文件
└── scripts/
    └── deploy.sh          # 部署脚本
```

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libxml2-dev \
    libxslt1-dev \
    && rm -rf /var/lib/apt/lists/*

# 复制依赖文件
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 安装应用
RUN pip install -e .

# 创建数据目录
RUN mkdir -p /app/out /app/cache

EXPOSE 5000

CMD ["dbradar", "serve", "--host", "0.0.0.0", "--port", "5000"]
```

### docker-compose.yml

```yaml
version: '3.8'

services:
  web:
    build: .
    image: py-radar:latest
    container_name: py-radar-web
    command: dbradar serve --host 0.0.0.0 --port 5000
    ports:
      - "5000:5000"
    volumes:
      - ./data/out:/app/out
      - ./data/cache:/app/cache
      - ./data/logs:/var/log
    env_file:
      - .env
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:5000/api/news"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s

  cron:
    build: .
    image: py-radar:latest
    container_name: py-radar-cron
    command: >
      sh -c "
        echo '0 6 * * * cd /app && dbradar run --top-k 20 --language zh >> /var/log/cron.log 2>&1' | crontab - &&
        cron -f
      "
    volumes:
      - ./data/out:/app/out
      - ./data/cache:/app/cache
      - ./data/logs:/var/log
    env_file:
      - .env
    restart: unless-stopped
    depends_on:
      - web
```

### 部署脚本

创建 `scripts/deploy.sh`：

```bash
#!/bin/bash
set -e

PROJECT_DIR="/opt/py-radar"
BACKUP_DIR="/opt/backups/py-radar"

echo "=== Daily DB Radar Deployment ==="

# 进入项目目录
cd $PROJECT_DIR

# 备份当前数据（保留最近7天）
echo "[1/6] Backing up data..."
mkdir -p $BACKUP_DIR
tar czf $BACKUP_DIR/backup-$(date +%Y%m%d-%H%M%S).tar.gz data/ 2>/dev/null || true
find $BACKUP_DIR -name "backup-*.tar.gz" -mtime +7 -delete

# 拉取最新代码
echo "[2/6] Pulling latest code..."
git fetch origin
git reset --hard origin/main

# 检查环境变量
echo "[3/6] Checking environment..."
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    exit 1
fi

# 构建镜像
echo "[4/6] Building Docker image..."
docker compose build --no-cache

# 停止旧服务
echo "[5/6] Stopping old services..."
docker compose down

# 启动新服务
echo "[6/6] Starting new services..."
docker compose up -d

# 健康检查
echo "Waiting for health check..."
sleep 5
if curl -sf http://localhost:5000/api/news > /dev/null; then
    echo "✓ Deployment successful!"
    echo "  Web: http://$(curl -s ifconfig.me):5000"
else
    echo "✗ Health check failed!"
    docker compose logs --tail=50
    exit 1
fi
```

赋予执行权限：
```bash
chmod +x scripts/deploy.sh
```

---

## 阶段 2：HTTPS 配置

### 使用阿里云 SSL 证书

1. **申请免费证书**
   - 访问 [SSL 证书控制台](https://yundun.console.aliyun.com/?p=cas)
   - 申请「个人测试证书（免费版）」
   - 验证域名所有权

2. **下载证书**
   - 格式选择：Nginx
   - 上传到服务器：`/opt/py-radar/ssl/`

3. **配置 Nginx**

创建 `nginx.conf`：

```nginx
server {
    listen 80;
    server_name radar.yourdomain.com;
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl;
    server_name radar.yourdomain.com;

    ssl_certificate /etc/nginx/ssl/cert.pem;
    ssl_certificate_key /etc/nginx/ssl/key.pem;
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers HIGH:!aNULL:!MD5;

    # 安全响应头
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;
    add_header X-XSS-Protection "1; mode=block" always;

    # Gzip 压缩
    gzip on;
    gzip_types text/plain text/css application/json application/javascript;

    location / {
        proxy_pass http://py-radar-web:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
}
```

更新 `docker-compose.yml` 添加 Nginx：

```yaml
  nginx:
    image: nginx:alpine
    container_name: py-radar-nginx
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/conf.d/default.conf:ro
      - ./ssl:/etc/nginx/ssl:ro
    depends_on:
      - web
    restart: unless-stopped
```

---

## 阶段 3：数据持久化

### 使用阿里云 RDS PostgreSQL

1. **创建 RDS 实例**
   - 类型：PostgreSQL 14
   - 规格：2核 4G（基础版）
   - 存储：100GB
   - 网络：与 ECS 同 VPC

2. **创建数据库用户**

```sql
CREATE DATABASE dbradar;
CREATE USER dbradar WITH PASSWORD 'your-password';
GRANT ALL PRIVILEGES ON DATABASE dbradar TO dbradar;
```

3. **配置连接**

更新 `.env`：
```bash
DATABASE_URL=postgresql://dbradar:password@rm-xxx.mysql.rds.aliyuncs.com:5432/dbradar
```

### 使用阿里云 OSS

1. **创建 Bucket**
   - 名称：`py-radar-reports`
   - 地域：与 ECS 相同
   - 权限：私有

2. **配置访问密钥**

更新 `.env`：
```bash
OSS_ACCESS_KEY_ID=your-access-key
OSS_ACCESS_KEY_SECRET=your-secret
OSS_BUCKET=py-radar-reports
OSS_ENDPOINT=oss-cn-hangzhou.aliyuncs.com
```

---

## 阶段 4：异步队列

### 使用阿里云 Redis

1. **创建 Redis 实例**
   - 版本：Redis 6.0
   - 规格：1GB 主从版
   - 网络：与 ECS 同 VPC

2. **配置 Celery**

更新 `docker-compose.yml`：

```yaml
  worker:
    build: .
    image: py-radar:latest
    container_name: py-radar-worker
    command: celery -A dbradar.tasks worker --loglevel=info
    env_file:
      - .env
    depends_on:
      - redis
    restart: unless-stopped

  beat:
    build: .
    image: py-radar:latest
    container_name: py-radar-beat
    command: celery -A dbradar.tasks beat --loglevel=info
    env_file:
      - .env
    depends_on:
      - redis
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    container_name: py-radar-redis
    volumes:
      - ./data/redis:/data
    restart: unless-stopped
```

---

## 运维指南

### 日常检查

```bash
# 查看服务状态
docker compose ps

# 查看日志
docker compose logs -f web
docker compose logs -f cron

# 查看资源使用
docker stats

# 检查磁盘空间
df -h
```

### 备份策略

```bash
# 手动备份数据
tar czf backup-$(date +%Y%m%d).tar.gz /opt/py-radar/data/

# 自动备份脚本（添加到 crontab）
0 2 * * * /opt/py-radar/scripts/backup.sh
```

### 升级维护

```bash
# 1. 备份数据
./scripts/backup.sh

# 2. 拉取更新
git pull origin main

# 3. 重新部署
./scripts/deploy.sh

# 4. 验证服务
curl -f http://localhost:5000/api/news
```

### 故障排查

| 问题 | 排查命令 | 解决方案 |
|------|---------|---------|
| 服务无法启动 | `docker compose logs` | 检查 .env 配置 |
| LLM 超时 | `docker compose logs cron` | 增加 LLM_TIMEOUT |
| 磁盘满 | `df -h` | 清理旧报告 |
| 内存不足 | `free -h` | 升级 ECS 配置 |

### 监控告警

建议配置阿里云云监控：
- CPU 使用率 > 80%
- 内存使用率 > 80%
- 磁盘使用率 > 85%
- 服务端口 5000 不可访问

---

## 成本优化

| 阶段 | 配置 | 预估月费用 |
|------|------|-----------|
| 起步 | ECS 2核4G + 40G 云盘 | ¥150-200 |
| 生产 | ECS 2核4G + RDS + Redis + OSS | ¥400-600 |
| 高可用 | SLB + 2×ECS + 集群版 RDS | ¥1000+ |

**省钱技巧**：
- 使用抢占式实例（可节省 50-70%）
- 购买 1 年/3 年包年包月
- 使用 OSS 低频访问存储旧报告

---

## 参考链接

- [阿里云 ECS 文档](https://help.aliyun.com/document_detail/25367.html)
- [阿里云 RDS 文档](https://help.aliyun.com/document_detail/26092.html)
- [Docker 官方文档](https://docs.docker.com/)
