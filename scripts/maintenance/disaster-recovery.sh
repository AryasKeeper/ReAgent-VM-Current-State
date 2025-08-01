#!/bin/bash

# ReAgent Sydney - Disaster Recovery Script
# Complete system restoration from backups

set -euo pipefail

# Configuration
BACKUP_BASE_DIR="./backups"
RESTORE_DATE="${1:-latest}"
S3_BUCKET="${S3_BACKUP_BUCKET:-}"
AWS_REGION="${S3_REGION:-ap-southeast-2}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
LOG_FILE="./logs/restore_$(date +%Y%m%d_%H%M%S).log"
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

# Find latest backup
find_backup_files() {
    local component=$1
    local backup_dir="$BACKUP_BASE_DIR/$component"
    
    if [[ "$RESTORE_DATE" == "latest" ]]; then
        find "$backup_dir" -name "*_[0-9]*.*" -type f | sort | tail -1
    else
        find "$backup_dir" -name "*_${RESTORE_DATE}*.*" -type f | head -1
    fi
}

# Download from S3 if needed
download_from_s3() {
    if [[ -z "$S3_BUCKET" ]]; then
        return 0
    fi
    
    log INFO "Downloading backups from S3..."
    
    # Download latest backups if not present locally
    if [[ "$RESTORE_DATE" == "latest" ]]; then
        local s3_prefix="s3://$S3_BUCKET/reagent-backups/"
        aws s3 sync "$s3_prefix" "$BACKUP_BASE_DIR" --region "$AWS_REGION" || log WARN "S3 download failed"
    fi
}

# Pre-restoration checks
pre_restore_checks() {
    log INFO "Performing pre-restoration checks..."
    
    # Check if Docker is running
    if ! docker info >/dev/null 2>&1; then
        log ERROR "Docker is not running"
        exit 1
    fi
    
    # Warn about data loss
    echo -e "${RED}WARNING: This will DESTROY current data and restore from backup!${NC}"
    echo -e "${RED}Current data will be permanently lost!${NC}"
    echo
    read -p "Are you sure you want to continue? (type 'YES' to confirm): " confirm
    
    if [[ "$confirm" != "YES" ]]; then
        log INFO "Restoration cancelled by user"
        exit 0
    fi
    
    # Stop all services
    log INFO "Stopping all ReAgent services..."
    docker-compose -f docker-compose.prod.yml down || log WARN "Some services may not have been running"
    
    # Create backup of current data (just in case)
    if [[ -d "./data" ]]; then
        log INFO "Creating emergency backup of current data..."
        mv "./data" "./data_emergency_backup_$(date +%Y%m%d_%H%M%S)" || log WARN "Could not backup current data"
    fi
    
    mkdir -p "./data"/{postgres,postgres_replica,redis_master,weaviate,grafana,prometheus,alertmanager}
}

# Restore PostgreSQL
restore_postgresql() {
    log INFO "Restoring PostgreSQL database..."
    
    local backup_file=$(find_backup_files "postgres")
    if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
        log ERROR "PostgreSQL backup file not found"
        return 1
    fi
    
    log INFO "Using backup file: $backup_file"
    
    # Start only PostgreSQL for restoration
    docker-compose -f docker-compose.prod.yml up -d postgres
    
    # Wait for PostgreSQL to be ready
    log INFO "Waiting for PostgreSQL to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if docker exec reagent-postgres pg_isready -U reagent -d reagent >/dev/null 2>&1; then
            break
        fi
        sleep 2
        ((attempt++))
    done
    
    if [[ $attempt -eq $max_attempts ]]; then
        log ERROR "PostgreSQL failed to start within timeout"
        return 1
    fi
    
    # Get password
    local postgres_password=$(cat ./secrets/postgres_password.txt)
    
    # Drop existing database and recreate
    log INFO "Recreating database..."
    docker exec -e PGPASSWORD="$postgres_password" reagent-postgres \
        psql -U reagent -d postgres -c "DROP DATABASE IF EXISTS reagent;"
    docker exec -e PGPASSWORD="$postgres_password" reagent-postgres \
        psql -U reagent -d postgres -c "CREATE DATABASE reagent;"
    
    # Restore from backup
    log INFO "Restoring database from backup..."
    
    if [[ "$backup_file" == *.sql.gz ]]; then
        # SQL format restore
        gunzip -c "$backup_file" | docker exec -i -e PGPASSWORD="$postgres_password" reagent-postgres \
            psql -U reagent -d reagent
    elif [[ "$backup_file" == *.dump.gz ]]; then
        # Custom format restore
        gunzip -c "$backup_file" | docker exec -i -e PGPASSWORD="$postgres_password" reagent-postgres \
            pg_restore -U reagent -d reagent --no-owner --no-privileges
    else
        log ERROR "Unknown backup format: $backup_file"
        return 1
    fi
    
    # Restore TimescaleDB hypertables
    log INFO "Recreating TimescaleDB hypertables..."
    docker exec -e PGPASSWORD="$postgres_password" reagent-postgres \
        psql -U reagent -d reagent -c "SELECT setup_timescale_hypertables();" || log WARN "Failed to setup hypertables"
    
    # Update statistics
    docker exec -e PGPASSWORD="$postgres_password" reagent-postgres \
        psql -U reagent -d reagent -c "ANALYZE;" || log WARN "Failed to analyze database"
    
    log INFO "PostgreSQL restoration completed"
}

