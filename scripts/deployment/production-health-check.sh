#!/bin/bash

# ReAgent Sydney - Production Health Check Script
# Comprehensive service health monitoring for production deployment

set -euo pipefail

# Configuration
SCRIPT_DIR="$(dirname "$0")"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
LOG_FILE="$PROJECT_DIR/logs/health-check.log"
METRICS_FILE="$PROJECT_DIR/logs/health-metrics.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Ensure logs directory exists
mkdir -p "$(dirname "$LOG_FILE")"

# Logging function
log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp="$(date '+%Y-%m-%d %H:%M:%S')"
    echo -e "[$timestamp] [$level] $message" | tee -a "$LOG_FILE"
}

# Health check functions
check_service_health() {
    local service_name="$1"
    local health_endpoint="$2"
    local timeout="${3:-10}"
    
    log "INFO" "Checking health of $service_name..."
    
    if curl -f -s -m "$timeout" "$health_endpoint" >/dev/null 2>&1; then
        log "INFO" "${GREEN}✓ $service_name is healthy${NC}"
        return 0
    else
        log "ERROR" "${RED}✗ $service_name is unhealthy${NC}"
        return 1
    fi
}

check_docker_service() {
    local service_name="$1"
    local container_name="${2:-$service_name}"
    
    log "INFO" "Checking Docker service: $service_name"
    
    # Check if container exists and is running
    if docker ps --format "table {{.Names}}\t{{.Status}}" | grep -q "$container_name.*Up"; then
        log "INFO" "${GREEN}✓ $service_name container is running${NC}"
        
        # Check health status if available
        local health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container_name" 2>/dev/null || echo "none")
        if [ "$health_status" = "healthy" ]; then
            log "INFO" "${GREEN}✓ $service_name is healthy${NC}"
            return 0
        elif [ "$health_status" = "starting" ]; then
            log "WARN" "${YELLOW}⚠ $service_name is starting${NC}"
            return 1
        elif [ "$health_status" = "unhealthy" ]; then
            log "ERROR" "${RED}✗ $service_name is unhealthy${NC}"
            return 1
        else
            log "INFO" "${BLUE}→ $service_name has no health check${NC}"
            return 0
        fi
    else
        log "ERROR" "${RED}✗ $service_name container is not running${NC}"
        return 1
    fi
}

check_database_connectivity() {
    log "INFO" "Testing PostgreSQL connectivity..."
    
    if docker exec reagent-postgres-1 psql -U reagent -d reagent -c "SELECT 1;" >/dev/null 2>&1; then
        log "INFO" "${GREEN}✓ PostgreSQL is accessible${NC}"
        return 0
    else
        log "ERROR" "${RED}✗ PostgreSQL connection failed${NC}"
        return 1
    fi
}

check_redis_connectivity() {
    log "INFO" "Testing Redis connectivity..."
    
    if docker exec reagent-redis-1 redis-cli ping | grep -q "PONG"; then
        log "INFO" "${GREEN}✓ Redis is accessible${NC}"
        return 0
    else
        log "ERROR" "${RED}✗ Redis connection failed${NC}"
        return 1
    fi
}

check_weaviate_connectivity() {
    log "INFO" "Testing Weaviate connectivity..."
    
    if curl -f -s -m 10 "http://localhost:8080/v1/.well-known/ready" >/dev/null 2>&1; then
        log "INFO" "${GREEN}✓ Weaviate is accessible${NC}"
        return 0
    else
        log "ERROR" "${RED}✗ Weaviate connection failed${NC}"
        return 1
    fi
}

