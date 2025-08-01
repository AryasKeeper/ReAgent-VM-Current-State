#!/bin/bash

# ReAgent Sydney - Complete System Backup Script
# Comprehensive backup of all system components

set -euo pipefail

# Configuration
BACKUP_BASE_DIR="./backups"
DATE=$(date +%Y%m%d_%H%M%S)
RETENTION_DAYS=30
S3_BUCKET="${S3_BACKUP_BUCKET:-}"
AWS_REGION="${S3_REGION:-ap-southeast-2}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
LOG_FILE="./logs/backup_$DATE.log"
mkdir -p "$(dirname "$LOG_FILE")"

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" | tee -a "$LOG_FILE" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" | tee -a "$LOG_FILE" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" | tee -a "$LOG_FILE" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" | tee -a "$LOG_FILE" ;;
    esac
}

# Check prerequisites
check_prerequisites() {
    log INFO "Checking prerequisites..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log ERROR "Docker is not running or not accessible"
        exit 1
    fi
    
    # Check if containers are running
    local required_containers=("reagent-postgres" "reagent-redis-master" "reagent-weaviate")
    for container in "${required_containers[@]}"; do
        if ! docker ps --format "table {{.Names}}" | grep -q "^$container$"; then
            log WARN "Container $container is not running"
        fi
    done
    
    # Create backup directories
    mkdir -p "$BACKUP_BASE_DIR"/{postgres,redis,weaviate,grafana,prometheus,configs,logs}
    
    log INFO "Prerequisites check completed"
}

# PostgreSQL backup
backup_postgresql() {
    log INFO "Starting PostgreSQL backup..."
    
    local backup_dir="$BACKUP_BASE_DIR/postgres"
    local backup_file="$backup_dir/reagent_$DATE.sql"
    
    # Get password from secrets
    local postgres_password
    if [[ -f "./secrets/postgres_password.txt" ]]; then
        postgres_password=$(cat ./secrets/postgres_password.txt)
    else
        log ERROR "PostgreSQL password file not found"
        return 1
    fi
    
    # Create SQL dump
    log INFO "Creating PostgreSQL database dump..."
    if docker exec -e PGPASSWORD="$postgres_password" reagent-postgres \
        pg_dump -h localhost -U reagent -d reagent \
        --verbose --no-owner --no-privileges \
        --exclude-table-data=agent_logs > "$backup_file" 2>>"$LOG_FILE"; then
        log INFO "PostgreSQL dump created successfully"
    else
        log ERROR "Failed to create PostgreSQL dump"
        return 1
    fi
    
    # Create custom format backup (smaller, faster restore)
    local custom_backup="$backup_dir/reagent_$DATE.dump"
    if docker exec -e PGPASSWORD="$postgres_password" reagent-postgres \
        pg_dump -h localhost -U reagent -d reagent \
        --format=custom --compress=9 \
        --exclude-table-data=agent_logs > "$custom_backup" 2>>"$LOG_FILE"; then
        log INFO "PostgreSQL custom format backup created"
    else
        log WARN "Failed to create custom format backup"
    fi
    
    # Backup TimescaleDB continuous aggregates metadata
    local ts_metadata="$backup_dir/timescaledb_metadata_$DATE.sql"
    docker exec -e PGPASSWORD="$postgres_password" reagent-postgres \
        pg_dump -h localhost -U reagent -d reagent \
        --schema-only --table="_timescaledb_*" > "$ts_metadata" 2>>"$LOG_FILE"
    
    # Compress backups
    gzip "$backup_file" "$custom_backup" "$ts_metadata"
    
    # Calculate backup size
    local backup_size=$(du -sh "$backup_dir"/reagent_$DATE.* | awk '{print $1}')
    log INFO "PostgreSQL backup completed. Size: $backup_size"
}

