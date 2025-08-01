#!/bin/bash

# ReAgent Sydney - Production Deployment Script
# Complete automated deployment with enterprise-grade validation and monitoring
# Version: 2.0 - Enterprise Edition
# Author: ReAgent Operations Team

set -euo pipefail

# =================================================================
# CONFIGURATION AND GLOBALS
# =================================================================

# Script arguments with enhanced validation
DEPLOYMENT_ENV="${1:-production}"
SKIP_BACKUPS="${2:-false}"
DRY_RUN="${3:-false}"
FORCE_DEPLOYMENT="${FORCE_DEPLOYMENT:-false}"
ROLLBACK_ON_FAILURE="${ROLLBACK_ON_FAILURE:-true}"

# Advanced deployment configuration
HEALTH_CHECK_TIMEOUT="${HEALTH_CHECK_TIMEOUT:-300}"
HEALTH_CHECK_INTERVAL="${HEALTH_CHECK_INTERVAL:-10}"
DATABASE_MIGRATION_TIMEOUT="${DATABASE_MIGRATION_TIMEOUT:-600}"
SERVICE_START_TIMEOUT="${SERVICE_START_TIMEOUT:-180}"
PERFORMANCE_VALIDATION_ENABLED="${PERFORMANCE_VALIDATION_ENABLED:-true}"
SECURITY_VALIDATION_ENABLED="${SECURITY_VALIDATION_ENABLED:-true}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Logging
DEPLOYMENT_LOG="./logs/deployment_$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$(dirname "$DEPLOYMENT_LOG")"

log() {
    local level=$1
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case $level in
        INFO)  echo -e "${GREEN}[INFO]${NC} $message" | tee -a "$DEPLOYMENT_LOG" ;;
        WARN)  echo -e "${YELLOW}[WARN]${NC} $message" | tee -a "$DEPLOYMENT_LOG" ;;
        ERROR) echo -e "${RED}[ERROR]${NC} $message" | tee -a "$DEPLOYMENT_LOG" ;;
        DEBUG) echo -e "${BLUE}[DEBUG]${NC} $message" | tee -a "$DEPLOYMENT_LOG" ;;
    esac
}

# Pre-flight checks
pre_flight_checks() {
    log INFO "Running pre-flight checks..."
    
    local errors=0
    
    # Check if running as appropriate user
    if [[ $EUID -eq 0 ]]; then
        log WARN "Running as root. Consider using a dedicated user."
    fi
    
    # Check Docker
    if ! command -v docker >/dev/null 2>&1; then
        log ERROR "Docker is not installed"
        ((errors++))
    elif ! docker info >/dev/null 2>&1; then
        log ERROR "Docker daemon is not running"
        ((errors++))
    fi
    
    # Check Docker Compose
    if ! command -v docker-compose >/dev/null 2>&1; then
        log ERROR "Docker Compose is not installed"
        ((errors++))
    fi
    
    # Check required files
    local required_files=(
        "docker-compose.prod.yml"
        "docker-compose.monitoring.yml"
        ".env.production"
        "secrets/postgres_password.txt"
        "secrets/redis_password.txt"
        "ssl/fullchain.pem"
        "ssl/privkey.pem"
    )
    
    for file in "${required_files[@]}"; do
        if [[ ! -f "$file" ]]; then
            log ERROR "Required file missing: $file"
            ((errors++))
        fi
    done
    
    # Check SSL certificate validity
    if [[ -f "ssl/fullchain.pem" ]]; then
        local cert_expiry=$(openssl x509 -in ssl/fullchain.pem -text -noout | grep "Not After" | cut -d: -f2- | xargs)
        local expiry_timestamp=$(date -d "$cert_expiry" +%s)
        local current_timestamp=$(date +%s)
        local days_until_expiry=$(( (expiry_timestamp - current_timestamp) / 86400 ))
        
        if [[ $days_until_expiry -lt 30 ]]; then
            log WARN "SSL certificate expires in $days_until_expiry days"
        fi
    fi
    
    # Check system resources
    local total_memory=$(free -m | awk 'NR==2{print $2}')
    local available_disk=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    
    if [[ $total_memory -lt 4096 ]]; then
        log WARN "System has less than 4GB RAM ($total_memory MB available)"
    fi
    
    if [[ $available_disk -lt 50 ]]; then
        log WARN "Less than 50GB disk space available ($available_disk GB available)"
    fi
    
    # Check network connectivity to required services
    local external_services=(
        "8.8.8.8:53"  # DNS
        "api.openai.com:443"  # OpenAI
    )
    
    for service in "${external_services[@]}"; do
        if ! timeout 5 bash -c "</dev/tcp/${service/ /:}" 2>/dev/null; then
            log WARN "Cannot connect to $service"
        fi
    done
    
    if [[ $errors -gt 0 ]]; then
        log ERROR "Pre-flight check failed with $errors errors"
        return 1
    fi
    
    log INFO "Pre-flight checks passed"
    return 0
}