# Restore Redis
restore_redis() {
    log INFO "Restoring Redis data..."
    
    local backup_file=$(find_backup_files "redis")
    if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
        log ERROR "Redis backup file not found"
        return 1
    fi
    
    log INFO "Using backup file: $backup_file"
    
    # Extract RDB file
    local temp_dir=$(mktemp -d)
    if [[ "$backup_file" == *.gz ]]; then
        gunzip -c "$backup_file" > "$temp_dir/dump.rdb"
    else
        cp "$backup_file" "$temp_dir/dump.rdb"
    fi
    
    # Copy RDB file to Redis data directory
    mkdir -p "./data/redis_master"
    cp "$temp_dir/dump.rdb" "./data/redis_master/"
    
    # Start Redis
    docker-compose -f docker-compose.prod.yml up -d redis-master
    
    # Wait for Redis to load data
    sleep 5
    
    # Verify data loaded
    local key_count=$(docker exec reagent-redis-master redis-cli DBSIZE)
    log INFO "Redis restoration completed. Restored $key_count keys"
    
    # Cleanup
    rm -rf "$temp_dir"
}

# Restore Weaviate
restore_weaviate() {
    log INFO "Restoring Weaviate vector database..."
    
    local backup_file=$(find_backup_files "weaviate")
    if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
        log ERROR "Weaviate backup file not found"
        return 1
    fi
    
    log INFO "Using backup file: $backup_file"
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Copy to Weaviate data directory
    mkdir -p "./data/weaviate"
    cp -r "$temp_dir"/*/* "./data/weaviate/" 2>/dev/null || true
    
    # Start Weaviate
    docker-compose -f docker-compose.prod.yml up -d weaviate
    
    # Wait for Weaviate to be ready
    log INFO "Waiting for Weaviate to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if curl -s -f "http://localhost:8080/v1/.well-known/ready" >/dev/null 2>&1; then
            break
        fi
        sleep 5
        ((attempt++))
    done
    
    if [[ $attempt -eq $max_attempts ]]; then
        log ERROR "Weaviate failed to start within timeout"
        return 1
    fi
    
    log INFO "Weaviate restoration completed"
    
    # Cleanup
    rm -rf "$temp_dir"
}

# Restore Grafana
restore_grafana() {
    log INFO "Restoring Grafana configuration..."
    
    local backup_file=$(find_backup_files "grafana")
    if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
        log ERROR "Grafana backup file not found"
        return 1
    fi
    
    log INFO "Using backup file: $backup_file"
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Copy to Grafana data directory
    mkdir -p "./data/grafana"
    cp -r "$temp_dir"/grafana_data_*/* "./data/grafana/" 2>/dev/null || true
    
    # Start Grafana
    docker-compose -f docker-compose.monitoring.yml up -d grafana
    
    log INFO "Grafana restoration completed"
    
    # Cleanup
    rm -rf "$temp_dir"
}

