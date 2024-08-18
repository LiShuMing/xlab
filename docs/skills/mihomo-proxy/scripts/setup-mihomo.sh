#!/bin/bash
#
# Mihomo Proxy Setup Script
# Usage: bash setup-mihomo.sh /path/to/config.yaml [mihomo_binary_path]
#

set -e

CONFIG_FILE="${1:-}"
MIHOMO_BIN="${2:-}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() { echo "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo "${RED}[ERROR]${NC} $1"; }

# Check arguments
if [[ -z "$CONFIG_FILE" ]]; then
    log_error "Usage: bash setup-mihomo.sh /path/to/config.yaml [mihomo_binary_path]"
    exit 1
fi

if [[ ! -f "$CONFIG_FILE" ]]; then
    log_error "Config file not found: $CONFIG_FILE"
    exit 1
fi

# Detect mihomo binary
if [[ -z "$MIHOMO_BIN" ]]; then
    MIHOMO_BIN=$(which mihomo 2>/dev/null || echo "")
    if [[ -z "$MIHOMO_BIN" ]]; then
        # Common locations
        for loc in ~/.local/bin/mihomo /usr/local/bin/mihomo /usr/bin/mihomo; do
            if [[ -f "$loc" ]]; then
                MIHOMO_BIN="$loc"
                break
            fi
        done
    fi
fi

if [[ -z "$MIHOMO_BIN" ]]; then
    log_error "Mihomo binary not found. Please install mihomo first."
    log_info "Download from: https://github.com/MetaCubeX/mihomo/releases"
    exit 1
fi

log_info "Using mihomo binary: $MIHOMO_BIN"

# Get user info
USER_NAME=$(whoami)
USER_HOME=$(eval echo "~$USER_NAME")

# Step 1: Create config directory
log_info "Creating config directory..."
mkdir -p "$USER_HOME/.config/mihomo"
mkdir -p "$USER_HOME/.config/systemd/user"

# Step 2: Copy config file
log_info "Copying config file..."
cp "$CONFIG_FILE" "$USER_HOME/.config/mihomo/config.yaml"

# Step 3: Download MMDB if not exists
MMDB_FILE="$USER_HOME/.config/mihomo/Country.mmdb"
if [[ ! -f "$MMDB_FILE" ]] || [[ $(stat -c%s "$MMDB_FILE" 2>/dev/null || stat -f%z "$MMDB_FILE") -lt 100000 ]]; then
    log_info "Downloading GeoIP database (MMDB)..."
    
    # Try multiple sources
    MMDB_URLS=(
        "https://fastly.jsdelivr.net/gh/Hackl0us/GeoIP2-CN@release/Country.mmdb"
        "https://cdn.jsdelivr.net/gh/Loyalsoldier/v2ray-rules-dat@release/Country.mmdb"
        "https://github.com/MetaCubeX/meta-rules-dat/releases/download/latest/country.mmdb"
    )
    
    for url in "${MMDB_URLS[@]}"; do
        log_info "Trying: $url"
        if curl -L --connect-timeout 30 -o "$MMDB_FILE" "$url" 2>/dev/null; then
            if [[ -f "$MMDB_FILE" ]] && [[ $(stat -c%s "$MMDB_FILE" 2>/dev/null || stat -f%z "$MMDB_FILE") -gt 100000 ]]; then
                log_info "MMDB downloaded successfully"
                break
            fi
        fi
    done
    
    if [[ ! -f "$MMDB_FILE" ]] || [[ $(stat -c%s "$MMDB_FILE" 2>/dev/null || stat -f%z "$MMDB_FILE") -lt 100000 ]]; then
        log_warn "MMDB download failed. Mihomo will try to download on first start."
    fi
else
    log_info "MMDB already exists"
fi

# Step 4: Create systemd service
log_info "Creating systemd user service..."
cat > "$USER_HOME/.config/systemd/user/mihomo.service" << EOF
[Unit]
Description=Mihomo (Clash Meta) Proxy
After=network.target

[Service]
Type=simple
ExecStart=$MIHOMO_BIN -d $USER_HOME/.config/mihomo
Restart=on-failure
RestartSec=5

[Install]
WantedBy=default.target
EOF

# Step 5: Enable and start service
log_info "Enabling and starting mihomo service..."
systemctl --user daemon-reload
systemctl --user enable mihomo
systemctl --user start mihomo

sleep 2

# Check service status
if systemctl --user is-active --quiet mihomo; then
    log_info "Mihomo service started successfully"
else
    log_error "Mihomo service failed to start"
    log_info "Check logs: journalctl --user -u mihomo --no-pager -n 30"
    exit 1
fi

# Step 6: Add proxy settings to bashrc
BASHRC="$USER_HOME/.bashrc"
if ! grep -q "mihomo proxy" "$BASHRC" 2>/dev/null; then
    log_info "Adding proxy settings to .bashrc..."
    cat >> "$BASHRC" << 'EOF'

# mihomo proxy settings
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
EOF
else
    log_info "Proxy settings already in .bashrc"
fi

# Step 7: Test proxy
log_info "Testing proxy connection..."
sleep 2

if curl -x http://127.0.0.1:7890 -s --connect-timeout 10 https://www.google.com -o /dev/null; then
    log_info "Proxy test successful - Google accessible"
else
    log_warn "Proxy test failed - check node selection in Web UI"
fi

# Summary
echo ""
echo "======================================"
log_info "Setup Complete!"
echo "======================================"
echo ""
echo "Proxy Ports:"
echo "  HTTP:     127.0.0.1:7890"
echo "  SOCKS5:   127.0.0.1:7891"
echo "  Web UI:   http://127.0.0.1:9090/ui"
echo ""
echo "Usage:"
echo "  source ~/.bashrc     # Load proxy settings"
echo "  proxy_on             # Enable proxy"
echo "  proxy_off            # Disable proxy"
echo ""
echo "Service Management:"
echo "  systemctl --user status mihomo"
echo "  systemctl --user restart mihomo"
echo ""