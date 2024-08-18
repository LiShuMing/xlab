---
name: mihomo-proxy
description: >
  Configure mihomo (Clash Meta) proxy for scientific internet access on Linux.
  Use when the user asks to set up proxy, VPN, or "科学上网" on a Linux machine,
  especially when they have an existing Clash/Mihomo config file. Triggers on
  keywords like: "设置代理", "科学上网", "clash", "mihomo", "vpn配置", "proxy setup".
---

# Mihomo Proxy Setup Guide

Configure mihomo (Clash Meta) as a user-level systemd service for proxying
network traffic through existing VPN/Clash configurations.

## Prerequisites

1. **Mihomo binary** installed on the system (check with `which mihomo`)
2. **Clash config file** (typically `config.yaml`) from your VPN provider
3. User-level systemd support (most modern Linux distributions)

## Workflow

### Step 1: Verify Mihomo Installation

Check if mihomo is installed:

```bash
which mihomo
```

If not installed, install via:
- Debian/Ubuntu: `sudo dpkg -i mihomo-linux-amd64-*.deb`
- Or download from: https://github.com/MetaCubeX/mihomo/releases

### Step 2: Prepare Configuration Directory

Create user config directory and copy the clash config:

```bash
mkdir -p ~/.config/mihomo
cp /path/to/your/config.yaml ~/.config/mihomo/config.yaml
```

### Step 3: Download GeoIP Database (MMDB)

**Critical**: If the network is blocked, mihomo cannot auto-download MMDB.
Download manually from CDN mirror:

```bash
cd ~/.config/mihomo
curl -L -o Country.mmdb "https://fastly.jsdelivr.net/gh/Hackl0us/GeoIP2-CN@release/Country.mmdb"
```

Alternative sources:
- `https://cdn.jsdelivr.net/gh/Loyalsoldier/v2ray-rules-dat@release/Country.mmdb`
- `https://github.com/MetaCubeX/meta-rules-dat/releases`

### Step 4: Create Systemd User Service

Create the service file at `~/.config/systemd/user/mihomo.service`:

```ini
[Unit]
Description=Mihomo (Clash Meta) Proxy
After=network.target

[Service]
Type=simple
ExecStart=/home/<USER>/.local/bin/mihomo -d /home/<USER>/.config/mihomo
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
```

Replace `<USER>` with actual username.

### Step 5: Enable and Start Service

```bash
systemctl --user daemon-reload
systemctl --user enable mihomo
systemctl --user start mihomo
systemctl --user status mihomo
```

### Step 6: Configure Environment Variables

Add proxy settings to `~/.bashrc`:

```bash
# Proxy settings for mihomo
export http_proxy="http://127.0.0.1:7890"
export https_proxy="http://127.0.0.1:7890"
export all_proxy="socks5://127.0.0.1:7891"
export no_proxy="localhost,127.0.0.1,::1,*.cn"

# Function to toggle proxy
proxy_on() {
    export http_proxy="http://127.0.0.1:7890"
    export https_proxy="http://127.0.0.1:7890"
    export all_proxy="socks5://127.0.0.1:7891"
    export no_proxy="localhost,127.0.0.1,::1,*.cn"
    echo "Proxy enabled"
}

proxy_off() {
    unset http_proxy https_proxy all_proxy no_proxy
    echo "Proxy disabled"
}
```

### Step 7: Verify Proxy Works

Test connectivity:

```bash
export http_proxy="http://127.0.0.1:7890" https_proxy="http://127.0.0.1:7890"
curl -s --connect-timeout 5 https://www.google.com -o /dev/null -w "%{http_code}\n"
curl -s --connect-timeout 5 https://github.com -o /dev/null -w "%{http_code}\n"
```

Expected output: `200`

## Common Ports

| Port | Protocol | Description |
|------|----------|-------------|
| 7890 | HTTP | HTTP proxy |
| 7891 | SOCKS5 | SOCKS proxy |
| 7893 | Mixed | HTTP + SOCKS combined |
| 9090 | REST API | Web UI / external controller |

## Troubleshooting

### MMDB Download Failed

If mihomo fails to start with MMDB error, manually download (see Step 3).

### Service Won't Start

Check logs:
```bash
journalctl --user -u mihomo --no-pager -n 50
```

### Proxy Not Working

1. Check mihomo is listening:
   ```bash
   ss -tlnp | grep mihomo
   ```

2. Test direct proxy connection:
   ```bash
   curl -x http://127.0.0.1:7890 https://www.google.com
   ```

### Config Updated

When updating `config.yaml`, restart service:
```bash
cp new-config.yaml ~/.config/mihomo/config.yaml
systemctl --user restart mihomo
```

## Bundled Script

For automated setup, run:

```bash
bash scripts/setup-mihomo.sh /path/to/config.yaml
```

The script will:
1. Copy config to `~/.config/mihomo`
2. Download MMDB if needed
3. Create systemd service
4. Enable and start the service
5. Add proxy settings to `~/.bashrc`

## Quick Commands Reference

```bash
# Service management
systemctl --user status mihomo   # Check status
systemctl --user restart mihomo  # Restart after config change
systemctl --user stop mihomo     # Stop proxy
systemctl --user start mihomo    # Start proxy

# Proxy toggle (after source ~/.bashrc)
proxy_on   # Enable proxy env vars
proxy_off  # Disable proxy env vars

# Quick test
curl -x http://127.0.0.1:7890 https://www.google.com
```

## Web UI

Access the dashboard at: `http://127.0.0.1:9090/ui`

Use this to:
- Select proxy nodes
- View connection stats
- Toggle proxy modes (Rule/Global/Direct)