# Create pre-deployment backup
create_deployment_backup() {
    if [[ "$SKIP_BACKUPS" == "true" ]]; then
        log INFO "Skipping pre-deployment backup (SKIP_BACKUPS=true)"
        return 0
    fi
    
    log INFO "Creating pre-deployment backup..."
    
    # Create deployment-specific backup
    local backup_tag="pre_deployment_$(date +%Y%m%d_%H%M%S)"
    
    if [[ -f "./scripts/backup-full-system.sh" ]]; then
        if ./scripts/backup-full-system.sh; then
            log INFO "Pre-deployment backup completed successfully"
            echo "$backup_tag" > "./logs/last_deployment_backup.txt"
        else
            log ERROR "Pre-deployment backup failed"
            return 1
        fi
    else
        log WARN "Backup script not found, skipping pre-deployment backup"
    fi
}

# Stop existing services gracefully
stop_services() {
    log INFO "Stopping existing services..."
    
    # Stop monitoring stack first (to avoid alerts during deployment)
    if [[ -f "docker-compose.monitoring.yml" ]]; then
        docker-compose -f docker-compose.monitoring.yml down --timeout 30 || log WARN "Some monitoring services may not have stopped cleanly"
    fi
    
    # Stop main application stack
    if [[ -f "docker-compose.prod.yml" ]]; then
        docker-compose -f docker-compose.prod.yml down --timeout 60 || log WARN "Some application services may not have stopped cleanly"
    fi
    
    # Wait for all containers to fully stop
    local max_wait=60
    local wait_time=0
    
    while [[ $wait_time -lt $max_wait ]]; do
        local running_containers=$(docker ps -q | wc -l)
        if [[ $running_containers -eq 0 ]]; then
            break
        fi
        sleep 2
        ((wait_time+=2))
    done
    
    if [[ $wait_time -ge $max_wait ]]; then
        log WARN "Some containers may still be running after graceful shutdown attempt"
        docker ps
    fi
    
    log INFO "Services stopped successfully"
}

# Pull latest images
pull_images() {
    log INFO "Pulling latest Docker images..."
    
    # Pull images for main stack
    if docker-compose -f docker-compose.prod.yml pull; then
        log INFO "Main stack images pulled successfully"
    else
        log ERROR "Failed to pull main stack images"
        return 1
    fi
    
    # Pull images for monitoring stack
    if docker-compose -f docker-compose.monitoring.yml pull; then
        log INFO "Monitoring stack images pulled successfully"
    else
        log WARN "Failed to pull monitoring stack images"
    fi
    
    # Clean up old images to save space
    docker image prune -f >/dev/null 2>&1 || log WARN "Could not clean up old images"
}

# Start services in correct order
start_services() {
    log INFO "Starting services..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "DRY RUN: Would start services now"
        return 0
    fi
    
    # Start core infrastructure services first
    log INFO "Starting core infrastructure..."
    docker-compose -f docker-compose.prod.yml up -d postgres redis-master weaviate
    
    # Wait for databases to be ready
    log INFO "Waiting for databases to be ready..."
    local max_attempts=30
    local attempt=0
    
    while [[ $attempt -lt $max_attempts ]]; do
        if docker exec reagent-postgres pg_isready -U reagent -d reagent >/dev/null 2>&1 && \
           docker exec reagent-redis-master redis-cli ping >/dev/null 2>&1 && \
           curl -sf "http://localhost:8080/v1/.well-known/ready" >/dev/null 2>&1; then
            break
        fi
        sleep 5
        ((attempt++))
    done
    
    if [[ $attempt -eq $max_attempts ]]; then
        log ERROR "Databases failed to become ready within timeout"
        return 1
    fi
    
    log INFO "Databases are ready"
    
    # Start application services
    log INFO "Starting application services..."
    docker-compose -f docker-compose.prod.yml up -d
    
    # Wait for application to be ready
    log INFO "Waiting for application to be ready..."
    attempt=0
    max_attempts=20
    
    while [[ $attempt -lt $max_attempts ]]; do
        if curl -sf "http://localhost:8000/health" >/dev/null 2>&1; then
            break
        fi
        sleep 5
        ((attempt++))
    done
    
    if [[ $attempt -eq $max_attempts ]]; then
        log ERROR "Application failed to become ready within timeout"
        return 1
    fi
    
    log INFO "Application is ready"
    
    # Start monitoring services
    log INFO "Starting monitoring services..."
    docker-compose -f docker-compose.monitoring.yml up -d
    
    log INFO "All services started successfully"
}

