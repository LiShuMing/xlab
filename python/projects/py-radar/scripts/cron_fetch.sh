#!/bin/bash
# DB Radar - 定时抓取脚本
# 用法: ./scripts/cron_fetch.sh
# 建议添加到 crontab: 0 8 * * * /path/to/scripts/cron_fetch.sh

set -e

# 项目目录
PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
LOG_FILE="${PROJECT_DIR}/logs/fetch.log"

# 创建日志目录
mkdir -p "${PROJECT_DIR}/logs"

# 日志函数
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "${LOG_FILE}"
}

log "========== 开始定时抓取 =========="

# 进入项目目录
cd "${PROJECT_DIR}"

# 激活虚拟环境（如果存在）
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 运行抓取命令
log "开始抓取数据..."
if python -m dbradar run --html --language zh --max-items 150 --top-k 25 >> "${LOG_FILE}" 2>&1; then
    log "抓取完成！"
else
    log "错误: 抓取失败"
    exit 1
fi

log "========== 抓取结束 =========="