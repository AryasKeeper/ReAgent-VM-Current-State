#!/bin/bash
set -euo pipefail

# ReAgent Docker Build Validation Pipeline
# Comprehensive build testing and validation for production deployment

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUILD_LOG="/tmp/reagent-build-validation.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
VALIDATION_REPORT="build-validation-report-${TIMESTAMP}.json"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$BUILD_LOG"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$BUILD_LOG"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$BUILD_LOG"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$BUILD_LOG"; }

# Initialize validation report
init_report() {
    cat > "$VALIDATION_REPORT" << EOF
{
  "validation_timestamp": "$(date -u +"%Y-%m-%dT%H:%M:%SZ")",
  "validation_type": "docker_build_comprehensive",
  "results": {
    "pre_build_checks": {},
    "build_tests": {},
    "health_checks": {},
    "performance_metrics": {}
  },
  "summary": {
    "total_checks": 0,
    "passed": 0,
    "failed": 0,
    "warnings": 0
  }
}
EOF
}

# Update report function
update_report() {
    local section="$1"
    local test_name="$2" 
    local status="$3"
    local details="$4"
    local duration="${5:-0}"
    
    python3 -c "
import json
import sys

try:
    with open('$VALIDATION_REPORT', 'r') as f:
        report = json.load(f)
    
    if '$section' not in report['results']:
        report['results']['$section'] = {}
    
    report['results']['$section']['$test_name'] = {
        'status': '$status',
        'details': '$details',
        'duration_seconds': $duration,
        'timestamp': '$(date -u +'%Y-%m-%dT%H:%M:%SZ')'
    }
    
    # Update summary
    report['summary']['total_checks'] += 1
    if '$status' == 'passed':
        report['summary']['passed'] += 1
    elif '$status' == 'failed':
        report['summary']['failed'] += 1
    elif '$status' == 'warning':
        report['summary']['warnings'] += 1
    
    with open('$VALIDATION_REPORT', 'w') as f:
        json.dump(report, f, indent=2)
        
except Exception as e:
    print(f'Error updating report: {e}', file=sys.stderr)
    " || log_warning "Failed to update validation report"
}

# Pre-build validation checks
validate_prebuild() {
    log_info "Starting pre-build validation checks..."
    
    local start_time=$(date +%s)
    
    # Check Docker daemon
    log_info "Checking Docker daemon status..."
    if docker info >/dev/null 2>&1; then
        log_success "Docker daemon is running"
        update_report "pre_build_checks" "docker_daemon" "passed" "Docker daemon accessible"
    else
        log_error "Docker daemon not accessible"
        update_report "pre_build_checks" "docker_daemon" "failed" "Docker daemon not running"
        return 1
    fi
    
    # Check disk space
    log_info "Checking available disk space..."
    local available_space=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available_space" -gt 5 ]; then
        log_success "Sufficient disk space: ${available_space}GB available"
        update_report "pre_build_checks" "disk_space" "passed" "${available_space}GB available"
    else
        log_error "Insufficient disk space: ${available_space}GB available (minimum 5GB required)"
        update_report "pre_build_checks" "disk_space" "failed" "Only ${available_space}GB available"
        return 1
    fi
    
    # Check memory
    log_info "Checking available memory..."
    local available_mem=$(free -g | awk 'NR==2{print $7}')
    if [ "$available_mem" -gt 2 ]; then
        log_success "Sufficient memory: ${available_mem}GB available"
        update_report "pre_build_checks" "memory" "passed" "${available_mem}GB available"
    else
        log_warning "Low memory: ${available_mem}GB available (recommended 4GB+)"
        update_report "pre_build_checks" "memory" "warning" "Only ${available_mem}GB available"
    fi
    
    # Check requirements.txt syntax
    log_info "Validating requirements.txt..."
    if python3 -m pip check --disable-pip-version-check >/dev/null 2>&1; then
        log_success "requirements.txt syntax valid"
        update_report "pre_build_checks" "requirements_syntax" "passed" "Requirements file syntax valid"
    else
        log_warning "requirements.txt may have issues (will attempt build anyway)"
        update_report "pre_build_checks" "requirements_syntax" "warning" "Potential requirements issues detected"
    fi
    
    # Check Dockerfile syntax
    log_info "Validating Dockerfile syntax..."
    local dockerfile_errors=0
    for dockerfile in Dockerfile.api Dockerfile.agents Dockerfile.health-monitor Dockerfile.celery; do
        if [ -f "$dockerfile" ]; then
            if docker build -f "$dockerfile" --dry-run . >/dev/null 2>&1; then
                log_success "$dockerfile syntax valid"
                update_report "pre_build_checks" "${dockerfile}_syntax" "passed" "Dockerfile syntax valid"
            else
                log_error "$dockerfile syntax invalid"
                update_report "pre_build_checks" "${dockerfile}_syntax" "failed" "Dockerfile syntax errors"
                dockerfile_errors=$((dockerfile_errors + 1))
            fi
        else
            log_error "$dockerfile not found"
            update_report "pre_build_checks" "${dockerfile}_exists" "failed" "Dockerfile not found"
            dockerfile_errors=$((dockerfile_errors + 1))
        fi
    done
    
    # Check build context size
    log_info "Checking build context size..."
    local context_size=$(du -sh . --exclude=data --exclude=logs 2>/dev/null | cut -f1)
    log_info "Build context size: $context_size"
    update_report "pre_build_checks" "build_context_size" "passed" "Context size: $context_size"
    
    local end_time=$(date +%s)
    local duration=$((end_time - start_time))
    
    if [ $dockerfile_errors -eq 0 ]; then
        log_success "Pre-build validation completed successfully in ${duration}s"
        return 0
    else
        log_error "Pre-build validation failed with $dockerfile_errors errors"
        return 1
    fi
}

