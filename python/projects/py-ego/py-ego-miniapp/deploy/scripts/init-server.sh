#!/bin/bash
# PyEgo MiniApp - Server Initialization Script
# Run this on a fresh Ubuntu 22.04 server

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
APP_NAME="pyego"
APP_USER="pyego"
APP_DIR="/opt/${APP_NAME}"
DOCKER_COMPOSE_VERSION="2.23.0"

# Helper functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [ "$EUID" -ne 0 ]; then
    log_error "Please run as root"
    exit 1
fi

log_info "Starting server initialization for PyEgo MiniApp..."

# ============================================================================
# 1. System Update
# ============================================================================
log_info "Updating system packages..."
apt-get update
apt-get upgrade -y

# ============================================================================
# 2. Install Dependencies
# ============================================================================
log_info "Installing dependencies..."
apt-get install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    software-properties-common \
    git \
    vim \
    htop \
    ufw \
    fail2ban \
    certbot \
    python3-certbot-nginx \
    jq

# ============================================================================
# 3. Install Docker
# ============================================================================
log_info "Installing Docker..."
if ! command -v docker &> /dev/null; then
    curl -fsSL https://get.docker.com | sh
    systemctl enable docker
    systemctl start docker
    log_info "Docker installed successfully"
else
    log_warn "Docker already installed, skipping..."
fi

# Install Docker Compose plugin
if ! docker compose version &> /dev/null; then
    log_info "Installing Docker Compose plugin..."
    DOCKER_CONFIG=${DOCKER_CONFIG:-$HOME/.docker}
    mkdir -p $DOCKER_CONFIG/cli-plugins
    curl -SL "https://github.com/docker/compose/releases/download/v${DOCKER_COMPOSE_VERSION}/docker-compose-linux-$(uname -m)" \
        -o $DOCKER_CONFIG/cli-plugins/docker-compose
    chmod +x $DOCKER_CONFIG/cli-plugins/docker-compose
fi

# ============================================================================
# 4. Create Application User
# ============================================================================
log_info "Creating application user..."
if ! id "$APP_USER" &>/dev/null; then
    useradd -r -s /bin/bash -m -d "$APP_DIR" "$APP_USER"
    usermod -aG docker "$APP_USER"
    log_info "User $APP_USER created"
else
    log_warn "User $APP_USER already exists"
fi

# ============================================================================
# 5. Configure Firewall (UFW)
# ============================================================================
log_info "Configuring firewall..."
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh
ufw allow 80/tcp
ufw allow 443/tcp

# Enable UFW non-interactively
ufw --force enable
log_info "Firewall configured"

# ============================================================================
# 6. Configure Fail2Ban
# ============================================================================
log_info "Configuring Fail2Ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true
port = ssh
filter = sshd
logpath = /var/log/auth.log
maxretry = 3

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
action = iptables-multiport[name=ReqLimit, port="http,https", protocol=tcp]
logpath = /var/log/nginx/error.log
findtime = 600
bantime = 7200
maxretry = 10
EOF

systemctl enable fail2ban
systemctl restart fail2ban
log_info "Fail2Ban configured"

# ============================================================================
# 7. System Optimization
# ============================================================================
log_info "Applying system optimizations..."

# Increase file descriptor limits
cat >> /etc/security/limits.conf << EOF
${APP_USER} soft nofile 65536
${APP_USER} hard nofile 65536
root soft nofile 65536
root hard nofile 65536
EOF

# Kernel tuning for network performance
cat >> /etc/sysctl.conf << EOF
# Network performance
net.core.somaxconn = 65535
net.ipv4.tcp_max_syn_backlog = 65535
net.ipv4.ip_local_port_range = 1024 65535

# Security
net.ipv4.tcp_syncookies = 1
net.ipv4.tcp_synack_retries = 2
net.ipv4.tcp_syn_retries = 2
EOF

sysctl -p

# ============================================================================
# 8. Setup Log Rotation
# ============================================================================
log_info "Configuring log rotation..."
cat > /etc/logrotate.d/${APP_NAME} << EOF
${APP_DIR}/logs/*.log {
    daily
    rotate 14
    compress
    delaycompress
    missingok
    notifempty
    create 0644 ${APP_USER} ${APP_USER}
    sharedscripts
    postrotate
        /usr/bin/docker compose -f ${APP_DIR}/docker-compose.yml kill -s USR1 nginx 2>/dev/null || true
    endscript
}
EOF

# ============================================================================
# 9. Create Directory Structure
# ============================================================================
log_info "Creating application directory structure..."
mkdir -p "${APP_DIR}"/{config,scripts,ssl,logs,backups}
chown -R "${APP_USER}:${APP_USER}" "${APP_DIR}"
chmod 700 "${APP_DIR}/ssl"

# ============================================================================
# 10. Setup Auto-Updates (Security only)
# ============================================================================
log_info "Configuring automatic security updates..."
apt-get install -y unattended-upgrades
cat > /etc/apt/apt.conf.d/50unattended-upgrades << 'EOF'
Unattended-Upgrade::Allowed-Origins {
    "${distro_id}:${distro_codename}-security";
    "${distro_id}ESMApps:${distro_codename}-apps-security";
    "${distro_id}ESM:${distro_codename}-infra-security";
};
Unattended-Upgrade::AutoFixInterruptedDpkg "true";
Unattended-Upgrade::MinimalSteps "true";
Unattended-Upgrade::InstallOnShutdown "false";
Unattended-Upgrade::Remove-Unused-Kernel-Packages "true";
Unattended-Upgrade::Remove-Unused-Dependencies "true";
Unattended-Upgrade::Automatic-Reboot "false";
EOF

# ============================================================================
# 11. Setup Backup Directory
# ============================================================================
log_info "Setting up backup directory..."
mkdir -p /var/backups/${APP_NAME}
chown ${APP_USER}:${APP_USER} /var/backups/${APP_NAME}

# ============================================================================
# Completion
# ============================================================================
log_info "Server initialization completed!"
echo ""
echo "Next steps:"
echo "  1. Copy your application code to ${APP_DIR}"
echo "  2. Configure environment variables in ${APP_DIR}/.env"
echo "  3. Obtain SSL certificates with: certbot certonly --standalone -d your-domain.com"
echo "  4. Copy certificates to ${APP_DIR}/ssl/"
echo "  5. Start services with: cd ${APP_DIR} && docker compose up -d"
echo ""
echo "Useful commands:"
echo "  - View logs: docker compose logs -f"
echo "  - Restart: docker compose restart"
echo "  - Update: docker compose pull && docker compose up -d"