# Redis backup
backup_redis() {
    log INFO "Starting Redis backup..."
    
    local backup_dir="$BACKUP_BASE_DIR/redis"
    local backup_file="$backup_dir/dump_$DATE.rdb"
    
    # Create Redis backup using BGSAVE
    log INFO "Triggering Redis background save..."
    if docker exec reagent-redis-master redis-cli BGSAVE >/dev/null; then
        log INFO "Redis BGSAVE initiated"
        
        # Wait for BGSAVE to complete
        while docker exec reagent-redis-master redis-cli LASTSAVE | grep -q "$(docker exec reagent-redis-master redis-cli LASTSAVE)"; do
            sleep 2
        done
        
        # Copy the RDB file
        docker cp reagent-redis-master:/data/dump.rdb "$backup_file"
        
        # Also backup Redis configuration
        docker exec reagent-redis-master redis-cli CONFIG GET "*" > "$backup_dir/redis_config_$DATE.txt"
        
        gzip "$backup_file" "$backup_dir/redis_config_$DATE.txt"
        
        local backup_size=$(du -sh "$backup_file.gz" | awk '{print $1}')
        log INFO "Redis backup completed. Size: $backup_size"
    else
        log ERROR "Failed to create Redis backup"
        return 1
    fi
}

# Weaviate backup
backup_weaviate() {
    log INFO "Starting Weaviate backup..."
    
    local backup_dir="$BACKUP_BASE_DIR/weaviate"
    local weaviate_key=$(cat ./secrets/weaviate_api_key.txt 2>/dev/null || echo "")
    
    # Create Weaviate backup using API
    if [[ -n "$weaviate_key" ]]; then
        local backup_id="reagent_backup_$DATE"
        
        # Trigger backup
        if curl -s -X POST \
            -H "Authorization: Bearer $weaviate_key" \
            -H "Content-Type: application/json" \
            -d "{\"id\": \"$backup_id\"}" \
            "http://localhost:8080/v1/backups/filesystem" >/dev/null; then
            
            log INFO "Weaviate backup initiated with ID: $backup_id"
            
            # Wait for backup to complete
            local status="STARTED"
            while [[ "$status" == "STARTED" || "$status" == "TRANSFERRING" ]]; do
                sleep 5
                status=$(curl -s -H "Authorization: Bearer $weaviate_key" \
                    "http://localhost:8080/v1/backups/filesystem/$backup_id" | \
                    jq -r '.status' 2>/dev/null || echo "UNKNOWN")
            done
            
            if [[ "$status" == "SUCCESS" ]]; then
                # Copy backup files from container
                docker cp reagent-weaviate:/var/lib/weaviate/backups "$backup_dir/weaviate_$DATE"
                
                # Compress backup
                tar -czf "$backup_dir/weaviate_$DATE.tar.gz" -C "$backup_dir" "weaviate_$DATE"
                rm -rf "$backup_dir/weaviate_$DATE"
                
                local backup_size=$(du -sh "$backup_dir/weaviate_$DATE.tar.gz" | awk '{print $1}')
                log INFO "Weaviate backup completed. Size: $backup_size"
            else
                log ERROR "Weaviate backup failed with status: $status"
                return 1
            fi
        else
            log ERROR "Failed to initiate Weaviate backup"
            return 1
        fi
    else
        log WARN "Weaviate API key not found, skipping vector database backup"
    fi
}

# Grafana backup
backup_grafana() {
    log INFO "Starting Grafana backup..."
    
    local backup_dir="$BACKUP_BASE_DIR/grafana"
    
    # Copy Grafana data directory
    docker cp reagent-grafana:/var/lib/grafana "$backup_dir/grafana_data_$DATE"
    
    # Export Grafana dashboards via API
    local admin_password="${GRAFANA_ADMIN_PASSWORD:-admin}"
    mkdir -p "$backup_dir/dashboards_$DATE"
    
    # Get list of dashboards
    local dashboard_uids=$(curl -s -u "admin:$admin_password" \
        "http://localhost:3001/api/search?type=dash-db" | \
        jq -r '.[].uid' 2>/dev/null || echo "")
    
    if [[ -n "$dashboard_uids" ]]; then
        for uid in $dashboard_uids; do
            curl -s -u "admin:$admin_password" \
                "http://localhost:3001/api/dashboards/uid/$uid" | \
                jq '.dashboard' > "$backup_dir/dashboards_$DATE/dashboard_$uid.json" 2>/dev/null || true
        done
        log INFO "Exported Grafana dashboards"
    fi
    
    # Compress backup
    tar -czf "$backup_dir/grafana_$DATE.tar.gz" -C "$backup_dir" \
        "grafana_data_$DATE" "dashboards_$DATE" 2>/dev/null || true
    rm -rf "$backup_dir/grafana_data_$DATE" "$backup_dir/dashboards_$DATE"
    
    local backup_size=$(du -sh "$backup_dir/grafana_$DATE.tar.gz" | awk '{print $1}')
    log INFO "Grafana backup completed. Size: $backup_size"
}

