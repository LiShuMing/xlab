# PyEgo MiniApp - 阿里云 ECS 部署方案

## 架构概览

```
┌─────────────────────────────────────────────────────────────────┐
│                         用户访问层                                │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────────────────┐  │
│  │  微信小程序  │  │   Web 浏览器  │  │      微信开发者工具       │  │
│  └──────┬──────┘  └──────┬──────┘  └────────────┬────────────┘  │
└─────────┼────────────────┼──────────────────────┼───────────────┘
          │                │                      │
          └────────────────┴──────────────────────┘
                             │
                             ▼ HTTPS (443)
┌─────────────────────────────────────────────────────────────────┐
│                      阿里云 ECS 服务器                            │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                    Nginx (Docker)                        │   │
│  │  • HTTPS 终止        • 反向代理        • 静态文件服务      │   │
│  │  • 速率限制          • Gzip 压缩       • 安全头           │   │
│  └─────────────────────────┬───────────────────────────────┘   │
│                            │                                    │
│  ┌─────────────────────────▼───────────────────────────────┐   │
│  │                   FastAPI 应用 (Docker)                   │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────────┐   │   │
│  │  │   API 路由   │  │   业务逻辑   │  │    核心模块      │   │   │
│  │  │  • 用户认证   │  │  • 记录服务   │  │  • MemoryStore  │   │   │
│  │  │  • 聊天会话   │  │  • 聊天服务   │  │  • RoleManager  │   │   │
│  │  │  • 文件上传   │  │  • 角色服务   │  │  • LLM Client   │   │   │
│  │  └─────────────┘  └─────────────┘  └─────────────────┘   │   │
│  └───────────────────────────────────────────────────────────┘   │
│                                                                   │
│  ┌─────────────────────────┐  ┌───────────────────────────────┐ │
│  │   PostgreSQL + pgvector  │  │          Redis                │ │
│  │  • 用户数据              │  │  • Session 缓存               │ │
│  │  • 聊天记录              │  │  • 速率限制计数               │ │
│  │  • 语义记忆 (向量)        │  │  • JWT 黑名单                 │ │
│  │  • 文件元数据            │  │  • 热点数据缓存               │ │
│  └─────────────────────────┘  └───────────────────────────────┘ │
│                                                                   │
│  ┌───────────────────────────────────────────────────────────┐ │
│  │              阿里云 OSS (文件存储)                          │ │
│  │  • 用户上传图片        • 语音文件备份        • CDN 加速      │ │
│  └───────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

## 服务器规格建议

| 阶段 | 配置 | 月成本 | 适用场景 |
|------|------|--------|----------|
| **开发测试** | 1vCPU 2GB, 40GB SSD | ~80 元 | 个人开发、功能测试 |
| **MVP 上线** | 2vCPU 4GB, 80GB SSD | ~150 元 | 小范围用户 (< 500) |
| **初期增长** | 4vCPU 8GB, 160GB SSD | ~300 元 | 中等规模 (< 2000) |
| **业务扩展** | 8vCPU 16GB + SLB | ~800 元 | 大规模用户 |

## 目录结构

```
deploy/
├── README.md                 # 部署文档
├── docker-compose.yml        # 容器编排配置
├── docker-compose.prod.yml   # 生产环境覆盖配置
├── Dockerfile                # 应用镜像构建
├── Dockerfile.nginx          # Nginx 镜像构建
├── config/
│   ├── nginx.conf            # Nginx 主配置
│   ├── nginx-app.conf        # 应用站点配置
│   └── supervisord.conf      # 进程管理配置
├── scripts/
│   ├── init-server.sh        # 服务器初始化脚本
│   ├── deploy.sh             # 部署脚本
│   ├── backup.sh             # 备份脚本
│   └── health-check.sh       # 健康检查脚本
└── ssl/                      # SSL 证书目录 (gitignore)
    ├── fullchain.pem
    └── privkey.pem
```

## 快速开始

### 1. 购买并配置 ECS

```bash
# 阿里云控制台操作
1. 购买 ECS 实例 (推荐 Ubuntu 22.04 LTS)
2. 配置安全组：开放 22(SSH), 80(HTTP), 443(HTTPS)
3. 绑定域名并解析到 ECS IP
4. 备案域名 (中国大陆必需)
```

### 2. 服务器初始化

```bash
# 登录服务器
ssh root@your-server-ip

# 下载并运行初始化脚本
curl -fsSL https://raw.githubusercontent.com/your-repo/main/deploy/scripts/init-server.sh | bash
```

### 3. 部署应用

```bash
# 克隆代码
git clone https://github.com/your-repo/py-ego-miniapp.git
cd py-ego-miniapp

# 配置环境变量
cp deploy/config/.env.example deploy/config/.env
vim deploy/config/.env  # 编辑配置

# 启动服务
cd deploy && docker compose up -d

# 查看状态
docker compose ps
docker compose logs -f app
```

## 环境变量配置

详见 `config/.env.example` 文件，需要配置：

- **数据库**: `DATABASE_URL`
- **Redis**: `REDIS_URL`
- **微信**: `WECHAT_APP_ID`, `WECHAT_APP_SECRET`
- **LLM**: `LLM_API_KEY`
- **OSS**: `OSS_ACCESS_KEY_ID`, `OSS_ACCESS_KEY_SECRET`
- **JWT**: `JWT_SECRET_KEY`

## 维护操作

```bash
# 查看日志
docker compose logs -f app
docker compose logs -f --tail 100 app

# 重启服务
docker compose restart app

# 更新代码
git pull && docker compose up -d --build

# 数据库备份
./scripts/backup.sh

# 进入容器调试
docker compose exec app bash

# 查看资源使用
docker stats
```

## 监控告警

- **应用监控**: 内置 `/health` 端点
- **资源监控**: 阿里云云监控
- **日志收集**: 阿里云 SLS (可选)

## 安全建议

1. **禁用 root 登录**，使用普通用户 + sudo
2. **配置防火墙**，仅开放必要端口
3. **定期更新**系统和依赖
4. **启用自动备份**
5. **使用密钥认证** SSH

## 故障排查

详见 [TROUBLESHOOTING.md](./TROUBLESHOOTING.md)