# Restore Prometheus
restore_prometheus() {
    log INFO "Restoring Prometheus data..."
    
    local backup_file=$(find_backup_files "prometheus")
    if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
        log ERROR "Prometheus backup file not found"
        return 1
    fi
    
    log INFO "Using backup file: $backup_file"
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Copy snapshots to Prometheus data directory
    mkdir -p "./data/prometheus"
    cp -r "$temp_dir"/prometheus_snapshots_*/* "./data/prometheus/" 2>/dev/null || true
    
    # Start Prometheus
    docker-compose -f docker-compose.monitoring.yml up -d prometheus
    
    log INFO "Prometheus restoration completed"
    
    # Cleanup
    rm -rf "$temp_dir"
}

# Restore configurations
restore_configurations() {
    log INFO "Restoring system configurations..."
    
    local backup_file=$(find_backup_files "configs")
    if [[ -z "$backup_file" || ! -f "$backup_file" ]]; then
        log ERROR "Configuration backup file not found"
        return 1
    fi
    
    log INFO "Using backup file: $backup_file"
    
    # Extract backup
    local temp_dir=$(mktemp -d)
    tar -xzf "$backup_file" -C "$temp_dir"
    
    # Restore configurations (with confirmation)
    echo -e "${YELLOW}WARNING: This will overwrite current configuration files!${NC}"
    read -p "Restore configurations? (y/N): " restore_configs
    
    if [[ "$restore_configs" =~ ^[Yy]$ ]]; then
        # Backup current configs
        [[ -d "./config" ]] && mv "./config" "./config_backup_$(date +%Y%m%d_%H%M%S)"
        [[ -d "./monitoring" ]] && mv "./monitoring" "./monitoring_backup_$(date +%Y%m%d_%H%M%S)"
        
        # Restore configs
        cp -r "$temp_dir"/configs_*/config . 2>/dev/null || true
        cp -r "$temp_dir"/configs_*/monitoring . 2>/dev/null || true
        cp "$temp_dir"/configs_*/docker-compose*.yml . 2>/dev/null || true
        
        # Restore secrets (if GPG encrypted)
        if [[ -f "$temp_dir"/configs_*/secrets_encrypted.tar.gz.gpg ]]; then
            if command -v gpg >/dev/null 2>&1; then
                gpg --decrypt "$temp_dir"/configs_*/secrets_encrypted.tar.gz.gpg | tar -xzf - || log WARN "Failed to decrypt secrets"
            else
                log WARN "GPG not available, cannot decrypt secrets"
            fi
        elif [[ -d "$temp_dir"/configs_*/secrets ]]; then
            # Backup current secrets
            [[ -d "./secrets" ]] && mv "./secrets" "./secrets_backup_$(date +%Y%m%d_%H%M%S)"
            cp -r "$temp_dir"/configs_*/secrets . 2>/dev/null || true
        fi
        
        log INFO "Configuration restoration completed"
    else
        log INFO "Configuration restoration skipped"
    fi
    
    # Cleanup
    rm -rf "$temp_dir"
}

# Start all services
start_all_services() {
    log INFO "Starting all ReAgent services..."
    
    # Start core services first
    docker-compose -f docker-compose.prod.yml up -d postgres redis-master weaviate
    
    # Wait for core services
    sleep 30
    
    # Start application services
    docker-compose -f docker-compose.prod.yml up -d
    
    # Start monitoring services
    docker-compose -f docker-compose.monitoring.yml up -d
    
    log INFO "All services started"
}

# Post-restoration validation
post_restore_validation() {
    log INFO "Performing post-restoration validation..."
    
    local errors=0
    
    # Check PostgreSQL
    if docker exec reagent-postgres pg_isready -U reagent -d reagent >/dev/null 2>&1; then
        local table_count=$(docker exec -e PGPASSWORD="$(cat ./secrets/postgres_password.txt)" reagent-postgres \
            psql -U reagent -d reagent -t -c "SELECT COUNT(*) FROM information_schema.tables WHERE table_schema = 'public';" | tr -d ' ')
        log INFO "PostgreSQL: OK ($table_count tables)"
    else
        log ERROR "PostgreSQL: FAILED"
        ((errors++))
    fi
    
    # Check Redis
    if docker exec reagent-redis-master redis-cli ping >/dev/null 2>&1; then
        local key_count=$(docker exec reagent-redis-master redis-cli DBSIZE)
        log INFO "Redis: OK ($key_count keys)"
    else
        log ERROR "Redis: FAILED"
        ((errors++))
    fi
    
    # Check Weaviate
    if curl -s -f "http://localhost:8080/v1/.well-known/ready" >/dev/null 2>&1; then
        log INFO "Weaviate: OK"
    else
        log ERROR "Weaviate: FAILED"
        ((errors++))
    fi
    
    # Check API
    sleep 10  # Give API time to start
    if curl -s -f "http://localhost:8000/health" >/dev/null 2>&1; then
        log INFO "ReAgent API: OK"
    else
        log ERROR "ReAgent API: FAILED"
        ((errors++))
    fi
    
    if [[ $errors -eq 0 ]]; then
        log INFO "Post-restoration validation: PASSED"
        return 0
    else
        log ERROR "Post-restoration validation: FAILED ($errors errors)"
        return 1
    fi
}

