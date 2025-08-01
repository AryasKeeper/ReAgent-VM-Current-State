#!/bin/bash

# ReAgent Sydney - Graceful Shutdown Script
# Safely stops all services with proper cleanup and data preservation

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
SHUTDOWN_LOG="./logs/shutdown_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$SHUTDOWN_LOG")"

# Shutdown options
FORCE_SHUTDOWN="${1:-false}"
SKIP_BACKUP="${2:-false}"
MAINTENANCE_MODE="${3:-false}"

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" | tee -a "$SHUTDOWN_LOG" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" | tee -a "$SHUTDOWN_LOG" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" | tee -a "$SHUTDOWN_LOG" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" | tee -a "$SHUTDOWN_LOG" ;;
    esac
}

# Enable maintenance mode
enable_maintenance_mode() {
    if [[ "$MAINTENANCE_MODE" == "true" ]]; then
        log INFO "Enabling maintenance mode..."
        
        # Create maintenance page
        cat << 'EOF' > ./maintenance.html
<!DOCTYPE html>
<html>
<head>
    <title>ReAgent Sydney - Maintenance</title>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { font-family: Arial, sans-serif; text-align: center; padding: 50px; background: #f5f5f5; }
        .container { max-width: 600px; margin: 0 auto; background: white; padding: 40px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        h1 { color: #e74c3c; }
        p { color: #666; line-height: 1.6; }
        .eta { background: #3498db; color: white; padding: 10px; border-radius: 5px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔧 Maintenance in Progress</h1>
        <p>ReAgent Sydney is currently undergoing scheduled maintenance to improve your experience.</p>
        <div class="eta">Expected completion: Within 30 minutes</div>
        <p>We apologize for any inconvenience and appreciate your patience.</p>
        <p><strong>For urgent inquiries:</strong> contact your system administrator</p>
    </div>
</body>
</html>
EOF
        
        # Update nginx to serve maintenance page
        if docker ps --format "{{.Names}}" | grep -q "^reagent-nginx$"; then
            docker exec reagent-nginx sh -c 'echo "location / { return 503; }" > /etc/nginx/conf.d/maintenance.conf'
            docker exec reagent-nginx nginx -s reload 2>/dev/null || log WARN "Failed to reload nginx for maintenance mode"
        fi
        
        log INFO "Maintenance mode enabled"
    fi
}

# Disable maintenance mode
disable_maintenance_mode() {
    if [[ "$MAINTENANCE_MODE" == "true" ]]; then
        log INFO "Disabling maintenance mode..."
        
        # Remove maintenance configuration
        if docker ps --format "{{.Names}}" | grep -q "^reagent-nginx$"; then
            docker exec reagent-nginx rm -f /etc/nginx/conf.d/maintenance.conf 2>/dev/null || true
            docker exec reagent-nginx nginx -s reload 2>/dev/null || log WARN "Failed to reload nginx to disable maintenance mode"
        fi
        
        # Remove maintenance page
        rm -f ./maintenance.html
        
        log INFO "Maintenance mode disabled"
    fi
}

# Pre-shutdown backup
create_pre_shutdown_backup() {
    if [[ "$SKIP_BACKUP" == "true" ]]; then
        log INFO "Skipping pre-shutdown backup (SKIP_BACKUP=true)"
        return 0
    fi
    
    log INFO "Creating pre-shutdown backup..."
    
    local backup_tag="pre_shutdown_$(date +%Y%m%d_%H%M%S)"
    
    # Quick database backup
    if docker ps --format "{{.Names}}" | grep -q "^reagent-postgres$"; then
        log INFO "Creating PostgreSQL backup..."
        
        if docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
            pg_dump -U reagent -d reagent -f "/backups/pre_shutdown_$(date +%Y%m%d_%H%M%S).sql"; then
            log INFO "PostgreSQL backup completed"
        else
            log ERROR "PostgreSQL backup failed"
            return 1
        fi
    fi
    
    # Redis backup
    if docker ps --format "{{.Names}}" | grep -q "^reagent-redis-master$"; then
        log INFO "Creating Redis backup..."
        
        if docker exec reagent-redis-master redis-cli BGSAVE; then
            # Wait for background save to complete
            local max_wait=30
            local wait_time=0
            
            while [[ $wait_time -lt $max_wait ]]; do
                local lastsave=$(docker exec reagent-redis-master redis-cli LASTSAVE)
                sleep 2
                local newsave=$(docker exec reagent-redis-master redis-cli LASTSAVE)
                
                if [[ "$newsave" != "$lastsave" ]]; then
                    log INFO "Redis backup completed"
                    break
                fi
                
                ((wait_time+=2))
            done
            
            if [[ $wait_time -ge $max_wait ]]; then
                log WARN "Redis backup may not have completed within timeout"
            fi
        else
            log ERROR "Redis backup failed"
            return 1
        fi
    fi
    
    echo "$backup_tag" > "./logs/last_shutdown_backup.txt"
    log INFO "Pre-shutdown backup completed: $backup_tag"
}

# Drain active connections and tasks
drain_active_connections() {
    log INFO "Draining active connections and tasks..."
    
    # Check for active API requests
    if docker ps --format "{{.Names}}" | grep -q "^reagent-api$"; then
        log INFO "Checking for active API requests..."
        
        # Wait for current requests to complete (max 60 seconds)
        local max_wait=60
        local wait_time=0
        
        while [[ $wait_time -lt $max_wait ]]; do
            # Check if there are active connections (this is a simplified check)
            local api_logs=$(docker logs --tail=10 reagent-api 2>/dev/null | grep -c "$(date '+%Y-%m-%d %H:%M')" || echo "0")
            
            if [[ $api_logs -eq 0 ]]; then
                log INFO "No recent API activity detected"
                break
            fi
            
            log DEBUG "Waiting for API requests to complete... (${wait_time}s elapsed)"
            sleep 5
            ((wait_time+=5))
        done
        
        if [[ $wait_time -ge $max_wait ]]; then
            log WARN "API requests may still be active after drainage timeout"
        fi
    fi
    
    # Stop accepting new Celery tasks
    if docker ps --format "{{.Names}}" | grep -q "^reagent-celery-worker"; then
        log INFO "Stopping Celery task acceptance..."
        
        # Send TERM signal to allow current tasks to complete
        docker exec reagent-celery-worker pkill -TERM celery || log WARN "Could not send TERM signal to Celery workers"
        
        # Wait for tasks to complete
        local max_wait=120  # 2 minutes for task completion
        local wait_time=0
        
        while [[ $wait_time -lt $max_wait ]]; do
            local active_tasks=$(docker exec reagent-celery-worker celery -A src.core.celery inspect active 2>/dev/null | grep -c "task" || echo "0")
            
            if [[ $active_tasks -eq 0 ]]; then
                log INFO "All Celery tasks completed"
                break
            fi
            
            log DEBUG "Waiting for Celery tasks to complete... ($active_tasks active, ${wait_time}s elapsed)"
            sleep 10
            ((wait_time+=10))
        done
        
        if [[ $wait_time -ge $max_wait ]]; then
            log WARN "Some Celery tasks may still be active after drainage timeout"
        fi
    fi
    
    log INFO "Connection drainage completed"
}

# Stop services in reverse dependency order
stop_services_gracefully() {
    log INFO "Stopping services gracefully..."
    
    # Stop nginx first to stop accepting new requests
    if docker ps --format "{{.Names}}" | grep -q "^reagent-nginx$"; then
        log INFO "Stopping nginx load balancer..."
        docker stop --time=30 reagent-nginx || log WARN "nginx stop may have timed out"
    fi
    
    # Stop application services
    local app_services=(
        "reagent-agents"
        "reagent-api"
        "reagent-celery-beat"
        "reagent-celery-worker"
    )
    
    for service in "${app_services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${service}$"; then
            log INFO "Stopping $service..."
            
            if [[ "$FORCE_SHUTDOWN" == "true" ]]; then
                docker stop --time=10 "$service" || log WARN "$service force stop may have failed"
            else
                docker stop --time=60 "$service" || log WARN "$service graceful stop may have timed out"
            fi
        fi
    done
    
    # Stop monitoring services
    log INFO "Stopping monitoring services..."
    if [[ -f "docker-compose.monitoring.yml" ]]; then
        local timeout_flag=""
        if [[ "$FORCE_SHUTDOWN" == "true" ]]; then
            timeout_flag="--timeout 10"
        else
            timeout_flag="--timeout 30"
        fi
        
        docker-compose -f docker-compose.monitoring.yml down $timeout_flag || log WARN "Some monitoring services may not have stopped cleanly"
    fi
    
    # Stop infrastructure services last
    local infra_services=(
        "reagent-weaviate"
        "reagent-redis-sentinel"
        "reagent-redis-master"
        "reagent-postgres-replica"
        "reagent-postgres"
    )
    
    for service in "${infra_services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${service}$"; then
            log INFO "Stopping $service..."
            
            if [[ "$FORCE_SHUTDOWN" == "true" ]]; then
                docker stop --time=10 "$service" || log WARN "$service force stop may have failed"
            else
                docker stop --time=90 "$service" || log WARN "$service graceful stop may have timed out"
            fi
        fi
    done
    
    log INFO "All services stopped"
}

# Clean up resources
cleanup_resources() {
    log INFO "Cleaning up resources..."
    
    # Remove stopped containers (if force shutdown)
    if [[ "$FORCE_SHUTDOWN" == "true" ]]; then
        log INFO "Removing stopped containers..."
        docker container prune -f >/dev/null 2>&1 || log WARN "Container cleanup may have failed"
    fi
    
    # Clean up networks if they're empty
    local networks=(
        "reagent-backend"
        "reagent-frontend"
        "reagent-monitoring"
    )
    
    for network in "${networks[@]}"; do
        if docker network ls --format "{{.Name}}" | grep -q "^${network}$"; then
            local connected_containers=$(docker network inspect "$network" --format '{{len .Containers}}' 2>/dev/null || echo "0")
            
            if [[ "$connected_containers" == "0" ]]; then
                log DEBUG "Network $network is empty, considering removal"
                # Don't actually remove networks during shutdown to avoid issues on restart
            fi
        fi
    done
    
    # Sync filesystem to ensure all data is written
    sync
    
    log INFO "Resource cleanup completed"
}

# Verify shutdown completion
verify_shutdown() {
    log INFO "Verifying shutdown completion..."
    
    local running_containers=$(docker ps -q | wc -l)
    
    if [[ $running_containers -eq 0 ]]; then
        log INFO "All containers stopped successfully"
        return 0
    else
        log WARN "$running_containers containers are still running:"
        docker ps --format "table {{.Names}}\t{{.Status}}"
        
        if [[ "$FORCE_SHUTDOWN" == "true" ]]; then
            log INFO "Force stopping remaining containers..."
            docker ps -q | xargs -r docker stop --time=5
            
            local remaining=$(docker ps -q | wc -l)
            if [[ $remaining -eq 0 ]]; then
                log INFO "All containers force stopped"
                return 0
            else
                log ERROR "$remaining containers could not be stopped"
                return 1
            fi
        else
            return 1
        fi
    fi
}

# Generate shutdown report
generate_shutdown_report() {
    local shutdown_status="${1:-SUCCESS}"
    
    log INFO "Generating shutdown report..."
    
    local report_file="./logs/shutdown_report_$(date +%Y%m%d_%H%M%S).json"
    
    cat << EOF > "$report_file"
{
    "timestamp": "$(date -Iseconds)",
    "shutdown_status": "$shutdown_status",
    "shutdown_type": "$([ "$FORCE_SHUTDOWN" == "true" ] && echo "FORCE" || echo "GRACEFUL")",
    "maintenance_mode": $MAINTENANCE_MODE,
    "backup_created": $([ "$SKIP_BACKUP" == "true" ] && echo "false" || echo "true"),
    "running_containers_before": $(docker ps -a --filter "name=reagent-" -q | wc -l),
    "running_containers_after": $(docker ps --filter "name=reagent-" -q | wc -l),
    "system_info": {
        "uptime": "$(uptime -p)",
        "load_average": "$(uptime | awk -F'load average:' '{print $2}')",
        "memory_usage": "$(free -m | awk 'NR==2{printf "%.2f%%", ($2-$7)*100/$2}')",
        "disk_usage": "$(df -h . | awk 'NR==2{print $5}')"
    },
    "shutdown_log": "$SHUTDOWN_LOG"
}
EOF
    
    log INFO "Shutdown report generated: $report_file"
}

# Signal handlers for graceful shutdown
cleanup_on_signal() {
    log WARN "Received shutdown signal, initiating graceful shutdown..."
    FORCE_SHUTDOWN="false"
    main
    exit 0
}

trap cleanup_on_signal SIGINT SIGTERM

# Main shutdown function
main() {
    local start_time=$(date +%s)
    
    log INFO "Starting ReAgent Sydney graceful shutdown"
    log INFO "Force shutdown: $FORCE_SHUTDOWN"
    log INFO "Skip backup: $SKIP_BACKUP"
    log INFO "Maintenance mode: $MAINTENANCE_MODE"
    
    # Shutdown sequence
    enable_maintenance_mode
    
    if ! create_pre_shutdown_backup; then
        log ERROR "Pre-shutdown backup failed. Continue shutdown? (y/N)"
        if [[ "$FORCE_SHUTDOWN" != "true" ]]; then
            read -r -n 1 response
            if [[ ! "$response" =~ ^[Yy]$ ]]; then
                log ERROR "Shutdown aborted due to backup failure"
                disable_maintenance_mode
                exit 1
            fi
        fi
    fi
    
    drain_active_connections
    stop_services_gracefully
    cleanup_resources
    
    if verify_shutdown; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        
        log INFO "Graceful shutdown completed successfully in ${duration}s"
        generate_shutdown_report "SUCCESS"
        
        echo
        echo -e "${GREEN}✓ ReAgent Sydney shutdown completed successfully${NC}"
        echo
        echo "Shutdown summary:"
        echo "- Duration: ${duration} seconds"
        echo "- Type: $([ "$FORCE_SHUTDOWN" == "true" ] && echo "Force" || echo "Graceful")"
        echo "- Backup: $([ "$SKIP_BACKUP" == "true" ] && echo "Skipped" || echo "Created")"
        echo "- Maintenance mode: $([ "$MAINTENANCE_MODE" == "true" ] && echo "Enabled" || echo "Disabled")"
        echo
        echo "To restart the system:"
        echo "  ./scripts/deploy-production.sh"
        echo
        echo "Shutdown log: $SHUTDOWN_LOG"
        
        # Don't disable maintenance mode on successful shutdown if it was requested
        # This allows for maintenance work to be done
        
    else
        log ERROR "Shutdown verification failed"
        generate_shutdown_report "FAILED"
        
        echo
        echo -e "${RED}✗ ReAgent Sydney shutdown encountered issues${NC}"
        echo
        echo "Some containers may still be running. Check with:"
        echo "  docker ps"
        echo
        echo "For emergency shutdown:"
        echo "  ./scripts/graceful-shutdown.sh true"
        echo
        echo "Shutdown log: $SHUTDOWN_LOG"
        
        disable_maintenance_mode
        exit 1
    fi
}

# Script usage
usage() {
    cat << EOF
ReAgent Sydney - Graceful Shutdown Script

Usage: $0 [FORCE_SHUTDOWN] [SKIP_BACKUP] [MAINTENANCE_MODE]

Arguments:
    FORCE_SHUTDOWN     Force immediate shutdown without waiting (default: false)
    SKIP_BACKUP       Skip pre-shutdown backup creation (default: false)
    MAINTENANCE_MODE  Enable maintenance mode during shutdown (default: false)

Examples:
    $0                    # Graceful shutdown with backup
    $0 false false true   # Graceful shutdown with backup and maintenance mode
    $0 true true false    # Force shutdown without backup
    $0 true               # Force shutdown with backup

Shutdown Process:
    1. Enable maintenance mode (if requested)
    2. Create pre-shutdown backup (unless skipped)
    3. Drain active connections and tasks
    4. Stop services in reverse dependency order
    5. Clean up resources
    6. Verify shutdown completion

EOF
}

# Handle command line arguments
case "${1:-}" in
    -h|--help|help)
        usage
        exit 0
        ;;
    *)
        main "$@"
        ;;
esac