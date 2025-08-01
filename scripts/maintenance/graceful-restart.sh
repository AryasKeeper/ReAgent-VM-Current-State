#!/bin/bash

# ReAgent Sydney - Graceful Restart Script
# Combines graceful shutdown and startup with rolling restart options

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
RESTART_LOG="./logs/restart_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$RESTART_LOG")"

# Restart options
ROLLING_RESTART="${1:-false}"
SKIP_BACKUP="${2:-false}"
UPDATE_IMAGES="${3:-false}"

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" | tee -a "$RESTART_LOG" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" | tee -a "$RESTART_LOG" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" | tee -a "$RESTART_LOG" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" | tee -a "$RESTART_LOG" ;;
    esac
}

# Pre-restart health check
pre_restart_health_check() {
    log INFO "Running pre-restart health check..."
    
    local critical_issues=0
    
    # Check if system is already stopped
    local running_containers=$(docker ps --filter "name=reagent-" -q | wc -l)
    if [[ $running_containers -eq 0 ]]; then
        log INFO "System is already stopped, proceeding with startup only"
        return 0
    fi
    
    # Check for critical system issues
    local memory_usage=$(free | awk 'NR==2{printf "%.2f", ($2-$7)*100/$2}')
    local disk_usage=$(df -h . | awk 'NR==2{gsub(/%/,""); print $5}')
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_cores=$(nproc)
    
    # Memory check
    if (( $(echo "$memory_usage > 90" | bc -l) )); then
        log WARN "High memory usage: ${memory_usage}%"
        ((critical_issues++))
    fi
    
    # Disk check
    if [[ $disk_usage -gt 90 ]]; then
        log WARN "High disk usage: ${disk_usage}%"
        ((critical_issues++))
    fi
    
    # Load check
    local load_percent=$(echo "$load_avg * 100 / $cpu_cores" | bc -l | cut -d. -f1)
    if [[ $load_percent -gt 90 ]]; then
        log WARN "High CPU load: ${load_avg} (${load_percent}%)"
        ((critical_issues++))
    fi
    
    # Check for stuck processes
    local stuck_containers=$(docker ps --filter "health=unhealthy" -q | wc -l)
    if [[ $stuck_containers -gt 0 ]]; then
        log WARN "$stuck_containers containers are unhealthy"
        docker ps --filter "health=unhealthy" --format "table {{.Names}}\t{{.Status}}"
        ((critical_issues++))
    fi
    
    if [[ $critical_issues -gt 0 ]]; then
        log WARN "Pre-restart check found $critical_issues issues"
        
        if [[ "$ROLLING_RESTART" == "true" ]]; then
            log INFO "Continuing with rolling restart despite issues"
        else
            log WARN "Consider using rolling restart to minimize impact"
        fi
    else
        log INFO "Pre-restart health check passed"
    fi
    
    return 0
}

# Rolling restart function
perform_rolling_restart() {
    log INFO "Performing rolling restart..."
    
    # Update images if requested
    if [[ "$UPDATE_IMAGES" == "true" ]]; then
        log INFO "Updating Docker images..."
        docker-compose -f docker-compose.prod.yml pull
        docker-compose -f docker-compose.monitoring.yml pull
    fi
    
    # Rolling restart order: non-critical services first
    local restart_groups=(
        "reagent-celery-beat:30"
        "reagent-celery-worker:60"
        "reagent-agents:90"
        "reagent-api:60"
        "reagent-nginx:30"
    )
    
    for group in "${restart_groups[@]}"; do
        local service="${group%%:*}"
        local timeout="${group##*:}"
        
        if docker ps --format "{{.Names}}" | grep -q "^${service}"; then
            log INFO "Rolling restart: $service (timeout: ${timeout}s)"
            
            # Create backup connection info
            local service_status=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "unknown")
            
            # Restart with timeout
            if docker restart --time="$timeout" "$service"; then
                log INFO "$service restarted successfully"
                
                # Wait for service to be healthy
                local max_wait=120
                local wait_time=0
                
                while [[ $wait_time -lt $max_wait ]]; do
                    local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "no-health-check")
                    
                    if [[ "$health_status" == "healthy" ]] || [[ "$health_status" == "no-health-check" ]]; then
                        break
                    fi
                    
                    sleep 5
                    ((wait_time+=5))
                done
                
                if [[ $wait_time -ge $max_wait ]]; then
                    log WARN "$service may not be fully healthy after restart"
                else
                    log INFO "$service is healthy after restart"
                fi
                
                # Brief pause between service restarts
                sleep 10
                
            else
                log ERROR "$service restart failed"
                return 1
            fi
        else
            log DEBUG "$service not running, skipping"
        fi
    done
    
    # Restart monitoring services
    log INFO "Restarting monitoring services..."
    docker-compose -f docker-compose.monitoring.yml restart
    
    # Infrastructure services (only if absolutely necessary)
    local infra_services=(
        "reagent-weaviate"
        "reagent-redis-master"
        "reagent-postgres"
    )
    
    for service in "${infra_services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${service}"; then
            local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "unknown")
            
            if [[ "$health_status" == "unhealthy" ]]; then
                log WARN "Infrastructure service $service is unhealthy, restarting..."
                
                if docker restart --time=120 "$service"; then
                    log INFO "$service restarted"
                    sleep 30  # Allow infrastructure to stabilize
                else
                    log ERROR "$service restart failed"
                    return 1
                fi
            else
                log INFO "Infrastructure service $service is healthy, skipping restart"
            fi
        fi
    done
    
    log INFO "Rolling restart completed"
    return 0
}