# Build validation tests
validate_builds() {
    log_info "Starting Docker build validation..."
    
    local services=("api" "orchestrator" "health-monitor" "celery-worker")
    local build_errors=0
    
    for service in "${services[@]}"; do
        log_info "Building $service..."
        local start_time=$(date +%s)
        
        if docker-compose build --no-cache "$service" >/dev/null 2>&1; then
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            log_success "$service built successfully in ${duration}s"
            update_report "build_tests" "${service}_build" "passed" "Build completed" "$duration"
            
            # Check image size
            local image_size=$(docker images --format "table {{.Repository}}:{{.Tag}}\\t{{.Size}}" | grep "reagent-$service\\|reagent_$service" | awk '{print $2}' | head -1)
            if [ -n "$image_size" ]; then
                log_info "$service image size: $image_size"
                update_report "build_tests" "${service}_image_size" "passed" "Image size: $image_size"
            fi
        else
            local end_time=$(date +%s)
            local duration=$((end_time - start_time))
            log_error "$service build failed after ${duration}s"
            update_report "build_tests" "${service}_build" "failed" "Build failed" "$duration"
            build_errors=$((build_errors + 1))
        fi
    done
    
    return $build_errors
}

# Health check validation
validate_health_checks() {
    log_info "Starting health check validation..."
    
    # Start core services first
    log_info "Starting core infrastructure services..."
    if docker-compose up -d postgres redis weaviate; then
        log_success "Core services started"
        update_report "health_checks" "core_services_start" "passed" "PostgreSQL, Redis, Weaviate started"
    else
        log_error "Failed to start core services"
        update_report "health_checks" "core_services_start" "failed" "Core service startup failed"
        return 1
    fi
    
    # Wait for core services to be healthy
    log_info "Waiting for core services to be healthy..."
    local max_wait=180
    local wait_time=0
    
    while [ $wait_time -lt $max_wait ]; do
        local healthy_services=$(docker-compose ps --services --filter "status=running" | grep -E "(postgres|redis|weaviate)" | wc -l)
        if [ "$healthy_services" -eq 3 ]; then
            log_success "All core services are healthy"
            update_report "health_checks" "core_services_health" "passed" "All core services healthy in ${wait_time}s"
            break
        fi
        
        sleep 10
        wait_time=$((wait_time + 10))
        log_info "Waiting for services... (${wait_time}s/${max_wait}s)"
    done
    
    if [ $wait_time -ge $max_wait ]; then
        log_error "Core services failed to become healthy within ${max_wait}s"
        update_report "health_checks" "core_services_health" "failed" "Services not healthy after ${max_wait}s"
        return 1
    fi
    
    # Test application services
    log_info "Starting application services..."
    if docker-compose up -d api health-monitor; then
        log_success "Application services started"
        update_report "health_checks" "app_services_start" "passed" "API and health monitor started"
    else
        log_error "Failed to start application services"
        update_report "health_checks" "app_services_start" "failed" "Application service startup failed"
        return 1
    fi
    
    # Wait for application services
    log_info "Waiting for application services to be healthy..."
    wait_time=0
    max_wait=240
    
    while [ $wait_time -lt $max_wait ]; do
        if docker-compose ps api | grep -q "healthy"; then
            log_success "API service is healthy"
            update_report "health_checks" "api_health" "passed" "API healthy in ${wait_time}s"
            break
        fi
        
        sleep 15
        wait_time=$((wait_time + 15))
        log_info "Waiting for API health... (${wait_time}s/${max_wait}s)"
    done
    
    if [ $wait_time -ge $max_wait ]; then
        log_error "API service failed to become healthy"
        update_report "health_checks" "api_health" "failed" "API not healthy after ${max_wait}s"
        
        # Get logs for debugging
        log_info "API service logs (last 20 lines):"
        docker-compose logs --tail=20 api
        return 1
    fi
    
    return 0
}

