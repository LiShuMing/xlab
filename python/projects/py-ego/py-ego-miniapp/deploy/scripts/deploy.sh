#!/bin/bash
# PyEgo MiniApp - Deployment Script
# Usage: ./deploy.sh [environment]
#   environment: development (default) | production

set -e

# Configuration
APP_NAME="pyego"
APP_DIR="/opt/${APP_NAME}"
ENVIRONMENT="${1:-development}"
BACKUP_DIR="/var/backups/${APP_NAME}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }
log_step() { echo -e "${BLUE}[STEP]${NC} $1"; }

# ============================================================================
# Pre-deployment Checks
# ============================================================================
log_step "Running pre-deployment checks..."

# Check if running from correct directory
if [ ! -f "docker-compose.yml" ]; then
    log_error "docker-compose.yml not found. Please run from deploy directory."
    exit 1
fi

# Check environment file
if [ ! -f ".env" ]; then
    log_error ".env file not found. Please create it from .env.example"
    exit 1
fi

# Check Docker
if ! docker info > /dev/null 2>&1; then
    log_error "Docker is not running"
    exit 1
fi

# Check SSL certificates for production
if [ "$ENVIRONMENT" == "production" ]; then
    if [ ! -f "ssl/fullchain.pem" ] || [ ! -f "ssl/privkey.pem" ]; then
        log_warn "SSL certificates not found in ssl/"
        log_warn "Obtain them with: certbot certonly --standalone -d your-domain.com"
        log_warn "Then copy to ssl/:"
        log_warn "  sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ssl/"
        log_warn "  sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ssl/"
        log_warn "  sudo chown -R $(whoami):$(whoami) ssl/"
        exit 1
    fi
fi

log_info "Pre-deployment checks passed"

# ============================================================================
# Backup (Production only)
# ============================================================================
if [ "$ENVIRONMENT" == "production" ]; then
    log_step "Creating backup..."
    mkdir -p "$BACKUP_DIR"

    # Backup database
    if docker compose ps | grep -q "db"; then
        log_info "Backing up database..."
        docker compose exec -T db pg_dump -U postgres pyego | gzip > "${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
        log_info "Database backup created: ${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"
    fi

    # Backup environment file
    cp .env "${BACKUP_DIR}/env_${TIMESTAMP}"

    # Cleanup old backups (keep 7 days)
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +7 -delete
    find "$BACKUP_DIR" -name "env_*" -mtime +7 -delete
fi

# ============================================================================
# Build and Deploy
# ============================================================================
log_step "Building and deploying..."

# Pull latest images
docker compose pull

# Build application image
docker compose build --no-cache app

# Stop existing services gracefully
log_info "Stopping existing services..."
docker compose down --timeout 30

# Start services
log_info "Starting services..."
if [ "$ENVIRONMENT" == "production" ]; then
    docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d
else
    docker compose up -d
fi

# ============================================================================
# Post-deployment
# ============================================================================
log_step "Running post-deployment tasks..."

# Wait for services to be ready
log_info "Waiting for services to be ready..."
sleep 5

# Check health
log_info "Checking service health..."
MAX_RETRIES=30
RETRY_COUNT=0

while [ $RETRY_COUNT -lt $MAX_RETRIES ]; do
    if curl -sf http://localhost:8000/health > /dev/null 2>&1; then
        log_info "Application is healthy!"
        break
    fi

    RETRY_COUNT=$((RETRY_COUNT + 1))
    log_warn "Health check failed, retrying ($RETRY_COUNT/$MAX_RETRIES)..."
    sleep 2
done

if [ $RETRY_COUNT -eq $MAX_RETRIES ]; then
    log_error "Health check failed after $MAX_RETRIES attempts"
    log_error "Check logs with: docker compose logs -f app"
    exit 1
fi

# Run database migrations (if needed)
log_info "Running database migrations..."
docker compose exec -T app alembic upgrade head || log_warn "Migration skipped or failed"

# Cleanup old images
log_info "Cleaning up old Docker images..."
docker image prune -af --filter "until=168h" || true

# ============================================================================
# Summary
# ============================================================================
log_step "Deployment completed successfully!"
echo ""
echo "Service Status:"
docker compose ps
echo ""
echo "Useful commands:"
echo "  - View logs: docker compose logs -f"
echo "  - App logs: docker compose logs -f app"
echo "  - Restart: docker compose restart app"
echo "  - Shell: docker compose exec app bash"
