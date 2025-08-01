#!/bin/bash

# ReAgent Sydney - Production Health Check Script
# Comprehensive system validation for production deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
HEALTH_LOG="./logs/health_check_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$HEALTH_LOG")"

# Health check results
PASSED_CHECKS=0
FAILED_CHECKS=0
TOTAL_CHECKS=0

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}✓${NC} $message" | tee -a "$HEALTH_LOG" ;;
        WARN)  echo -e "${YELLOW}⚠${NC} $message" | tee -a "$HEALTH_LOG" ;;
        ERROR) echo -e "${RED}✗${NC} $message" | tee -a "$HEALTH_LOG" ;;
        DEBUG) echo -e "${BLUE}ℹ${NC} $message" | tee -a "$HEALTH_LOG" ;;
    esac
}

check_result() {
    local test_name="$1"
    local result="$2"
    ((TOTAL_CHECKS++))
    
    if [[ $result -eq 0 ]]; then
        log INFO "$test_name: PASSED"
        ((PASSED_CHECKS++))
        return 0
    else
        log ERROR "$test_name: FAILED"
        ((FAILED_CHECKS++))
        return 1
    fi
}

# Check Docker services status
check_docker_services() {
    echo "=== Docker Services Health Check ==="
    
    # Check if Docker is running
    if docker info >/dev/null 2>&1; then
        check_result "Docker daemon" 0
    else
        check_result "Docker daemon" 1
        return 1
    fi
    
    # Check production services
    local prod_services=(
        "reagent-postgres"
        "reagent-redis-master" 
        "reagent-weaviate"
        "reagent-api"
        "reagent-agents"
        "reagent-nginx"
    )
    
    for service in "${prod_services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${service}$"; then
            local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$service" 2>/dev/null || echo "no-health-check")
            
            if [[ "$health_status" == "healthy" ]] || [[ "$health_status" == "no-health-check" ]]; then
                check_result "Service $service" 0
            else
                check_result "Service $service (status: $health_status)" 1
            fi
        else
            check_result "Service $service (not running)" 1
        fi
    done
    
    # Check monitoring services
    local monitoring_services=(
        "reagent-prometheus"
        "reagent-grafana"
        "reagent-alertmanager"
    )
    
    for service in "${monitoring_services[@]}"; do
        if docker ps --format "{{.Names}}" | grep -q "^${service}$"; then
            check_result "Monitoring service $service" 0
        else
            check_result "Monitoring service $service (not running)" 1
        fi
    done
}

# Check HTTP endpoints
check_http_endpoints() {
    echo
    echo "=== HTTP Endpoints Health Check ==="
    
    local endpoints=(
        "http://localhost:8000/health:API Health"
        "http://localhost:8000/api/v1/docs:API Documentation"
        "http://localhost:8080/v1/.well-known/ready:Weaviate Ready"
        "http://localhost:8080/v1/.well-known/live:Weaviate Live"
        "http://localhost:9090/-/ready:Prometheus Ready"
        "http://localhost:9090/-/healthy:Prometheus Healthy"
        "http://localhost:3001/api/health:Grafana Health"
        "http://localhost:9093/-/ready:AlertManager Ready"
    )
    
    for endpoint_info in "${endpoints[@]}"; do
        local url="${endpoint_info%%:*}"
        local name="${endpoint_info##*:}"
        
        if timeout 10 curl -sf "$url" >/dev/null 2>&1; then
            check_result "$name" 0
        else
            check_result "$name" 1
        fi
    done
}