# Full restart function
perform_full_restart() {
    log INFO "Performing full restart..."
    
    # Graceful shutdown
    if ./scripts/graceful-shutdown.sh false "$SKIP_BACKUP" true; then
        log INFO "Graceful shutdown completed"
    else
        log ERROR "Graceful shutdown failed"
        return 1
    fi
    
    # Brief pause to ensure all resources are released
    sleep 5
    
    # Clean up any remaining resources
    log INFO "Cleaning up remaining resources..."
    docker system prune -f --volumes >/dev/null 2>&1 || log WARN "System cleanup may have failed"
    
    # Update images if requested
    if [[ "$UPDATE_IMAGES" == "true" ]]; then
        log INFO "Updating Docker images..."
        docker-compose -f docker-compose.prod.yml pull
        docker-compose -f docker-compose.monitoring.yml pull
    fi
    
    # Start services
    if ./scripts/deploy-production.sh production true false; then
        log INFO "Production deployment completed"
    else
        log ERROR "Production deployment failed"
        return 1
    fi
    
    log INFO "Full restart completed"
    return 0
}

# Post-restart verification
post_restart_verification() {
    log INFO "Running post-restart verification..."
    
    # Wait for services to stabilize
    log INFO "Waiting for services to stabilize..."
    sleep 30
    
    # Run health check
    if ./scripts/production-health-check.sh >/dev/null 2>&1; then
        log INFO "Post-restart health check passed"
    else
        log WARN "Post-restart health check found issues"
        
        # Run abbreviated health check for critical services
        local critical_checks=0
        
        # API health
        if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
            log INFO "API endpoint is responding"
        else
            log ERROR "API endpoint is not responding"
            ((critical_checks++))
        fi
        
        # Database connectivity
        if docker exec reagent-postgres pg_isready -U reagent -d reagent >/dev/null 2>&1; then
            log INFO "PostgreSQL is responding"
        else
            log ERROR "PostgreSQL is not responding"
            ((critical_checks++))
        fi
        
        # Redis connectivity
        if docker exec reagent-redis-master redis-cli ping >/dev/null 2>&1; then
            log INFO "Redis is responding"
        else
            log ERROR "Redis is not responding"
            ((critical_checks++))
        fi
        
        # Weaviate connectivity
        if curl -sf "http://localhost:8080/v1/.well-known/ready" >/dev/null 2>&1; then
            log INFO "Weaviate is responding"
        else
            log ERROR "Weaviate is not responding"
            ((critical_checks++))
        fi
        
        if [[ $critical_checks -gt 0 ]]; then
            log ERROR "Critical services are not responding after restart"
            return 1
        else
            log INFO "All critical services are responding"
        fi
    fi
    
    # Check container resource usage
    log INFO "Container resource usage after restart:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | tee -a "$RESTART_LOG"
    
    return 0
}