# Generate restoration report
generate_restore_report() {
    log INFO "Generating restoration report..."
    
    local report_file="./logs/restore_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat << EOF > "$report_file"
ReAgent Sydney - Disaster Recovery Report
========================================
Date: $(date)
Restore Date: $RESTORE_DATE

Restoration Status:
- PostgreSQL: $(docker exec reagent-postgres pg_isready -U reagent -d reagent >/dev/null 2>&1 && echo "OK" || echo "FAILED")
- Redis: $(docker exec reagent-redis-master redis-cli ping >/dev/null 2>&1 && echo "OK" || echo "FAILED")
- Weaviate: $(curl -s -f "http://localhost:8080/v1/.well-known/ready" >/dev/null 2>&1 && echo "OK" || echo "FAILED")
- Grafana: $(curl -s -f "http://localhost:3001/api/health" >/dev/null 2>&1 && echo "OK" || echo "FAILED")
- Prometheus: $(curl -s -f "http://localhost:9090/-/ready" >/dev/null 2>&1 && echo "OK" || echo "FAILED")

Service Status:
EOF
    
    docker-compose -f docker-compose.prod.yml ps >> "$report_file"
    
    log INFO "Restoration report generated: $report_file"
}

# Main restoration function
run_full_restore() {
    local start_time=$(date +%s)
    
    log INFO "Starting disaster recovery for ReAgent Sydney"
    log INFO "Restore date: $RESTORE_DATE"
    
    download_from_s3
    pre_restore_checks
    
    local failed_components=()
    
    restore_postgresql || failed_components+=("postgresql")
    restore_redis || failed_components+=("redis")
    restore_weaviate || failed_components+=("weaviate")
    restore_grafana || failed_components+=("grafana")
    restore_prometheus || failed_components+=("prometheus")
    restore_configurations
    
    start_all_services
    
    if post_restore_validation; then
        log INFO "Post-restoration validation passed"
    else
        failed_components+=("validation")
    fi
    
    generate_restore_report
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [[ ${#failed_components[@]} -eq 0 ]]; then
        log INFO "Disaster recovery completed successfully in ${duration}s"
        echo
        echo -e "${GREEN}ReAgent Sydney has been successfully restored!${NC}"
        echo "Access points:"
        echo "- API: http://localhost:8000"
        echo "- Grafana: http://localhost:3001"
        echo "- Prometheus: http://localhost:9090"
        return 0
    else
        log ERROR "Disaster recovery completed with failures in: ${failed_components[*]}"
        return 1
    fi
}

# Script usage
usage() {
    cat << EOF
ReAgent Sydney - Disaster Recovery Script

Usage: $0 [OPTIONS] [RESTORE_DATE]

OPTIONS:
    full                    Restore complete system (default)
    postgresql              Restore only PostgreSQL database
    redis                   Restore only Redis data
    weaviate                Restore only Weaviate vector database
    grafana                 Restore only Grafana configuration
    prometheus              Restore only Prometheus data
    configs                 Restore only system configurations
    
RESTORE_DATE:
    latest                  Use latest available backup (default)
    YYYYMMDD_HHMMSS        Use specific backup date/time

Examples:
    $0 full                 # Restore everything from latest backup
    $0 full 20231215_143000 # Restore everything from specific backup
    $0 postgresql latest    # Restore only database from latest backup

EOF
}

# Main entry point
main() {
    case "${1:-full}" in
        full)
            run_full_restore
            ;;
        postgresql|postgres)
            pre_restore_checks
            restore_postgresql
            start_all_services
            post_restore_validation
            ;;
        redis)
            pre_restore_checks
            restore_redis
            start_all_services
            ;;
        weaviate)
            pre_restore_checks
            restore_weaviate
            start_all_services
            ;;
        grafana)
            restore_grafana
            ;;
        prometheus)
            restore_prometheus
            ;;
        configs)
            restore_configurations
            ;;
        -h|--help|help)
            usage
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            usage
            exit 1
            ;;
    esac
}

# Run main function
main "$@"