# Prometheus backup
backup_prometheus() {
    log INFO "Starting Prometheus backup..."
    
    local backup_dir="$BACKUP_BASE_DIR/prometheus"
    
    # Snapshot Prometheus data
    if curl -s -X POST "http://localhost:9090/api/v1/admin/tsdb/snapshot" >/dev/null; then
        log INFO "Prometheus snapshot created"
        
        # Copy snapshot data
        docker cp reagent-prometheus:/prometheus/snapshots "$backup_dir/prometheus_snapshots_$DATE"
        
        # Also backup Prometheus configuration
        cp -r ./monitoring/prometheus "$backup_dir/prometheus_config_$DATE"
        
        # Compress backup
        tar -czf "$backup_dir/prometheus_$DATE.tar.gz" -C "$backup_dir" \
            "prometheus_snapshots_$DATE" "prometheus_config_$DATE"
        rm -rf "$backup_dir/prometheus_snapshots_$DATE" "$backup_dir/prometheus_config_$DATE"
        
        local backup_size=$(du -sh "$backup_dir/prometheus_$DATE.tar.gz" | awk '{print $1}')
        log INFO "Prometheus backup completed. Size: $backup_size"
    else
        log ERROR "Failed to create Prometheus snapshot"
        return 1
    fi
}

# Configuration backup
backup_configurations() {
    log INFO "Backing up system configurations..."
    
    local backup_dir="$BACKUP_BASE_DIR/configs"
    local config_backup="$backup_dir/configs_$DATE"
    
    mkdir -p "$config_backup"
    
    # Copy configuration files
    cp -r ./config "$config_backup/"
    cp -r ./monitoring "$config_backup/"
    cp docker-compose*.yml "$config_backup/" 2>/dev/null || true
    cp .env.production* "$config_backup/" 2>/dev/null || true
    cp -r ./sql "$config_backup/" 2>/dev/null || true
    
    # Copy secrets (encrypted)
    if command -v gpg >/dev/null 2>&1; then
        tar -czf - ./secrets | gpg --symmetric --cipher-algo AES256 --output "$config_backup/secrets_encrypted.tar.gz.gpg"
        log INFO "Secrets backed up with GPG encryption"
    else
        log WARN "GPG not available, copying secrets without encryption"
        cp -r ./secrets "$config_backup/"
    fi
    
    # Compress configurations
    tar -czf "$backup_dir/configs_$DATE.tar.gz" -C "$backup_dir" "configs_$DATE"
    rm -rf "$config_backup"
    
    local backup_size=$(du -sh "$backup_dir/configs_$DATE.tar.gz" | awk '{print $1}')
    log INFO "Configuration backup completed. Size: $backup_size"
}

# Upload to S3 (if configured)
upload_to_s3() {
    if [[ -z "$S3_BUCKET" ]]; then
        log INFO "S3 backup not configured, skipping upload"
        return 0
    fi
    
    log INFO "Uploading backups to S3..."
    
    if ! command -v aws >/dev/null 2>&1; then
        log ERROR "AWS CLI not found, cannot upload to S3"
        return 1
    fi
    
    # Upload all backup files
    for backup_type in postgres redis weaviate grafana prometheus configs; do
        local backup_files=$(find "$BACKUP_BASE_DIR/$backup_type" -name "*_$DATE.*" -type f 2>/dev/null || true)
        
        for file in $backup_files; do
            local s3_path="s3://$S3_BUCKET/reagent-backups/$(date +%Y/%m/%d)/$(basename "$file")"
            
            if aws s3 cp "$file" "$s3_path" --region "$AWS_REGION" --storage-class STANDARD_IA; then
                log INFO "Uploaded $(basename "$file") to S3"
            else
                log ERROR "Failed to upload $(basename "$file") to S3"
            fi
        done
    done
}

