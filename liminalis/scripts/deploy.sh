#!/usr/bin/env bash
# Liminalis 生产环境一键部署脚本（微信公众号平台）
# 基于 nginx + FastAPI 的部署方案
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "======================================"
echo "Liminalis 生产环境部署"
echo "======================================"
echo "项目目录: ${PROJECT_ROOT}"
echo ""

# ========================
# 0. 前置检查
# ========================
echo "[0/7] 前置检查..."

if [[ ! -f "${PROJECT_ROOT}/.env.local" ]]; then
    echo "警告: .env.local 不存在，请从 .env 复制并修改"
    echo "  cp .env .env.local"
    echo "  # 编辑 .env.local，设置数据库密码、微信 AppID/Secret 等"
fi

# 检查 Node 和 npm
if ! command -v npm >/dev/null 2>&1; then
    echo "错误: npm 未安装"
    exit 1
fi

# 检查 Python
PYTHON_BIN=""
if [[ -d "${PROJECT_ROOT}/.venv" ]]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
elif [[ -d "${HOME}/.venv" ]]; then
    PYTHON_BIN="${HOME}/.venv/bin/python"
fi

if [[ -z "${PYTHON_BIN}" || ! -x "${PYTHON_BIN}" ]]; then
    echo "错误: 未找到 Python 虚拟环境"
    echo "请先运行: python3.11 -m venv .venv && source .venv/bin/activate && pip install -e ."
    exit 1
fi

echo "  Python: ${PYTHON_BIN}"
echo "  Node:   $(node --version 2>/dev/null || echo 'N/A')"
echo "  npm:    $(npm --version 2>/dev/null || echo 'N/A')"

# ========================
# 1. 安装/更新 Python 依赖
# ========================
echo ""
echo "[1/7] 安装 Python 依赖..."
"${PYTHON_BIN}" -m pip install -e . --quiet
if "${PYTHON_BIN}" -c "import faiss" 2>/dev/null; then
    echo "  faiss-cpu 已安装"
else
    echo "  安装 faiss-cpu..."
    "${PYTHON_BIN}" -m pip install faiss-cpu --quiet
fi

# ========================
# 2. 构建前端
# ========================
echo ""
echo "[2/7] 构建前端..."
npm ci
npm run build

if [[ ! -d "${PROJECT_ROOT}/dist" ]]; then
    echo "错误: 前端构建失败，dist/ 目录不存在"
    exit 1
fi
echo "  dist/ 构建成功"

# ========================
# 3. 数据库迁移
# ========================
echo ""
echo "[3/7] 运行数据库迁移..."
"${PYTHON_BIN}" -m liminalis db upgrade || true

# ========================
# 4. 安装 systemd 服务
# ========================
echo ""
echo "[4/7] 配置 systemd 服务..."
if [[ "$(id -u)" -eq 0 ]]; then
    "${SCRIPT_DIR}/setup-systemd.sh"
else
    echo "  需要 root 权限配置 systemd，跳过（可手动运行 sudo scripts/setup-systemd.sh）"
fi

# ========================
# 5. 检查 Nginx 配置
# ========================
echo ""
echo "[5/7] 检查 Nginx 配置..."
if command -v nginx >/dev/null 2>&1; then
    if [[ -f "/etc/nginx/sites-enabled/liminalis" ]]; then
        echo "  Nginx 站点已启用"
        if sudo nginx -t 2>/dev/null; then
            echo "  Nginx 配置测试通过"
            sudo systemctl reload nginx 2>/dev/null || true
        else
            echo "  警告: Nginx 配置测试失败，请检查"
        fi
    else
        echo "  提示: Nginx 站点未配置"
        echo "  可运行: sudo scripts/setup-nginx.sh <your-domain.example.com>"
    fi
else
    echo "  警告: Nginx 未安装"
fi

# ========================
# 6. 启动/重启服务
# ========================
echo ""
echo "[6/7] 启动服务..."
if systemctl is-active --quiet liminalis 2>/dev/null; then
    echo "  重启 liminalis 服务..."
    sudo systemctl restart liminalis
else
    echo "  启动 liminalis 服务..."
    sudo systemctl start liminalis 2>/dev/null || "${SCRIPT_DIR}/start-prod.sh"
fi

# ========================
# 7. 健康检查
# ========================
echo ""
echo "[7/7] 健康检查..."
sleep 2

LIMINALIS_API_PORT="${LIMINALIS_API_PORT:-8010}"
for i in {1..10}; do
    if curl -fsS --max-time 2 "http://127.0.0.1:${LIMINALIS_API_PORT}/health" >/dev/null 2>&1; then
        echo "  ✓ 后端服务健康 (http://127.0.0.1:${LIMINALIS_API_PORT}/health)"
        break
    fi
    if [[ $i -eq 10 ]]; then
        echo "  ✗ 后端服务未响应，请检查日志: sudo journalctl -u liminalis -n 50"
    else
        sleep 1
    fi
done

echo ""
echo "======================================"
echo "部署完成"
echo "======================================"
echo ""
echo "常用命令:"
echo "  查看状态:  sudo systemctl status liminalis"
echo "  查看日志:  sudo journalctl -u liminalis -f"
echo "  重启服务:  sudo systemctl restart liminalis"
echo ""
echo "如果 Nginx 和 HTTPS 已配置，请通过域名访问:"
echo "  https://<your-domain>/health"
echo "======================================"
