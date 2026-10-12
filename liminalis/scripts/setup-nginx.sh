#!/usr/bin/env bash
# 安装并启用 Nginx 配置（Liminalis 微信公众号部署）
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

# 参数解析
DOMAIN="${1:-}"
if [[ -z "${DOMAIN}" ]]; then
    echo "用法: $0 <domain> [--dry-run]"
    echo "示例: $0 liminalis.example.com"
    exit 1
fi

DRY_RUN=false
if [[ "${2:-}" == "--dry-run" ]]; then
    DRY_RUN=true
fi

TEMPLATE_FILE="${SCRIPT_DIR}/nginx-liminalis.conf"
AVAILABLE_FILE="/etc/nginx/sites-available/liminalis"
ENABLED_FILE="/etc/nginx/sites-enabled/liminalis"
DEFAULT_FILE="/etc/nginx/sites-enabled/default"

if [[ ! -f "${TEMPLATE_FILE}" ]]; then
    echo "错误: 模板文件不存在: ${TEMPLATE_FILE}"
    exit 1
fi

# 检查 Nginx 是否安装
if ! command -v nginx >/dev/null 2>&1; then
    echo "错误: Nginx 未安装"
    echo "请先运行: sudo apt install -y nginx"
    exit 1
fi

echo "======================================"
echo "配置 Nginx for Liminalis"
echo "======================================"
echo "域名:     ${DOMAIN}"
echo "模板:     ${TEMPLATE_FILE}"
echo "项目目录: ${PROJECT_ROOT}"
echo ""

# 读取模板并替换变量
CONFIG_CONTENT=$(sed \
    -e "s/your-domain.example/${DOMAIN}/g" \
    -e "s|/opt/xlab/liminalis|${PROJECT_ROOT}|g" \
    "${TEMPLATE_FILE}")

if ${DRY_RUN}; then
    echo "===== 生成的配置内容（干运行） ====="
    echo "${CONFIG_CONTENT}"
    echo "====================================="
    exit 0
fi

RUNNER="$(command -v sudo 2>/dev/null || echo "")"

# 写入配置
echo "写入 Nginx 配置: ${AVAILABLE_FILE}"
${RUNNER} mkdir -p "$(dirname "${AVAILABLE_FILE}")"
${RUNNER} tee "${AVAILABLE_FILE}" > /dev/null <<< "${CONFIG_CONTENT}"

# 创建日志目录
${RUNNER} mkdir -p /var/log/nginx

# 禁用默认站点（如果存在）
if [[ -f "${DEFAULT_FILE}" ]]; then
    echo "禁用默认站点: ${DEFAULT_FILE}"
    ${RUNNER} rm -f "${DEFAULT_FILE}"
fi

# 启用站点
if [[ ! -L "${ENABLED_FILE}" ]]; then
    echo "启用站点: ${ENABLED_FILE}"
    ${RUNNER} ln -s "${AVAILABLE_FILE}" "${ENABLED_FILE}"
fi

echo ""
echo "测试 Nginx 配置..."
${RUNNER} nginx -t

echo ""
echo "重载 Nginx..."
${RUNNER} systemctl reload nginx

echo ""
echo "======================================"
echo "Nginx 配置完成"
echo ""
echo "HTTP 测试:  curl http://${DOMAIN}/health"
echo ""
echo "下一步: 申请 HTTPS 证书"
echo "  sudo apt install -y certbot python3-certbot-nginx"
echo "  sudo certbot --nginx -d ${DOMAIN}"
echo "======================================"
