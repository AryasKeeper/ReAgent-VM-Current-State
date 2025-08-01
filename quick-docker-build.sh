#!/bin/bash
set -euo pipefail

# ReAgent Quick Docker Build Script
# Optimized for immediate deployment readiness

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG_FILE="/tmp/reagent-quick-build.log"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() { echo -e "${BLUE}[INFO]${NC} $1" | tee -a "$LOG_FILE"; }
log_success() { echo -e "${GREEN}[SUCCESS]${NC} $1" | tee -a "$LOG_FILE"; }
log_warning() { echo -e "${YELLOW}[WARNING]${NC} $1" | tee -a "$LOG_FILE"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1" | tee -a "$LOG_FILE"; }

show_usage() {
    echo "ReAgent Quick Docker Build Script"
    echo "Usage: $0 [OPTIONS]"
    echo ""
    echo "Options:"
    echo "  --no-cache          Build without using cache"
    echo "  --parallel          Build services in parallel"
    echo "  --validate-only     Only validate, don't build"
    echo "  --service <name>    Build specific service only"
    echo "  --help             Show this help message"
    echo ""
    echo "Services: api, orchestrator, health-monitor, celery-worker"
}

# Parse command line arguments
NO_CACHE=false
PARALLEL=false
VALIDATE_ONLY=false
SPECIFIC_SERVICE=""

while [[ $# -gt 0 ]]; do
    case $1 in
        --no-cache)
            NO_CACHE=true
            shift
            ;;
        --parallel)
            PARALLEL=true
            shift
            ;;
        --validate-only)
            VALIDATE_ONLY=true
            shift
            ;;
        --service)
            SPECIFIC_SERVICE="$2"
            shift 2
            ;;
        --help)
            show_usage
            exit 0
            ;;
        *)
            log_error "Unknown option: $1"
            show_usage
            exit 1
            ;;
    esac
done

# Pre-build checks
pre_build_checks() {
    log_info "Running pre-build checks..."
    
    # Check Docker daemon
    if ! docker info >/dev/null 2>&1; then
        log_error "Docker daemon not accessible"
        return 1
    fi
    
    # Check disk space (minimum 5GB)
    local available_space=$(df -BG . | awk 'NR==2 {print $4}' | sed 's/G//')
    if [ "$available_space" -lt 5 ]; then
        log_error "Insufficient disk space: ${available_space}GB available (minimum 5GB required)"
        return 1
    fi
    
    # Check memory (recommend 4GB+)
    local available_mem=$(free -g | awk 'NR==2{print $7}')
    if [ "$available_mem" -lt 2 ]; then
        log_warning "Low memory: ${available_mem}GB available (recommended 4GB+)"
    fi
    
    # Check required files
    local required_files=("Dockerfile.api" "Dockerfile.agents" "Dockerfile.health-monitor" "Dockerfile.celery" "requirements.txt")
    for file in "${required_files[@]}"; do
        if [ ! -f "$file" ]; then
            log_error "Required file not found: $file"
            return 1
        fi
    done
    
    log_success "Pre-build checks passed"
    return 0
}

