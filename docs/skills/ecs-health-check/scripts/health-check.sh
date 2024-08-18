#!/bin/bash
#
# ECS / Linux Server Health Check Script
# Performs comprehensive system health checks and outputs a structured report.
#
# Usage:
#   ./health-check.sh
#
# Note: Requires passwordless sudo or run as root for full output.
#

set -o pipefail

run_sudo() {
    sudo "$@" 2>/dev/null
}

HEADER_COUNT=0
print_header() {
    HEADER_COUNT=$((HEADER_COUNT + 1))
    echo ""
    echo "========== [$HEADER_COUNT] $1 =========="
}

# Color codes (optional, disable if not tty)
RED='\033[0;31m'
YELLOW='\033[1;33m'
GREEN='\033[0;32m'
NC='\033[0m'

# =============================================================================
# 1. SYSTEM BASICS
# =============================================================================
print_header "系统基本信息"
echo "主机名: $(hostname)"
echo "内核: $(uname -r)"
echo "架构: $(uname -m)"
cat /etc/os-release 2>/dev/null | grep -E '^(PRETTY_NAME|NAME|VERSION_ID)=' | sed 's/^/OS: /'
echo "运行时间: $(uptime -p 2>/dev/null || cat /proc/uptime | awk '{printf "%.0f 天 %.0f 小时 %.0f 分钟\n", $1/86400, ($1%86400)/3600, ($1%3600)/60}')"
echo "当前时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "当前用户: $(whoami)"
echo "登录用户: $(who | wc -l) 个会话"

# =============================================================================
# 2. CPU
# =============================================================================
print_header "CPU 与负载"
echo "CPU 核心数: $(nproc)"
echo "负载平均: $(cat /proc/loadavg | awk '{print $1, $2, $3}')"
echo "CPU 使用率:"
top -bn1 | grep "Cpu(s)" | sed 's/^/  /'

# =============================================================================
# 3. MEMORY
# =============================================================================
print_header "内存使用情况"
free -h
echo ""
echo "内存占用 TOP 10 进程:"
printf "%-10s %-8s %-8s %-8s %s\n" "USER" "%CPU" "%MEM" "RSS(M)" "COMMAND"
ps aux --sort=-%mem | head -11 | tail -10 | awk '{printf "%-10s %-8s %-8s %-8s ", $1, $3, $4, int($6/1024); for(i=11;i<=NF;i++) printf "%s ", $i; print ""}'

# =============================================================================
# 4. DISK
# =============================================================================
print_header "磁盘空间"
df -hT | grep -v tmpfs | grep -v efivarfs
echo ""
echo "Inode 使用:"
df -i | grep -v tmpfs | grep -v efivarfs

# =============================================================================
# 5. IO
# =============================================================================
print_header "磁盘 I/O"
if command -v iostat &>/dev/null; then
    iostat -x 1 2 2>/dev/null | tail -n +4 | head -20
else
    echo "iostat 未安装 (sysstat)"
fi

# =============================================================================
# 6. PROCESSES
# =============================================================================
print_header "僵尸进程与异常进程"
ZOMBIES=$(ps aux | awk '$8 ~ /^Z/')
if [ -n "$ZOMBIES" ]; then
    echo "发现僵尸进程:"
    echo "$ZOMBIES"
else
    echo "无僵尸进程"
fi
DSTATE=$(ps aux | awk '$8 ~ /^D/')
if [ -n "$DSTATE" ]; then
    echo "发现 D 状态进程:"
    echo "$DSTATE"
else
    echo "无 D 状态进程"
fi
echo "当前总进程数: $(ps aux | wc -l)"

# =============================================================================
# 7. NETWORK
# =============================================================================
print_header "网络连接与端口"
echo "监听端口:"
ss -tlnp | grep LISTEN | awk '{printf "  %-6s %-22s %s\n", $1, $4, $7}'
echo ""
echo "连接统计:"
ss -s | grep -E "(Total|TCP|UDP|INET)"
echo ""
echo "网络接口:"
ip -brief addr 2>/dev/null || ifconfig -a 2>/dev/null | grep -E "^(eth|ens|enp|lo)" | head -5

# =============================================================================
# 8. SERVICES
# =============================================================================
print_header "系统服务状态"
FAILED=$(run_sudo systemctl --failed --no-legend 2>/dev/null)
if [ -n "$FAILED" ]; then
    echo "失败的系统服务:"
    echo "$FAILED" | awk '{print "  [FAILED] " $1}'
else
    echo "所有系统服务正常"
fi

# =============================================================================
# 9. LOGS
# =============================================================================
print_header "最近系统日志错误 (24h)"
run_sudo journalctl --priority=3 --since "24 hours ago" --no-pager 2>/dev/null | tail -15 | sed 's/^/  /' || echo "  无法读取日志"

# =============================================================================
# 10. SECURITY
# =============================================================================
print_header "登录与安全"
echo "最近登录 (last -10):"
last -10 2>/dev/null | sed 's/^/  /'
echo ""
echo "失败登录尝试:"
run_sudo grep "Failed password" /var/log/auth.log 2>/dev/null | tail -5 | sed 's/^/  /' || echo "  无记录"

