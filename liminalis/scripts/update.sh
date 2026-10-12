#!/usr/bin/env bash
# Liminalis 生产环境更新发布脚本
# 用于拉取最新代码并重新部署
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

cd "${PROJECT_ROOT}"

echo "======================================"
echo "Liminalis 更新发布"
echo "======================================"
echo "项目目录: ${PROJECT_ROOT}"
echo ""

# ========================
# 1. 拉取最新代码
# ========================
echo "[1/5] 拉取最新代码..."
if [[ -d "${PROJECT_ROOT}/.git" ]]; then
    git pull
else
    echo "  警告: 不是 git 仓库，跳过拉取"
fi

# ========================
# 2. 安装依赖并构建
# ========================
echo ""
echo "[2/5] 安装依赖并构建..."

# Python
PYTHON_BIN=""
if [[ -d "${PROJECT_ROOT}/.venv" ]]; then
    PYTHON_BIN="${PROJECT_ROOT}/.venv/bin/python"
elif [[ -d "${HOME}/.venv" ]]; then
    PYTHON_BIN="${HOME}/.venv/bin/python"
fi

if [[ -n "${PYTHON_BIN}" && -x "${PYTHON_BIN}" ]]; then
    "${PYTHON_BIN}" -m pip install -e . --quiet
else
    echo "  警告: 未找到 Python 虚拟环境"
fi

# Node
npm ci
npm run build

# ========================
# 3. 数据库迁移
# ========================
echo ""
echo "[3/5] 运行数据库迁移..."
if [[ -n "${PYTHON_BIN}" && -x "${PYTHON_BIN}" ]]; then
    "${PYTHON_BIN}" -m liminalis db upgrade || true
else
    echo "  跳过: Python 环境未就绪"
fi

# ========================
# 4. 重启服务
# ========================
echo ""
echo "[4/5] 重启服务..."
if systemctl is-active --quiet liminalis 2>/dev/null; then
    echo "  通过 systemd 重启..."
    sudo systemctl restart liminalis
else
    echo "  systemd 服务未运行，尝试通过脚本重启..."
    "${SCRIPT_DIR}/stop-prod.sh" 2>/dev/null || true
    sleep 1
    "${SCRIPT_DIR}/start-prod.sh"
fi

# ========================
# 5. 验证
# ========================
echo ""
echo "[5/5] 验证服务状态..."
sleep 2

LIMINALIS_API_PORT="${LIMINALIS_API_PORT:-8010}"
if curl -fsS --max-time 3 "http://127.0.0.1:${LIMINALIS_API_PORT}/health" >/dev/null 2>&1; then
    echo "  ✓ 服务健康 (port ${LIMINALIS_API_PORT})"
else
    echo "  ✗ 服务未响应"
fi

echo ""
echo "======================================"
echo "更新发布完成"
echo "======================================"
echo ""
echo "查看日志:"
echo "  sudo journalctl -u liminalis -n 100 --no-pager"
echo ""