# Build optimization setup
setup_build_optimization() {
    log_info "Setting up build optimization..."
    
    # Enable BuildKit for better caching and parallelism
    export DOCKER_BUILDKIT=1
    export COMPOSE_DOCKER_CLI_BUILD=1
    
    # Create .dockerignore if it doesn't exist or enhance it
    if [ ! -f ".dockerignore" ]; then
        log_info "Creating .dockerignore for build optimization..."
        cat > .dockerignore << 'EOF'
# Optimize build context
data/backups/
data/raw/
data/processed/
logs/
*.log
monitoring/grafana/
monitoring/prometheus/
.prometheus/
.grafana/
*.test
*_test.py
test_*.py
**/__pycache__/
**/*.pyc
.pytest_cache/
.coverage
htmlcov/
*.egg-info/
.git
.gitignore
README.md
*.md
docs/
EOF
    fi
    
    # Ensure required directories exist
    mkdir -p data/{postgres,redis,weaviate,celery-beat,prometheus,grafana}
    mkdir -p logs
    mkdir -p config/{api,agents,health-monitor,celery}
    
    log_success "Build optimization setup complete"
}

# Build specific service
build_service() {
    local service="$1"
    local start_time=$(date +%s)
    
    log_info "Building $service..."
    
    local build_cmd="docker-compose build"
    
    # Add build flags
    if [ "$NO_CACHE" = true ]; then
        build_cmd="$build_cmd --no-cache"
    fi
    
    # Add service name
    build_cmd="$build_cmd $service"
    
    # Execute build
    if eval "$build_cmd" 2>&1 | tee -a "$LOG_FILE"; then
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_success "$service built successfully in ${duration}s"
        
        # Check image size
        local image_info=$(docker images --format "table {{.Repository}}:{{.Tag}}\\t{{.Size}}" | grep -E "reagent.*$service|reagent.*$service" | head -1)
        if [ -n "$image_info" ]; then
            log_info "$service image: $image_info"
        fi
        
        return 0
    else
        local end_time=$(date +%s)
        local duration=$((end_time - start_time))
        log_error "$service build failed after ${duration}s"
        return 1
    fi
}

# Build all services
build_all_services() {
    local services=("api" "orchestrator" "health-monitor" "celery-worker")
    local failed_services=()
    
    if [ "$PARALLEL" = true ]; then
        log_info "Building all services in parallel..."
        
        local build_cmd="docker-compose build"
        if [ "$NO_CACHE" = true ]; then
            build_cmd="$build_cmd --no-cache"
        fi
        build_cmd="$build_cmd --parallel ${services[*]}"
        
        if eval "$build_cmd" 2>&1 | tee -a "$LOG_FILE"; then
            log_success "All services built successfully in parallel"
            return 0
        else
            log_error "Parallel build failed"
            return 1
        fi
    else
        log_info "Building services sequentially..."
        
        for service in "${services[@]}"; do
            if ! build_service "$service"; then
                failed_services+=("$service")
            fi
        done
        
        if [ ${#failed_services[@]} -eq 0 ]; then
            log_success "All services built successfully"
            return 0
        else
            log_error "Failed to build services: ${failed_services[*]}"
            return 1
        fi
    fi
}

# Validate builds
validate_builds() {
    log_info "Validating built images..."
    
    local services=("api" "orchestrator" "health-monitor" "celery-worker")
    local validation_errors=0
    
    for service in "${services[@]}"; do
        # Check if image exists
        if docker images --format "{{.Repository}}" | grep -q "reagent.*$service\|reagent_.*$service"; then
            log_success "$service image exists"
            
            # Basic image inspection
            local image_id=$(docker images --format "{{.ID}}" | head -1)
            if [ -n "$image_id" ]; then
                local image_size=$(docker images --format "{{.Size}}" | head -1)
                log_info "$service image size: $image_size"
            fi
        else
            log_error "$service image not found"
            validation_errors=$((validation_errors + 1))
        fi
    done
    
    if [ $validation_errors -eq 0 ]; then
        log_success "All images validated successfully"
        return 0
    else
        log_error "$validation_errors validation errors found"
        return 1
    fi
}

# Quick smoke test
run_smoke_test() {
    log_info "Running quick smoke test..."
    
    # Test if we can start core services
    log_info "Testing core service startup..."
    
    # Start core infrastructure services
    if docker-compose up -d postgres redis weaviate; then
        log_success "Core services started"
        
        # Wait a moment for startup
        sleep 10
        
        # Check if services are responding
        local healthy_count=0
        
        if docker-compose ps postgres | grep -q "healthy\|running"; then
            log_success "PostgreSQL is responsive"
            healthy_count=$((healthy_count + 1))
        else
            log_warning "PostgreSQL not responsive"
        fi
        
        if docker-compose ps redis | grep -q "healthy\|running"; then
            log_success "Redis is responsive"
            healthy_count=$((healthy_count + 1))
        else
            log_warning "Redis not responsive"
        fi
        
        if docker-compose ps weaviate | grep -q "healthy\|running"; then
            log_success "Weaviate is responsive"
            healthy_count=$((healthy_count + 1))
        else
            log_warning "Weaviate not responsive"
        fi
        
        # Cleanup
        docker-compose down >/dev/null 2>&1
        
        if [ $healthy_count -ge 2 ]; then
            log_success "Smoke test passed ($healthy_count/3 services responsive)"
            return 0
        else
            log_warning "Smoke test partial ($healthy_count/3 services responsive)"
            return 1
        fi
    else
        log_error "Failed to start core services for smoke test"
        return 1
    fi
}

# Generate build report
generate_build_report() {
    log_info "Generating build report..."
    
    local report_file="build-report-${TIMESTAMP}.txt"
    
    {
        echo "ReAgent Docker Build Report"
        echo "=========================="
        echo "Timestamp: $(date)"
        echo "Build Type: $([ "$NO_CACHE" = true ] && echo "Clean Build" || echo "Cached Build")"
        echo "Parallel: $([ "$PARALLEL" = true ] && echo "Yes" || echo "No")"
        echo ""
        
        echo "Built Images:"
        echo "============"
        docker images --format "table {{.Repository}}:{{.Tag}}\\t{{.Size}}\\t{{.CreatedAt}}" | grep reagent || echo "No ReAgent images found"
        
        echo ""
        echo "Build Summary:"
        echo "============="
        echo "Total build time: $(grep -o '[0-9]*s$' "$LOG_FILE" | awk '{sum+=$1} END {print sum "s"}' || echo "Unknown")"
        echo "Log file: $LOG_FILE"
        echo "Report file: $report_file"
        
    } > "$report_file"
    
    log_success "Build report saved: $report_file"
}

# Cleanup function
cleanup() {
    # Stop any running containers from tests
    docker-compose down >/dev/null 2>&1 || true
}

# Main execution
main() {
    echo "ReAgent Quick Docker Build Script"
    echo "================================="
    echo "Timestamp: $(date)"
    echo "Working Directory: $SCRIPT_DIR"
    echo ""
    
    # Setup trap for cleanup
    trap cleanup EXIT
    
    # Initialize log
    echo "Build started at $(date)" > "$LOG_FILE"
    
    local exit_code=0
    
    # Run pre-build checks
    if ! pre_build_checks; then
        log_error "Pre-build checks failed"
        exit_code=1
    fi
    
    # Setup build optimization
    if [ $exit_code -eq 0 ]; then
        setup_build_optimization
    fi
    
    # If validate only, skip building
    if [ "$VALIDATE_ONLY" = true ]; then
        log_info "Validation-only mode, skipping builds"
        validate_builds
        exit_code=$?
    elif [ $exit_code -eq 0 ]; then
        # Build services
        if [ -n "$SPECIFIC_SERVICE" ]; then
            if ! build_service "$SPECIFIC_SERVICE"; then
                exit_code=1
            fi
        else
            if ! build_all_services; then
                exit_code=1
            fi
        fi
        
        # Validate builds
        if [ $exit_code -eq 0 ]; then
            if ! validate_builds; then
                exit_code=1
            fi
        fi
        
        # Run smoke test if builds succeeded
        if [ $exit_code -eq 0 ] && [ -z "$SPECIFIC_SERVICE" ]; then
            if ! run_smoke_test; then
                log_warning "Smoke test failed, but builds are complete"
                # Don't fail the entire build for smoke test issues
            fi
        fi
    fi
    
    # Generate report
    generate_build_report
    
    if [ $exit_code -eq 0 ]; then
        log_success "Quick build completed successfully! 🚀"
        log_info "Next steps:"
        log_info "  1. Review build report"
        log_info "  2. Run full validation: ./docker-build-validation.sh"
        log_info "  3. Start services: docker-compose up -d"
    else
        log_error "Quick build failed. Check $LOG_FILE for details."
    fi
    
    return $exit_code
}

# Execute main function
main "$@"