# Check database connectivity and performance
check_database_health() {
    echo
    echo "=== Database Health Check ==="
    
    # PostgreSQL connectivity
    if docker exec reagent-postgres pg_isready -U reagent -d reagent >/dev/null 2>&1; then
        check_result "PostgreSQL connectivity" 0
        
        # Check database size and performance
        local db_size=$(docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
            psql -U reagent -d reagent -t -c "SELECT pg_size_pretty(pg_database_size('reagent'));" 2>/dev/null | tr -d ' ')
        
        if [[ -n "$db_size" ]]; then
            log INFO "Database size: $db_size"
            check_result "PostgreSQL database size query" 0
        else
            check_result "PostgreSQL database size query" 1
        fi
        
        # Check active connections
        local active_connections=$(docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
            psql -U reagent -d reagent -t -c "SELECT count(*) FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null | tr -d ' ')
        
        if [[ -n "$active_connections" ]]; then
            log INFO "Active database connections: $active_connections"
            check_result "PostgreSQL active connections query" 0
        else
            check_result "PostgreSQL active connections query" 1
        fi
    else
        check_result "PostgreSQL connectivity" 1
    fi
    
    # Redis connectivity and info
    if docker exec reagent-redis-master redis-cli ping >/dev/null 2>&1; then
        check_result "Redis connectivity" 0
        
        # Check Redis memory usage
        local redis_memory=$(docker exec reagent-redis-master redis-cli info memory | grep used_memory_human | cut -d: -f2 | tr -d '\r')
        if [[ -n "$redis_memory" ]]; then
            log INFO "Redis memory usage: $redis_memory"
            check_result "Redis memory info" 0
        else
            check_result "Redis memory info" 1
        fi
        
        # Check Redis connected clients
        local redis_clients=$(docker exec reagent-redis-master redis-cli info clients | grep connected_clients | cut -d: -f2 | tr -d '\r')
        if [[ -n "$redis_clients" ]]; then
            log INFO "Redis connected clients: $redis_clients"
            check_result "Redis client info" 0
        else
            check_result "Redis client info" 1
        fi
    else
        check_result "Redis connectivity" 1
    fi
}

# Check Weaviate vector database
check_weaviate_health() {
    echo
    echo "=== Weaviate Vector Database Health Check ==="
    
    # Basic connectivity
    if curl -sf "http://localhost:8080/v1/.well-known/ready" >/dev/null 2>&1; then
        check_result "Weaviate ready endpoint" 0
        
        # Check schema existence
        local schema_response=$(curl -s "http://localhost:8080/v1/schema" 2>/dev/null)
        if [[ -n "$schema_response" ]] && echo "$schema_response" | jq -e '.classes' >/dev/null 2>&1; then
            local class_count=$(echo "$schema_response" | jq '.classes | length' 2>/dev/null)
            log INFO "Weaviate schema classes: $class_count"
            check_result "Weaviate schema query" 0
        else
            check_result "Weaviate schema query" 1
        fi
        
        # Check object count (if schema exists)
        local objects_response=$(curl -s "http://localhost:8080/v1/objects" 2>/dev/null)
        if [[ -n "$objects_response" ]]; then
            local object_count=$(echo "$objects_response" | jq '.objects | length' 2>/dev/null || echo "0")
            log INFO "Weaviate objects count: $object_count"
            check_result "Weaviate objects query" 0
        else
            check_result "Weaviate objects query" 1
        fi
    else
        check_result "Weaviate ready endpoint" 1
    fi
}

# Check system resources
check_system_resources() {
    echo
    echo "=== System Resources Health Check ==="
    
    # Memory usage
    local memory_info=$(free -m)
    local total_memory=$(echo "$memory_info" | awk 'NR==2{print $2}')
    local available_memory=$(echo "$memory_info" | awk 'NR==2{print $7}')
    local memory_usage_percent=$(( (total_memory - available_memory) * 100 / total_memory ))
    
    log INFO "Memory usage: ${memory_usage_percent}% (${available_memory}MB available of ${total_memory}MB)"
    
    if [[ $memory_usage_percent -lt 80 ]]; then
        check_result "Memory usage (<80%)" 0
    else
        check_result "Memory usage (${memory_usage_percent}% - HIGH)" 1
    fi
    
    # Disk usage
    local disk_info=$(df -h .)
    local disk_usage_percent=$(echo "$disk_info" | awk 'NR==2{print $5}' | sed 's/%//')
    local disk_available=$(echo "$disk_info" | awk 'NR==2{print $4}')
    
    log INFO "Disk usage: ${disk_usage_percent}% (${disk_available} available)"
    
    if [[ $disk_usage_percent -lt 85 ]]; then
        check_result "Disk usage (<85%)" 0
    else
        check_result "Disk usage (${disk_usage_percent}% - HIGH)" 1
    fi
    
    # CPU load
    local load_avg=$(uptime | awk -F'load average:' '{print $2}' | awk '{print $1}' | sed 's/,//')
    local cpu_cores=$(nproc)
    local load_percent=$(echo "$load_avg * 100 / $cpu_cores" | bc -l | cut -d. -f1)
    
    log INFO "CPU load: ${load_avg} (${load_percent}% of ${cpu_cores} cores)"
    
    if [[ $load_percent -lt 70 ]]; then
        check_result "CPU load (<70%)" 0
    else
        check_result "CPU load (${load_percent}% - HIGH)" 1
    fi
}

# Check external connectivity
check_external_connectivity() {
    echo
    echo "=== External Connectivity Health Check ==="
    
    local external_services=(
        "8.8.8.8:53:DNS"
        "api.openai.com:443:OpenAI API"
        "domain.com.au:443:Domain API"
    )
    
    for service_info in "${external_services[@]}"; do
        local host=$(echo "$service_info" | cut -d: -f1)
        local port=$(echo "$service_info" | cut -d: -f2)
        local name=$(echo "$service_info" | cut -d: -f3)
        
        if timeout 5 bash -c "</dev/tcp/$host/$port" 2>/dev/null; then
            check_result "External connectivity to $name" 0
        else
            check_result "External connectivity to $name" 1
        fi
    done
}

# Check application-specific functionality
check_application_functionality() {
    echo
    echo "=== Application Functionality Health Check ==="
    
    # Test API authentication
    local auth_response=$(curl -s -w "%{http_code}" -o /dev/null "http://localhost:8000/api/v1/auth/health" 2>/dev/null || echo "000")
    if [[ "$auth_response" == "200" ]] || [[ "$auth_response" == "404" ]]; then
        check_result "API authentication endpoint" 0
    else
        check_result "API authentication endpoint (HTTP $auth_response)" 1
    fi
    
    # Test agent endpoints
    local agents=(
        "listing-watcher"
        "buyer-matchmaker"
        "suburb-signal"
        "seller-strategy"
        "off-market-radar"
        "agent-whisperer"
    )
    
    for agent in "${agents[@]}"; do
        local agent_response=$(curl -s -w "%{http_code}" -o /dev/null "http://localhost:8000/api/v1/agents/$agent/health" 2>/dev/null || echo "000")
        if [[ "$agent_response" == "200" ]] || [[ "$agent_response" == "404" ]]; then
            check_result "Agent endpoint: $agent" 0
        else
            check_result "Agent endpoint: $agent (HTTP $agent_response)" 1
        fi
    done
}

# Check SSL/TLS configuration
check_ssl_configuration() {
    echo
    echo "=== SSL/TLS Configuration Health Check ==="
    
    # Check SSL certificate files
    if [[ -f "ssl/fullchain.pem" ]]; then
        # Check certificate validity
        local cert_expiry=$(openssl x509 -in ssl/fullchain.pem -text -noout | grep "Not After" | cut -d: -f2- | xargs)
        local expiry_timestamp=$(date -d "$cert_expiry" +%s)
        local current_timestamp=$(date +%s)
        local days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))
        
        log INFO "SSL certificate expires in $days_until_expiry days"
        
        if [[ $days_until_expiry -gt 7 ]]; then
            check_result "SSL certificate validity (>7 days)" 0
        else
            check_result "SSL certificate validity ($days_until_expiry days - EXPIRING SOON)" 1
        fi
        
        # Check certificate chain
        if openssl verify -CAfile ssl/fullchain.pem ssl/fullchain.pem >/dev/null 2>&1; then
            check_result "SSL certificate chain" 0
        else
            check_result "SSL certificate chain" 1
        fi
    else
        check_result "SSL certificate file exists" 1
    fi
    
    # Check private key
    if [[ -f "ssl/privkey.pem" ]]; then
        check_result "SSL private key file exists" 0
        
        # Check key permissions
        local key_permissions=$(stat -c "%a" ssl/privkey.pem)
        if [[ "$key_permissions" == "600" ]]; then
            check_result "SSL private key permissions" 0
        else
            check_result "SSL private key permissions ($key_permissions - should be 600)" 1
        fi
    else
        check_result "SSL private key file exists" 1
    fi
}