generate_health_report() {
    local timestamp="$(date -u '+%Y-%m-%dT%H:%M:%SZ')"
    local report_file="$PROJECT_DIR/health-report-$(date '+%Y%m%d_%H%M%S').json"
    
    log "INFO" "Generating comprehensive health report..."
    
    # Get container stats
    local containers_status=$(docker ps --format "json" | jq -s '.')
    local service_stats=$(docker stats --no-stream --format "json" | jq -s '.')
    
    # Create comprehensive health report
    cat > "$report_file" << EOF
{
  "timestamp": "$timestamp",
  "report_type": "production_health_check",
  "overall_status": "$([ $OVERALL_HEALTH -eq 0 ] && echo "healthy" || echo "unhealthy")",
  "services": {
    "infrastructure": {
      "postgres": "$(check_docker_service postgres reagent-postgres-1 && echo "healthy" || echo "unhealthy")",
      "redis": "$(check_docker_service redis reagent-redis-1 && echo "healthy" || echo "unhealthy")",
      "weaviate": "$(check_docker_service weaviate reagent-weaviate-1 && echo "healthy" || echo "unhealthy")"
    },
    "application": {
      "api": "$(check_docker_service api reagent-api-1 && echo "healthy" || echo "unhealthy")",
      "agents": "$(check_docker_service agents reagent-agents-1 && echo "healthy" || echo "unhealthy")",
      "celery_worker": "$(check_docker_service celery-worker reagent-celery-worker-1 && echo "healthy" || echo "unhealthy")",
      "celery_beat": "$(check_docker_service celery-beat reagent-celery-beat-1 && echo "healthy" || echo "unhealthy")"
    },
    "frontend": {
      "web": "$(check_docker_service frontend reagent-frontend-1 && echo "healthy" || echo "unhealthy")"
    },
    "monitoring": {
      "prometheus": "$(check_docker_service prometheus reagent-prometheus-1 && echo "healthy" || echo "unhealthy")",
      "grafana": "$(check_docker_service grafana reagent-grafana-1 && echo "healthy" || echo "unhealthy")"
    }
  },
  "connectivity_tests": {
    "postgres_accessible": $(check_database_connectivity && echo "true" || echo "false"),
    "redis_accessible": $(check_redis_connectivity && echo "true" || echo "false"),
    "weaviate_accessible": $(check_weaviate_connectivity && echo "true" || echo "false")
  },
  "containers": $containers_status,
  "resource_usage": $service_stats,
  "endpoints": {
    "api_health": "$(check_service_health "API" "http://localhost:8000/api/v1/health/" && echo "healthy" || echo "unhealthy")",
    "grafana_health": "$(check_service_health "Grafana" "http://localhost:3001/api/health" && echo "healthy" || echo "unhealthy")",
    "prometheus_health": "$(check_service_health "Prometheus" "http://localhost:9090/-/healthy" && echo "healthy" || echo "unhealthy")"
  },
  "recommendations": [
    "Monitor service restart patterns",
    "Ensure proper resource allocation",
    "Validate health check endpoints",
    "Check dependency startup sequences"
  ]
}
EOF
    
    log "INFO" "${GREEN}Health report generated: $report_file${NC}"
}

# Main execution
main() {
    local start_time=$(date +%s)
    log "INFO" "${BLUE}=== ReAgent Production Health Check Started ===${NC}"
    
    # Initialize overall health status
    OVERALL_HEALTH=0
    
    # Check Docker service status
    log "INFO" "Checking Docker service status..."
    if ! systemctl is-active --quiet docker; then
        log "ERROR" "${RED}Docker service is not running${NC}"
        OVERALL_HEALTH=1
    fi
    
    # Check core infrastructure services
    log "INFO" "${BLUE}--- Infrastructure Services ---${NC}"
    check_docker_service "PostgreSQL" "reagent-postgres-1" || OVERALL_HEALTH=1
    check_docker_service "Redis" "reagent-redis-1" || OVERALL_HEALTH=1  
    check_docker_service "Weaviate" "reagent-weaviate-1" || OVERALL_HEALTH=1
    
    # Check application services  
    log "INFO" "${BLUE}--- Application Services ---${NC}"
    check_docker_service "API" "reagent-api-1" || OVERALL_HEALTH=1
    check_docker_service "Agents" "reagent-agents-1" || OVERALL_HEALTH=1
    check_docker_service "Celery Worker" "reagent-celery-worker-1" || OVERALL_HEALTH=1
    check_docker_service "Celery Beat" "reagent-celery-beat-1" || OVERALL_HEALTH=1
    
    # Check frontend service
    log "INFO" "${BLUE}--- Frontend Services ---${NC}"
    check_docker_service "Frontend" "reagent-frontend-1" || OVERALL_HEALTH=1
    
    # Check monitoring services
    log "INFO" "${BLUE}--- Monitoring Services ---${NC}"
    check_docker_service "Prometheus" "reagent-prometheus-1" || OVERALL_HEALTH=1
    check_docker_service "Grafana" "reagent-grafana-1" || OVERALL_HEALTH=1
    
    # Test connectivity
    log "INFO" "${BLUE}--- Connectivity Tests ---${NC}"
    check_database_connectivity || OVERALL_HEALTH=1
    check_redis_connectivity || OVERALL_HEALTH=1
    check_weaviate_connectivity || OVERALL_HEALTH=1
    
    # Test HTTP endpoints  
    log "INFO" "${BLUE}--- HTTP Endpoint Tests ---${NC}"
    check_service_health "API Health" "http://localhost:8000/api/v1/health/" || OVERALL_HEALTH=1
    check_service_health "Grafana" "http://localhost:3001/api/health" || OVERALL_HEALTH=1
    check_service_health "Prometheus" "http://localhost:9090/-/healthy" || OVERALL_HEALTH=1
    
    # Generate comprehensive report
    generate_health_report
    
    # Final status
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $OVERALL_HEALTH -eq 0 ]; then
        log "INFO" "${GREEN}=== All Services Healthy (${duration}s) ===${NC}"
        exit 0
    else
        log "ERROR" "${RED}=== System Health Issues Detected (${duration}s) ===${NC}"
        exit 1
    fi
}

# Script execution
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi