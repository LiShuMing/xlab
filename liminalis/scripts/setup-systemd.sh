#!/usr/bin/env bash
# 安装 Liminalis systemd 服务
# 用于微信公众号生产环境部署
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

SERVICE_NAME="liminalis"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

# 自动推断当前用户（用于 systemd 的 User= 字段）
DEPLOY_USER="${DEPLOY_USER:-$(whoami)}"

# 确定 Python 虚拟环境路径
if [[ -d "${PROJECT_ROOT}/.venv" ]]; then
    VENV_DIR="${PROJECT_ROOT}/.venv"
elif [[ -d "${HOME}/.venv" ]]; then
    VENV_DIR="${HOME}/.venv"
else
    echo "错误: 未找到 Python 虚拟环境"
    echo "请先运行: python3.11 -m venv ${PROJECT_ROOT}/.venv"
    exit 1
fi

PYTHON_BIN="${VENV_DIR}/bin/python"

if [[ ! -x "${PYTHON_BIN}" ]]; then
    echo "错误: Python 解释器不存在: ${PYTHON_BIN}"
    exit 1
fi

echo "======================================"
echo "安装 Liminalis systemd 服务"
echo "======================================"
echo "项目目录: ${PROJECT_ROOT}"
echo "部署用户: ${DEPLOY_USER}"
echo "Python:   ${PYTHON_BIN}"
echo "服务文件: ${SERVICE_FILE}"
echo ""

# 需要 root 权限
if [[ "$(id -u)" -ne 0 ]]; then
    echo "注意: 需要 root 权限写入 ${SERVICE_FILE}"
    echo "将使用 sudo ..."
fi

RUNNER="$(command -v sudo 2>/dev/null || echo "")"

# 写入服务文件
${RUNNER} tee "${SERVICE_FILE}" > /dev/null <<EOF
[Unit]
Description=Liminalis FastAPI
After=network.target postgresql.service redis-server.service

[Service]
Type=simple
WorkingDirectory=${PROJECT_ROOT}
EnvironmentFile=${PROJECT_ROOT}/.env.local
ExecStart=${PYTHON_BIN} -m backend.app
Restart=always
RestartSec=3
User=${DEPLOY_USER}

[Install]
WantedBy=multi-user.target
EOF

echo "服务文件已写入: ${SERVICE_FILE}"

# 重载 systemd
${RUNNER} systemctl daemon-reload

# 启用并启动
${RUNNER} systemctl enable "${SERVICE_NAME}"

# 如果已经在运行，则重启；否则只启用不启动
if ${RUNNER} systemctl is-active --quiet "${SERVICE_NAME}" 2>/dev/null; then
    echo "服务正在运行，执行重启..."
    ${RUNNER} systemctl restart "${SERVICE_NAME}"
else
    echo "服务未运行，执行启动..."
    ${RUNNER} systemctl start "${SERVICE_NAME}"
fi

sleep 2

# 状态检查
echo ""
echo "服务状态:"
${RUNNER} systemctl status "${SERVICE_NAME}" --no-pager || true

echo ""
echo "======================================"
echo "systemd 服务安装完成"
echo ""
echo "常用命令:"
echo "  sudo systemctl status ${SERVICE_NAME}"
echo "  sudo journalctl -u ${SERVICE_NAME} -f"
echo "  sudo systemctl restart ${SERVICE_NAME}"
echo "======================================"