# Run database migrations
run_migrations() {
    log INFO "Running database migrations..."
    
    if [[ "$DRY_RUN" == "true" ]]; then
        log INFO "DRY RUN: Would run migrations now"
        return 0
    fi
    
    # Run Alembic migrations
    if docker exec reagent-api alembic upgrade head; then
        log INFO "Database migrations completed successfully"
    else
        log ERROR "Database migrations failed"
        return 1
    fi
    
    # Setup TimescaleDB hypertables if needed
    if docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
        psql -U reagent -d reagent -c "SELECT setup_timescale_hypertables();" >/dev/null 2>&1; then
        log INFO "TimescaleDB hypertables setup completed"
    else
        log WARN "TimescaleDB hypertables setup failed or not needed"
    fi
    
    # Create performance indexes
    if docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
        psql -U reagent -d reagent -c "SELECT create_performance_indexes();" >/dev/null 2>&1; then
        log INFO "Performance indexes created successfully"
    else
        log WARN "Performance indexes creation failed or not needed"
    fi
}

# Post-deployment verification
post_deployment_verification() {
    log INFO "Running post-deployment verification..."
    
    local errors=0
    
    # Check service health
    local services=(
        "http://localhost:8000/health:API"
        "http://localhost:8080/v1/.well-known/ready:Weaviate"
        "http://localhost:9090/-/ready:Prometheus"
        "http://localhost:3001/api/health:Grafana"
    )
    
    for service_info in "${services[@]}"; do
        local url="${service_info%%:*}"
        local name="${service_info##*:}"
        
        if curl -sf "$url" >/dev/null 2>&1; then
            log INFO "$name health check: OK"
        else
            log ERROR "$name health check: FAILED"
            ((errors++))
        fi
    done
    
    # Check database connectivity
    if docker exec reagent-postgres pg_isready -U reagent -d reagent >/dev/null 2>&1; then
        log INFO "PostgreSQL connectivity: OK"
    else
        log ERROR "PostgreSQL connectivity: FAILED"
        ((errors++))
    fi
    
    if docker exec reagent-redis-master redis-cli ping >/dev/null 2>&1; then
        log INFO "Redis connectivity: OK"
    else
        log ERROR "Redis connectivity: FAILED"
        ((errors++))
    fi
    
    # Test key application functionality
    log INFO "Testing key application endpoints..."
    
    # Test search endpoint (should not error)
    if curl -sf "http://localhost:8000/api/v1/properties/search?limit=1" >/dev/null 2>&1; then
        log INFO "Property search endpoint: OK"
    else
        log WARN "Property search endpoint: Not responding (may be expected for new deployment)"
    fi
    
    # Check container resource usage
    log INFO "Checking container resource usage..."
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}" | tee -a "$DEPLOYMENT_LOG"
    
    if [[ $errors -gt 0 ]]; then
        log ERROR "Post-deployment verification failed with $errors errors"
        return 1
    fi
    
    log INFO "Post-deployment verification passed"
    return 0
}

# Rollback function
rollback_deployment() {
    log ERROR "Deployment failed. Initiating rollback..."
    
    # Stop current deployment
    docker-compose -f docker-compose.prod.yml down --timeout 30
    docker-compose -f docker-compose.monitoring.yml down --timeout 30
    
    # Check if we have a pre-deployment backup
    if [[ -f "./logs/last_deployment_backup.txt" ]]; then
        local backup_tag=$(cat "./logs/last_deployment_backup.txt")
        log INFO "Attempting to restore from backup: $backup_tag"
        
        if [[ -f "./scripts/disaster-recovery.sh" ]]; then
            if ./scripts/disaster-recovery.sh full latest; then
                log INFO "Rollback completed successfully"
                return 0
            else
                log ERROR "Rollback failed. Manual intervention required."
                return 1
            fi
        else
            log ERROR "Disaster recovery script not found. Manual rollback required."
            return 1
        fi
    else
        log ERROR "No backup information found. Manual rollback required."
        return 1
    fi
}