# Check backup system
check_backup_system() {
    echo
    echo "=== Backup System Health Check ==="
    
    # Check backup scripts exist
    local backup_scripts=(
        "scripts/backup-full-system.sh"
        "scripts/backup-postgres.sh"
        "scripts/backup-redis.sh"
        "scripts/disaster-recovery.sh"
    )
    
    for script in "${backup_scripts[@]}"; do
        if [[ -f "$script" ]]; then
            check_result "Backup script exists: $(basename "$script")" 0
        else
            check_result "Backup script exists: $(basename "$script")" 1
        fi
    done
    
    # Check backup directory structure
    local backup_dirs=(
        "backups"
        "backups/postgres"
        "backups/redis"
        "backups/weaviate"
    )
    
    for dir in "${backup_dirs[@]}"; do
        if [[ -d "$dir" ]]; then
            check_result "Backup directory exists: $dir" 0
        else
            check_result "Backup directory exists: $dir" 1
        fi
    done
    
    # Check for recent backups
    if [[ -d "backups" ]]; then
        local recent_backups=$(find backups -name "*.sql" -o -name "*.tar.gz" -o -name "*.backup" -mtime -1 | wc -l)
        if [[ $recent_backups -gt 0 ]]; then
            log INFO "Recent backups found: $recent_backups files"
            check_result "Recent backup files exist" 0
        else
            check_result "Recent backup files exist (none found in last 24h)" 1
        fi
    fi
}