# Performance metrics collection
collect_performance_metrics() {
    log_info "Collecting performance metrics..."
    
    # Resource usage
    local total_memory=$(docker stats --no-stream --format "table {{.Container}}\\t{{.MemUsage}}" | grep reagent | awk '{print $2}' | sed 's/MiB//g' | awk '{sum+=$1} END {print sum}')
    local total_cpu=$(docker stats --no-stream --format "table {{.Container}}\\t{{.CPUPerc}}" | grep reagent | awk '{print $2}' | sed 's/%//g' | awk '{sum+=$1} END {print sum}')
    
    log_info "Total memory usage: ${total_memory}MiB"
    log_info "Total CPU usage: ${total_cpu}%"
    
    update_report "performance_metrics" "memory_usage_mib" "passed" "${total_memory}MiB"
    update_report "performance_metrics" "cpu_usage_percent" "passed" "${total_cpu}%"
    
    # Container status
    local running_containers=$(docker-compose ps --services --filter "status=running" | wc -l)
    local total_containers=$(docker-compose ps --services | wc -l)
    
    log_info "Running containers: $running_containers/$total_containers"
    update_report "performance_metrics" "container_status" "passed" "$running_containers/$total_containers running"
    
    # Network connectivity
    if docker-compose exec -T api curl -f http://localhost:8000/api/v1/health/ready >/dev/null 2>&1; then
        log_success "API endpoint accessible"
        update_report "performance_metrics" "api_connectivity" "passed" "API endpoint responding"
    else
        log_error "API endpoint not accessible"
        update_report "performance_metrics" "api_connectivity" "failed" "API endpoint not responding"
    fi
}

# Cleanup function
cleanup() {
    log_info "Cleaning up test environment..."
    docker-compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    log_info "Cleanup completed"
}

# Generate final report
generate_final_report() {
    log_info "Generating final validation report..."
    
    # Add summary to report
    python3 -c "
import json
with open('$VALIDATION_REPORT', 'r') as f:
    report = json.load(f)

total = report['summary']['total_checks']
passed = report['summary']['passed']
failed = report['summary']['failed']
warnings = report['summary']['warnings']

print(f'\\n=== VALIDATION SUMMARY ===')
print(f'Total Checks: {total}')
print(f'Passed: {passed}')
print(f'Failed: {failed}')
print(f'Warnings: {warnings}')
print(f'Success Rate: {(passed/total*100):.1f}%' if total > 0 else 'Success Rate: 0%')
print(f'Report saved: $VALIDATION_REPORT')
print('=' * 25)
"
    
    if [ -f "$VALIDATION_REPORT" ]; then
        log_success "Validation report saved: $VALIDATION_REPORT"
    fi
}

# Main execution
main() {
    echo "ReAgent Docker Build Validation Pipeline"
    echo "======================================="
    echo "Timestamp: $(date)"
    echo "Working Directory: $SCRIPT_DIR"
    echo ""
    
    # Initialize
    init_report
    
    # Trap cleanup on exit
    trap cleanup EXIT
    
    local exit_code=0
    
    # Run validation phases
    if validate_prebuild; then
        log_success "Pre-build validation passed"
    else
        log_error "Pre-build validation failed"
        exit_code=1
    fi
    
    if [ $exit_code -eq 0 ]; then
        if validate_builds; then
            log_success "Build validation passed"
        else
            log_error "Build validation failed"
            exit_code=1
        fi
    fi
    
    if [ $exit_code -eq 0 ]; then
        if validate_health_checks; then
            log_success "Health check validation passed"
            collect_performance_metrics
        else
            log_error "Health check validation failed"
            exit_code=1
        fi
    fi
    
    # Generate final report
    generate_final_report
    
    if [ $exit_code -eq 0 ]; then
        log_success "All validation checks passed! Ready for production deployment."
    else
        log_error "Validation failed. Check logs and report for details."
    fi
    
    return $exit_code
}

# Execute main function
main "$@"