# Cleanup old backups
cleanup_old_backups() {
    log INFO "Cleaning up backups older than $RETENTION_DAYS days..."
    
    for backup_type in postgres redis weaviate grafana prometheus configs; do
        local backup_dir="$BACKUP_BASE_DIR/$backup_type"
        if [[ -d "$backup_dir" ]]; then
            find "$backup_dir" -type f -mtime +"$RETENTION_DAYS" -delete 2>/dev/null || true
            local removed=$(find "$backup_dir" -type f -mtime +"$RETENTION_DAYS" 2>/dev/null | wc -l || echo 0)
            if [[ $removed -gt 0 ]]; then
                log INFO "Removed $removed old backup files from $backup_type"
            fi
        fi
    done
}

# Generate backup report
generate_backup_report() {
    log INFO "Generating backup report..."
    
    local report_file="./logs/backup_report_$DATE.txt"
    
    cat << EOF > "$report_file"
ReAgent Sydney - Backup Report
==============================
Date: $(date)
Backup ID: $DATE

Backup Status:
EOF
    
    # Check each component backup
    for backup_type in postgres redis weaviate grafana prometheus configs; do
        local backup_dir="$BACKUP_BASE_DIR/$backup_type"
        local backup_files=$(find "$backup_dir" -name "*_$DATE.*" -type f 2>/dev/null | wc -l)
        local total_size=$(du -sh "$backup_dir" 2>/dev/null | awk '{print $1}' || echo "0B")
        
        echo "- $backup_type: $backup_files files, $total_size total" >> "$report_file"
    done
    
    echo "" >> "$report_file"
    echo "Total backup size: $(du -sh "$BACKUP_BASE_DIR" | awk '{print $1}')" >> "$report_file"
    echo "Backup location: $BACKUP_BASE_DIR" >> "$report_file"
    
    if [[ -n "$S3_BUCKET" ]]; then
        echo "S3 backup location: s3://$S3_BUCKET/reagent-backups/$(date +%Y/%m/%d)/" >> "$report_file"
    fi
    
    log INFO "Backup report generated: $report_file"
}

# Main backup function
run_backup() {
    local start_time=$(date +%s)
    
    log INFO "Starting complete system backup for ReAgent Sydney"
    log INFO "Backup ID: $DATE"
    
    # Run all backup components
    check_prerequisites
    
    local failed_components=()
    
    backup_postgresql || failed_components+=("postgresql")
    backup_redis || failed_components+=("redis")
    backup_weaviate || failed_components+=("weaviate")
    backup_grafana || failed_components+=("grafana")
    backup_prometheus || failed_components+=("prometheus")
    backup_configurations || failed_components+=("configurations")
    
    upload_to_s3 || log WARN "S3 upload had issues"
    cleanup_old_backups
    generate_backup_report
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [[ ${#failed_components[@]} -eq 0 ]]; then
        log INFO "Complete system backup finished successfully in ${duration}s"
        return 0
    else
        log ERROR "Backup completed with failures in: ${failed_components[*]}"
        return 1
    fi
}

# Script entry point
main() {
    case "${1:-backup}" in
        backup)
            run_backup
            ;;
        postgresql|postgres)
            check_prerequisites
            backup_postgresql
            ;;
        redis)
            check_prerequisites
            backup_redis
            ;;
        weaviate)
            check_prerequisites
            backup_weaviate
            ;;
        grafana)
            check_prerequisites
            backup_grafana
            ;;
        prometheus)
            check_prerequisites
            backup_prometheus
            ;;
        configs)
            check_prerequisites
            backup_configurations
            ;;
        *)
            echo "Usage: $0 [backup|postgresql|redis|weaviate|grafana|prometheus|configs]"
            exit 1
            ;;
    esac
}

# Run main function with all arguments
main "$@"