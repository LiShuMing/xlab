#!/bin/bash
# PyEgo MiniApp - Backup Script
# Usage: ./backup.sh [full|db|files]

set -e

# Configuration
APP_NAME="pyego"
APP_DIR="/opt/${APP_NAME}"
BACKUP_DIR="/var/backups/${APP_NAME}"
S3_BUCKET="${S3_BACKUP_BUCKET:-}"  # Optional: S3 bucket for offsite backups
RETENTION_DAYS=30
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DATE=$(date +%Y%m%d)

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info() { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Create backup directory
mkdir -p "$BACKUP_DIR"

# ============================================================================
# Database Backup
# ============================================================================
backup_database() {
    log_info "Backing up database..."

    local backup_file="${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz"

    # Check if database is running
    if ! docker ps | grep -q "${APP_NAME}-db"; then
        log_error "Database container is not running"
        return 1
    fi

    # Create backup
    docker exec "${APP_NAME}-db" pg_dump -U postgres pyego | gzip > "$backup_file"

    # Verify backup
    if [ -f "$backup_file" ] && [ -s "$backup_file" ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log_info "Database backup created: $backup_file ($size)"
    else
        log_error "Database backup failed"
        return 1
    fi
}

# ============================================================================
# Files Backup
# ============================================================================
backup_files() {
    log_info "Backing up configuration files..."

    local backup_file="${BACKUP_DIR}/files_${TIMESTAMP}.tar.gz"

    # Create archive of important files
    tar -czf "$backup_file" \
        -C "$APP_DIR" \
        .env \
        config/ \
        ssl/ \
        2>/dev/null || true

    if [ -f "$backup_file" ]; then
        local size=$(du -h "$backup_file" | cut -f1)
        log_info "Files backup created: $backup_file ($size)"
    fi
}

# ============================================================================
# Full Backup
# ============================================================================
backup_full() {
    log_info "Creating full backup..."

    local backup_file="${BACKUP_DIR}/full_${TIMESTAMP}.tar.gz"
    local temp_dir=$(mktemp -d)

    # Database backup
    backup_database
    cp "${BACKUP_DIR}/db_${TIMESTAMP}.sql.gz" "$temp_dir/"

    # Files backup
    backup_files
    cp "${BACKUP_DIR}/files_${TIMESTAMP}.tar.gz" "$temp_dir/"

    # Docker volumes backup
    log_info "Backing up Docker volumes..."
    docker run --rm \
        -v "${APP_NAME}_postgres_data":/source/postgres:ro \
        -v "${APP_NAME}_redis_data":/source/redis:ro \
        -v "$temp_dir":/backup \
        alpine tar czf /backup/volumes.tar.gz -C /source .

    # Create full archive
    tar -czf "$backup_file" -C "$temp_dir" .

    # Cleanup temp
    rm -rf "$temp_dir"

    local size=$(du -h "$backup_file" | cut -f1)
    log_info "Full backup created: $backup_file ($size)"

    # Upload to S3 if configured
    if [ -n "$S3_BUCKET" ]; then
        upload_to_s3 "$backup_file"
    fi
}

# ============================================================================
# Upload to S3 (optional)
# ============================================================================
upload_to_s3() {
    local file="$1"
    local filename=$(basename "$file")

    log_info "Uploading to S3..."

    if command -v aws &> /dev/null; then
        aws s3 cp "$file" "s3://${S3_BUCKET}/backups/${filename}"
        log_info "Uploaded to s3://${S3_BUCKET}/backups/${filename}"
    else
        log_warn "AWS CLI not installed, skipping S3 upload"
    fi
}

# ============================================================================
# Cleanup Old Backups
# ============================================================================
cleanup_old_backups() {
    log_info "Cleaning up old backups (retention: $RETENTION_DAYS days)..."

    local deleted=0

    # Count files before deletion
    local before_count=$(find "$BACKUP_DIR" -type f | wc -l)

    # Delete old backups
    find "$BACKUP_DIR" -name "*.sql.gz" -mtime +$RETENTION_DAYS -delete
    find "$BACKUP_DIR" -name "*.tar.gz" -mtime +$RETENTION_DAYS -delete

    # Count files after deletion
    local after_count=$(find "$BACKUP_DIR" -type f | wc -l)
    deleted=$((before_count - after_count))

    log_info "Cleanup complete. Removed $deleted old backup files."
}

# ============================================================================
# Main
# ============================================================================
main() {
    local command="${1:-full}"

    case "$command" in
        db)
            backup_database
            ;;
        files)
            backup_files
            ;;
        full)
            backup_full
            ;;
        cleanup)
            cleanup_old_backups
            exit 0
            ;;
        *)
            echo "Usage: $0 [full|db|files|cleanup]"
            echo ""
            echo "Commands:"
            echo "  full    - Full backup (database + files + volumes)"
            echo "  db      - Database backup only"
            echo "  files   - Configuration files backup only"
            echo "  cleanup - Remove old backups"
            exit 1
            ;;
    esac

    # Always cleanup old backups after creating new ones
    cleanup_old_backups

    log_info "Backup operation completed!"
}

main "$@"