# Generate restart report
generate_restart_report() {
    local restart_status="${1:-SUCCESS}"
    
    log INFO "Generating restart report..."
    
    local report_file="./logs/restart_report_$(date +%Y%m%d_%H%M%S).json"
    
    cat << EOF > "$report_file"
{
    "timestamp": "$(date -Iseconds)",
    "restart_status": "$restart_status",
    "restart_type": "$([ "$ROLLING_RESTART" == "true" ] && echo "ROLLING" || echo "FULL")",
    "images_updated": $UPDATE_IMAGES,
    "backup_created": $([ "$SKIP_BACKUP" == "true" ] && echo "false" || echo "true"),
    "running_containers": $(docker ps --filter "name=reagent-" -q | wc -l),
    "healthy_containers": $(docker ps --filter "name=reagent-" --filter "health=healthy" -q | wc -l),
    "system_info": {
        "uptime": "$(uptime -p)",
        "load_average": "$(uptime | awk -F'load average:' '{print $2}')",
        "memory_usage": "$(free -m | awk 'NR==2{printf "%.2f%%", ($2-$7)*100/$2}')",
        "disk_usage": "$(df -h . | awk 'NR==2{print $5}')"
    },
    "container_status": $(docker ps --filter "name=reagent-" --format json | jq -s '.' 2>/dev/null || echo "[]"),
    "restart_log": "$RESTART_LOG"
}
EOF
    
    log INFO "Restart report generated: $report_file"
}

# Main restart function
main() {
    local start_time=$(date +%s)
    
    log INFO "Starting ReAgent Sydney restart"
    log INFO "Rolling restart: $ROLLING_RESTART"
    log INFO "Skip backup: $SKIP_BACKUP"
    log INFO "Update images: $UPDATE_IMAGES"
    
    # Pre-restart checks
    if ! pre_restart_health_check; then
        log ERROR "Pre-restart health check failed. Aborting restart."
        exit 1
    fi
    
    # Perform restart based on type
    local restart_success=false
    
    if [[ "$ROLLING_RESTART" == "true" ]]; then
        if perform_rolling_restart; then
            restart_success=true
        fi
    else
        if perform_full_restart; then
            restart_success=true
        fi
    fi
    
    if [[ "$restart_success" == "true" ]]; then
        # Post-restart verification
        if post_restart_verification; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            
            log INFO "Restart completed successfully in ${duration}s"
            generate_restart_report "SUCCESS"
            
            echo
            echo -e "${GREEN}✓ ReAgent Sydney restart completed successfully${NC}"
            echo
            echo "Restart summary:"
            echo "- Duration: ${duration} seconds"
            echo "- Type: $([ "$ROLLING_RESTART" == "true" ] && echo "Rolling" || echo "Full")"
            echo "- Images updated: $([ "$UPDATE_IMAGES" == "true" ] && echo "Yes" || echo "No")"
            echo "- Backup: $([ "$SKIP_BACKUP" == "true" ] && echo "Skipped" || echo "Created")"
            echo
            echo "Access points:"
            echo "- API: http://localhost:8000"
            echo "- Health Check: http://localhost:8000/health"
            echo "- Grafana: http://localhost:3001"
            echo
            echo "Restart log: $RESTART_LOG"
            
        else
            log ERROR "Post-restart verification failed"
            generate_restart_report "VERIFICATION_FAILED"
            exit 1
        fi
    else
        log ERROR "Restart process failed"
        generate_restart_report "FAILED"
        
        echo
        echo -e "${RED}✗ ReAgent Sydney restart failed${NC}"
        echo
        echo "Check the restart log for details: $RESTART_LOG"
        echo
        echo "To attempt recovery:"
        echo "  ./scripts/graceful-shutdown.sh true"
        echo "  ./scripts/deploy-production.sh"
        echo
        exit 1
    fi
}

# Script usage
usage() {
    cat << EOF
ReAgent Sydney - Graceful Restart Script

Usage: $0 [ROLLING_RESTART] [SKIP_BACKUP] [UPDATE_IMAGES]

Arguments:
    ROLLING_RESTART   Perform rolling restart instead of full shutdown/startup (default: false)
    SKIP_BACKUP      Skip pre-restart backup creation (default: false)
    UPDATE_IMAGES    Pull latest Docker images before restart (default: false)

Examples:
    $0                        # Full restart with backup, no image updates
    $0 true false false       # Rolling restart with backup, no image updates
    $0 false false true       # Full restart with backup and image updates
    $0 true true true         # Rolling restart without backup, with image updates

Restart Types:
    FULL RESTART:
        - Complete shutdown of all services
        - Clean up resources
        - Update images (if requested)
        - Full startup with health checks

    ROLLING RESTART:
        - Restart services individually
        - Maintain high availability
        - Minimal downtime
        - Infrastructure services only restarted if unhealthy

Restart Process:
    1. Pre-restart health check
    2. Create backup (unless skipped)
    3. Perform restart (rolling or full)
    4. Update images (if requested)
    5. Post-restart verification
    6. Generate restart report

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