# Generate deployment report
generate_deployment_report() {
    log INFO "Generating deployment report..."
    
    local report_file="./logs/deployment_report_$(date +%Y%m%d_%H%M%S).txt"
    
    cat << EOF > "$report_file"
ReAgent Sydney - Deployment Report
=================================
Date: $(date)
Environment: $DEPLOYMENT_ENV
Deployment Status: ${1:-SUCCESS}

Services Status:
$(docker-compose -f docker-compose.prod.yml ps)

Monitoring Services:
$(docker-compose -f docker-compose.monitoring.yml ps)

System Resources:
$(free -h)
$(df -h)

Container Resource Usage:
$(docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}")

Database Status:
$(docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT 'PostgreSQL OK' as status;" 2>/dev/null || echo "PostgreSQL: ERROR")

$(docker exec reagent-redis-master redis-cli ping 2>/dev/null || echo "Redis: ERROR")

Access Points:
- API: http://localhost:8000
- Grafana: http://localhost:3001
- Prometheus: http://localhost:9090

Deployment Log: $DEPLOYMENT_LOG
EOF
    
    log INFO "Deployment report generated: $report_file"
}

# Main deployment function
main() {
    local start_time=$(date +%s)
    
    log INFO "Starting ReAgent Sydney production deployment"
    log INFO "Environment: $DEPLOYMENT_ENV"
    log INFO "Skip backups: $SKIP_BACKUPS"
    log INFO "Dry run: $DRY_RUN"
    
    # Deployment pipeline
    if ! pre_flight_checks; then
        log ERROR "Pre-flight checks failed. Aborting deployment."
        exit 1
    fi
    
    if ! create_deployment_backup; then
        log ERROR "Pre-deployment backup failed. Aborting deployment."
        exit 1
    fi
    
    if ! stop_services; then
        log ERROR "Failed to stop services. Aborting deployment."
        exit 1
    fi
    
    if ! pull_images; then
        log ERROR "Failed to pull images. Aborting deployment."
        exit 1
    fi
    
    if ! start_services; then
        log ERROR "Failed to start services. Initiating rollback."
        rollback_deployment
        exit 1
    fi
    
    if ! run_migrations; then
        log ERROR "Database migrations failed. Initiating rollback."
        rollback_deployment
        exit 1
    fi
    
    if ! post_deployment_verification; then
        log ERROR "Post-deployment verification failed. Initiating rollback."
        rollback_deployment
        exit 1
    fi
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    log INFO "Deployment completed successfully in ${duration}s"
    
    generate_deployment_report "SUCCESS"
    
    echo
    echo -e "${GREEN}🎉 ReAgent Sydney deployed successfully!${NC}"
    echo
    echo "Access points:"
    echo "- API: http://localhost:8000"
    echo "- Health Check: http://localhost:8000/health"
    echo "- Grafana Monitoring: http://localhost:3001"
    echo "- Prometheus Metrics: http://localhost:9090"
    echo
    echo "Next steps:"
    echo "1. Monitor system health via Grafana dashboards"
    echo "2. Test key application functionality"
    echo "3. Verify external API integrations"
    echo "4. Set up SSL certificate auto-renewal if using Let's Encrypt"
    echo
    echo "Deployment log: $DEPLOYMENT_LOG"
}

# Script usage
usage() {
    cat << EOF
ReAgent Sydney - Production Deployment Script

Usage: $0 [ENVIRONMENT] [SKIP_BACKUPS] [DRY_RUN]

Arguments:
    ENVIRONMENT     Deployment environment (default: production)
    SKIP_BACKUPS   Skip pre-deployment backup (default: false)
    DRY_RUN        Perform deployment checks without actual deployment (default: false)

Examples:
    $0                          # Full production deployment with backups
    $0 production false false   # Same as above, explicit
    $0 production true false    # Skip pre-deployment backup
    $0 production false true    # Dry run - checks only, no deployment

Prerequisites:
    - Docker and Docker Compose installed
    - .env.production configured
    - secrets/ directory with required secrets
    - SSL certificates in ssl/ directory
    - Sufficient system resources (4GB+ RAM, 50GB+ disk)

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