#!/bin/bash
# PyEgo MiniApp - Health Check Script
# Usage: ./health-check.sh
# Exit codes: 0 = healthy, 1 = unhealthy

set -e

# Configuration
APP_NAME="pyego"
APP_URL="${APP_URL:-http://localhost:8000}"
ALERT_WEBHOOK="${ALERT_WEBHOOK:-}"  # Optional: DingTalk/WeChat webhook

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[OK]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Track overall health
HEALTHY=true

# ============================================================================
# Check Docker Containers
# ============================================================================
check_containers() {
    echo "=== Docker Containers ==="

    local required_containers=("${APP_NAME}-app" "${APP_NAME}-db" "${APP_NAME}-redis" "${APP_NAME}-nginx")

    for container in "${required_containers[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${container}$"; then
            local status=$(docker inspect --format='{{.State.Status}}' "$container" 2>/dev/null)
            local health=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "N/A")

            if [ "$status" == "running" ]; then
                if [ "$health" == "N/A" ] || [ "$health" == "healthy" ]; then
                    log_info "$container: $status (health: $health)"
                else
                    log_warn "$container: $status (health: $health)"
                    HEALTHY=false
                fi
            else
                log_error "$container: $status"
                HEALTHY=false
            fi
        else
            log_error "$container: NOT RUNNING"
            HEALTHY=false
        fi
    done
    echo ""
}

# ============================================================================
# Check Application Health Endpoint
# ============================================================================
check_app_health() {
    echo "=== Application Health ==="

    local response
    local http_code

    response=$(curl -sf "${APP_URL}/health" 2>/dev/null)
    http_code=$?

    if [ $http_code -eq 0 ]; then
        log_info "Health endpoint: OK"
        echo "  Response: $response"
    else
        log_error "Health endpoint: FAILED (exit code: $http_code)"
        HEALTHY=false
    fi
    echo ""
}

# ============================================================================
# Check API Endpoints
# ============================================================================
check_api() {
    echo "=== API Endpoints ==="

    local endpoints=("/" "/health")

    for endpoint in "${endpoints[@]}"; do
        local url="${APP_URL}${endpoint}"
        local http_code=$(curl -s -o /dev/null -w "%{http_code}" "$url" 2>/dev/null)

        if [ "$http_code" == "200" ] || [ "$http_code" == "307" ]; then
            log_info "$endpoint: HTTP $http_code"
        else
            log_error "$endpoint: HTTP $http_code"
            HEALTHY=false
        fi
    done
    echo ""
}

# ============================================================================
# Check Database
# ============================================================================
check_database() {
    echo "=== Database ==="

    if docker exec "${APP_NAME}-db" pg_isready -U postgres > /dev/null 2>&1; then
        local db_size=$(docker exec "${APP_NAME}-db" psql -U postgres -t -c "SELECT pg_size_pretty(pg_database_size('pyego'));" 2>/dev/null | xargs)
        log_info "PostgreSQL: Connected"
        echo "  Database size: $db_size"
    else
        log_error "PostgreSQL: Connection failed"
        HEALTHY=false
    fi
    echo ""
}

# ============================================================================
# Check Redis
# ============================================================================
check_redis() {
    echo "=== Redis ==="

    if docker exec "${APP_NAME}-redis" redis-cli ping | grep -q "PONG"; then
        local info=$(docker exec "${APP_NAME}-redis" redis-cli info stats 2>/dev/null | grep -E "^(total_connections_received|total_commands_processed)" | head -2)
        log_info "Redis: Connected"
        echo "  $info"
    else
        log_error "Redis: Connection failed"
        HEALTHY=false
    fi
    echo ""
}

# ============================================================================
# Check Disk Space
# ============================================================================
check_disk() {
    echo "=== Disk Space ==="

    local usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')

    if [ "$usage" -lt 80 ]; then
        log_info "Root partition: ${usage}% used"
    elif [ "$usage" -lt 90 ]; then
        log_warn "Root partition: ${usage}% used"
    else
        log_error "Root partition: ${usage}% used - CRITICAL"
        HEALTHY=false
    fi

    # Docker volume usage
    local docker_usage=$(docker system df --format "{{.Size}}" 2>/dev/null | head -1)
    echo "  Docker usage: $docker_usage"
    echo ""
}

# ============================================================================
# Check Memory
# ============================================================================
check_memory() {
    echo "=== Memory ==="

    local mem_info=$(free -m | awk 'NR==2{printf "Used: %s/%sMB (%.2f%%)", $3,$2,$3*100/$2}')
    local mem_percent=$(free | awk 'NR==2{printf "%.0f", $3*100/$2}')

    if [ "$mem_percent" -lt 80 ]; then
        log_info "Memory: $mem_info"
    elif [ "$mem_percent" -lt 90 ]; then
        log_warn "Memory: $mem_info"
    else
        log_error "Memory: $mem_info - HIGH"
    fi
    echo ""
}

# ============================================================================
# Send Alert (optional)
# ============================================================================
send_alert() {
    local message="$1"

    if [ -n "$ALERT_WEBHOOK" ]; then
        curl -s -X POST "$ALERT_WEBHOOK" \
            -H "Content-Type: application/json" \
            -d "{\"msgtype\": \"text\", \"text\": {\"content\": \"$message\"}}" \
            > /dev/null 2>&1 || true
    fi
}

# ============================================================================
# Main
# ============================================================================
main() {
    echo "PyEgo MiniApp Health Check"
    echo "=========================="
    echo "Time: $(date)"
    echo "URL: $APP_URL"
    echo ""

    check_containers
    check_app_health
    check_api
    check_database
    check_redis
    check_disk
    check_memory

    echo "=========================="
    if [ "$HEALTHY" = true ]; then
        log_info "All checks passed! System is healthy."
        exit 0
    else
        log_error "Some checks failed! System is unhealthy."
        send_alert "[ALERT] PyEgo health check failed at $(date)"
        exit 1
    fi
}

main