# =============================================================================
# 11. LARGE FILES & LOGS
# =============================================================================
print_header "大文件与日志"
echo "/var/log 总大小: $(du -sh /var/log 2>/dev/null | cut -f1)"
echo ""
echo "/var/log 子目录 TOP 10:"
du -sh /var/log/* 2>/dev/null | sort -rh | head -10 | sed 's/^/  /'
echo ""
echo "大于 100MB 的文件 (前10):"
run_sudo find /var/log /home -type f -size +100M 2>/dev/null | head -10 | sed 's/^/  /' || echo "  未发现"

# =============================================================================
# 12. UPDATES
# =============================================================================
print_header "系统更新"
if command -v apt &>/dev/null; then
    COUNT=$(apt list --upgradable 2>/dev/null | grep -c "upgradable")
    echo "可更新包数量: $COUNT"
else
    echo "非 apt 系统，跳过"
fi

# =============================================================================
# 13. FIREWALL
# =============================================================================
print_header "防火墙状态"
if command -v ufw &>/dev/null; then
    run_sudo ufw status verbose 2>/dev/null | sed 's/^/  /'
else
    echo "ufw 未安装"
    if command -v iptables &>/dev/null; then
        echo "iptables 规则数: $(run_sudo iptables -L 2>/dev/null | wc -l)"
    fi
fi

# =============================================================================
# 14. CRON
# =============================================================================
print_header "定时任务"
for user in $(cut -f1 -d: /etc/passwd | grep -E "^(root|admin|www-data|redis)"); do
    CRON=$(run_sudo crontab -u "$user" -l 2>/dev/null)
    if [ -n "$CRON" ] && [ "$CRON" != "no crontab for $user" ]; then
        echo "--- $user ---"
        echo "$CRON" | sed 's/^/  /'
    fi
done

# =============================================================================
# 15. SSH KEYS
# =============================================================================
print_header "SSH 授权密钥"
for user_home in /root /home/*; do
    if [ -f "$user_home/.ssh/authorized_keys" ]; then
        user=$(basename "$user_home")
        count=$(wc -l < "$user_home/.ssh/authorized_keys")
        echo "  $user: $count 行"
    fi
done

# =============================================================================
# 16. TIME SYNC
# =============================================================================
print_header "时间同步"
timedatectl status 2>/dev/null | sed 's/^/  /' || echo "  timedatectl 不可用"

# =============================================================================
# 17. SWAP
# =============================================================================
print_header "Swap 使用"
swapon --show 2>/dev/null | sed 's/^/  /' || echo "  无 swap"

# =============================================================================
# 18. OOM HISTORY
# =============================================================================
print_header "OOM 历史"
OOM=$(run_sudo dmesg 2>/dev/null | grep -i "out of memory\|oom\|killed process")
if [ -n "$OOM" ]; then
    echo "$OOM" | tail -5 | sed 's/^/  /'
else
    echo "  无 OOM 记录"
fi

# =============================================================================
# 19. ENVIRONMENT SECRETS
# =============================================================================
print_header "环境变量敏感信息扫描"
ENV_SECRETS=$(env | grep -iE "password|secret|token|key|api_key|private" | sed 's/=.*/=***/')
if [ -n "$ENV_SECRETS" ]; then
    echo "发现可疑环境变量 (值已隐藏):"
    echo "$ENV_SECRETS" | sed 's/^/  /'
else
    echo "  未发现明显的敏感环境变量"
fi

# =============================================================================
# 20. NGINX (if exists)
# =============================================================================
if command -v nginx &>/dev/null; then
    print_header "Nginx 状态"
    run_sudo nginx -t 2>&1 | sed 's/^/  /'
    echo ""
    run_sudo systemctl status nginx --no-legend --no-pager 2>/dev/null | head -5 | sed 's/^/  /'
fi

# =============================================================================
# 21. REDIS (if exists)
# =============================================================================
if command -v redis-cli &>/dev/null; then
    print_header "Redis 状态"
    run_sudo systemctl status redis-server --no-legend --no-pager 2>/dev/null | head -5 | sed 's/^/  /'
fi

# =============================================================================
# 22. DOCKER (if exists)
# =============================================================================
if command -v docker &>/dev/null; then
    print_header "Docker 状态"
    run_sudo systemctl status docker --no-legend --no-pager 2>/dev/null | head -5 | sed 's/^/  /'
    echo ""
    echo "容器数量: $(run_sudo docker ps -aq 2>/dev/null | wc -l)"
fi

# =============================================================================
# 23. CLOUD AGENTS
# =============================================================================
print_header "云厂商 Agent"
ps aux | grep -iE "aegis|aliyun|cloudmonitor|tencent|qcloud|barad" | grep -v grep | awk '{print "  " $11}' || echo "  未发现"

# =============================================================================
# SUMMARY
# =============================================================================
echo ""
echo "========================================"
echo "检查完成。共执行 $HEADER_COUNT 项检查。"
echo "时间: $(date '+%Y-%m-%d %H:%M:%S %Z')"
echo "========================================"
