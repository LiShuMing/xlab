---
name: ecs-health-check
description: >
  Comprehensive Linux/ECS server health check and diagnostics. Use when the user
  asks to check server status, inspect system health, diagnose performance issues,
  audit security, review running services, or analyze disk/memory/CPU usage on
  any Linux server (especially Alibaba Cloud ECS, Ubuntu/CentOS). Triggers on
  keywords like: "检查服务器", "health check", "server status", "运行状况",
  "系统检查", "排查问题", " diagnose ", "ECS 状态".
---

# ECS / Linux Server Health Check

Perform a systematic, multi-dimensional health check on a Linux server and
produce a structured report with findings prioritized by severity.

## Workflow

1. **Ensure sudo access**: The script requires sudo privileges (passwordless sudo or already running as root).
2. **Run checks**: Execute all check categories in sequence (or run the bundled
   script `scripts/health-check.sh`).
3. **Analyze output**: For each check, flag anomalies using the severity rules below.
4. **Produce report**: Output a Chinese-language report with sections:
   - ⚠️ 需要立即处理的问题 (Critical)
   - 🔶 需要注意的事项 (Warning/Info)
   - ✅ 运行良好的方面 (Healthy)
   - 📋 建议的修复优先级 (Action list)

## Check Categories

Run these checks in order. Use parallel execution where possible.

| # | Category | Key Commands | What to flag |
|---|----------|--------------|--------------|
| 1 | **System Basics** | `uname -a`, `uptime`, `cat /etc/os-release` | Unexpected reboots, very old kernel |
| 2 | **CPU & Load** | `nproc`, `cat /proc/loadavg`, `top -bn1` | Load > cores * 2, high steal time (>5%) |
| 3 | **Memory** | `free -h`, `ps aux --sort=-%mem` | Swap used, single process >30% RAM |
| 4 | **Disk Space** | `df -h`, `df -i` | Any partition >80% or >90% |
| 5 | **Disk I/O** | `iostat -x 1 3` | High %util (>80%), high await |
| 6 | **Processes** | `ps aux` awk '$8~/^Z/' or '/^D/' | Zombie processes, D-state processes |
| 7 | **Network** | `ss -tlnp`, `ss -s`, `ip -br a` | Unexpected open ports, high TIME_WAIT |
| 8 | **Services** | `systemctl --failed` | Any failed services |
| 9 | **Logs** | `journalctl -p 3 --since "24h"` | Recurring errors, OOMs |
| 10 | **Security** | `last`, `/var/log/auth.log` | Failed logins, root login from WAN |
| 11 | **Large Files** | `find /var/log /home -size +100M` | Runaway logs, huge DBs |
| 12 | **Updates** | `apt list --upgradable` | >0 security updates pending |
| 13 | **Firewall** | `ufw status`, `iptables -L` | Overly permissive rules |
| 14 | **Cron** | `crontab -l` for key users | Unexpected jobs |
| 15 | **SSH Keys** | `~/.ssh/authorized_keys` count | Unexpected keys for root/admin |
| 16 | **Time Sync** | `timedatectl status` | Not synchronized |
| 17 | **Swap** | `swapon --show` | Heavy swap usage |
| 18 | **OOM** | `dmesg \| grep -i oom` | Any OOM kills |
| 19 | **Env Secrets** | `env \| grep -iE "pass\|secret\|token\|key"` | Credentials in env vars |
| 20 | **Nginx** | `nginx -t`, `systemctl status nginx` | Config errors, not running |
| 21 | **Redis** | `systemctl status redis-server` | Not running, no auth |
| 22 | **Docker** | `systemctl status docker`, `docker ps -a` | Unexpected containers |
| 23 | **Cloud Agents** | `ps aux \| grep -iE "aegis\|aliyun\|cloudmonitor"` | Agent failures or high CPU |

## Severity Rules

- **Critical (⚠️)**: Service failed & needed, disk >90%, root breached, OOM kills,
  logrotate failing, secrets exposed in plain text.
- **Warning (🔶)**: Disk >80%, swap in use, failed but unused service, failed logins,
  pending updates, high single-process memory, SSH root login enabled.
- **Info (ℹ️)**: Observations that may become issues if trends continue.

## Report Template

Use this structure in Chinese:

```markdown
## ⚠️ 需要立即处理的问题
1. **[问题名]**: 现状 → 影响 → 修复建议

## 🔶 需要注意的事项
| 项目 | 现状 | 建议 |

## ✅ 运行良好的方面
- 列表

## 📋 建议的修复优先级
1. 高: ...
2. 中: ...
3. 低: ...
```

## Bundled Script

For one-shot execution, run:

```bash
bash scripts/health-check.sh
```

The script produces raw output; Kimi parses it into the report above.

**Note**: The script uses `sudo` internally. Run it in an environment with
passwordless sudo or as root.

## Tips

- When `systemctl --failed` shows errors, inspect the specific unit with
  `systemctl status <unit>` and `journalctl -u <unit>`.
- For logrotate failures, run `logrotate -d /etc/logrotate.conf` to find
  duplicate entries or syntax errors.
- For nginx, check both `/var/log/nginx/error.log` and config test `nginx -t`.