# Generate comprehensive health report
generate_health_report() {
    echo
    echo "=== Health Check Summary ==="
    
    local success_rate=0
    if [[ $TOTAL_CHECKS -gt 0 ]]; then
        success_rate=$(( PASSED_CHECKS * 100 / TOTAL_CHECKS ))
    fi
    
    echo -e "Total checks: $TOTAL_CHECKS"
    echo -e "Passed: ${GREEN}$PASSED_CHECKS${NC}"
    echo -e "Failed: ${RED}$FAILED_CHECKS${NC}"
    echo -e "Success rate: ${success_rate}%"
    
    # Overall health status
    local health_status
    local status_color
    
    if [[ $success_rate -ge 95 ]]; then
        health_status="EXCELLENT"
        status_color="$GREEN"
    elif [[ $success_rate -ge 90 ]]; then
        health_status="GOOD"
        status_color="$GREEN"
    elif [[ $success_rate -ge 80 ]]; then
        health_status="WARNING"
        status_color="$YELLOW"
    else
        health_status="CRITICAL"
        status_color="$RED"
    fi
    
    echo
    echo -e "Overall System Health: ${status_color}$health_status${NC}"
    echo
    
    # Generate detailed report file
    local report_file="./logs/health_report_$(date +%Y%m%d_%H%M%S).json"
    
    cat << EOF > "$report_file"
{
    "timestamp": "$(date -Iseconds)",
    "overall_health": "$health_status",
    "success_rate": $success_rate,
    "total_checks": $TOTAL_CHECKS,
    "passed_checks": $PASSED_CHECKS,
    "failed_checks": $FAILED_CHECKS,
    "system_info": {
        "uptime": "$(uptime -p)",
        "load_average": "$(uptime | awk -F'load average:' '{print $2}')",
        "memory_usage": "$(free -m | awk 'NR==2{printf "%.2f%%", ($2-$7)*100/$2}')",
        "disk_usage": "$(df -h . | awk 'NR==2{print $5}')"
    },
    "docker_containers": $(docker ps --format json | jq -s '.' 2>/dev/null || echo "[]"),
    "health_log": "$HEALTH_LOG"
}
EOF
    
    echo "Detailed health report: $report_file"
    echo "Health check log: $HEALTH_LOG"
    
    # Return appropriate exit code
    if [[ $success_rate -ge 90 ]]; then
        return 0
    else
        return 1
    fi
}

# Main health check execution
main() {
    echo "ReAgent Sydney - Production Health Check"
    echo "========================================"
    echo "Started: $(date)"
    echo
    
    check_docker_services
    check_http_endpoints
    check_database_health
    check_weaviate_health
    check_system_resources
    check_external_connectivity
    check_application_functionality
    check_ssl_configuration
    check_backup_system
    
    generate_health_report
}

# Execute main function
main "$@"