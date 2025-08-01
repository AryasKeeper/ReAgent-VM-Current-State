#!/bin/bash
# ReAgent Sydney - Production Deployment Script
# Cloud-native deployment with comprehensive validation

set -euo pipefail

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
ENVIRONMENT="${ENVIRONMENT:-development}"
COMPOSE_FILE="${PROJECT_ROOT}/docker-compose.yml"
OVERRIDE_FILE="${PROJECT_ROOT}/docker-compose.override.yml"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Logging functions
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    # Check Docker
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed or not in PATH"
        exit 1
    fi
    
    # Check Docker Compose
    if ! docker compose version &> /dev/null; then
        log_error "Docker Compose is not available"
        exit 1
    fi
    
    # Check environment files
    if [[ "$ENVIRONMENT" == "production" ]]; then
        if [[ ! -f "$PROJECT_ROOT/.env.production" ]]; then
            log_warning "Production environment file not found: .env.production"
            log_info "Using development environment variables"
        fi
    fi
    
    log_success "Prerequisites check completed"
}

# Validate configuration
validate_configuration() {
    log_info "Validating configuration..."
    
    # Check required directories
    local required_dirs=(
        "$PROJECT_ROOT/logs"
        "$PROJECT_ROOT/data/backups/postgres"
        "$PROJECT_ROOT/data/backups/weaviate"
        "$PROJECT_ROOT/config/nginx"
    )
    
    for dir in "${required_dirs[@]}"; do
        if [[ ! -d "$dir" ]]; then
            log_info "Creating directory: $dir"
            mkdir -p "$dir"
        fi
    done
    
    # Validate environment variables
    local required_vars=("OPENAI_API_KEY")
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var:-}" ]] && [[ -z "${!var}" ]]; then
            log_warning "Required environment variable not set: $var"
        fi
    done
    
    log_success "Configuration validation completed"
}

# Build images
build_images() {
    log_info "Building Docker images..."
    
    local build_args=""
    if [[ "$ENVIRONMENT" == "production" ]]; then
        build_args="--build-arg BUILD_ENV=production"
    fi
    
    # Build with no cache for production, with cache for development
    local cache_flag=""
    if [[ "$ENVIRONMENT" == "production" ]]; then
        cache_flag="--no-cache"
    fi
    
    docker compose -f "$COMPOSE_FILE" build $cache_flag $build_args
    
    log_success "Docker images built successfully"
}

# Deploy services
deploy_services() {
    log_info "Deploying services..."
    
    local compose_files="-f $COMPOSE_FILE"
    if [[ -f "$OVERRIDE_FILE" ]] && [[ "$ENVIRONMENT" == "production" ]]; then
        compose_files="$compose_files -f $OVERRIDE_FILE"
    fi
    
    # Start infrastructure services first
    log_info "Starting infrastructure services..."
    docker compose $compose_files up -d postgres redis weaviate
    
    # Wait for infrastructure to be healthy
    log_info "Waiting for infrastructure services to be healthy..."
    sleep 30
    
    # Check health of infrastructure services individually
    local services=("postgres" "redis" "weaviate")
    for service in "${services[@]}"; do
        log_info "Waiting for $service to be healthy..."
        local max_attempts=24
        local attempt=1
        
        while [[ $attempt -le $max_attempts ]]; do
            local health_status=$(docker compose $compose_files ps --format json | jq -r '.[] | select(.Service == "'$service'") | .Health' 2>/dev/null || echo "starting")
            
            if [[ "$health_status" == "healthy" ]]; then
                log_success "$service is healthy"
                break
            elif [[ "$health_status" == "unhealthy" ]]; then
                log_error "$service is unhealthy"
                docker compose $compose_files logs "$service" --tail=20
                exit 1
            else
                echo -n "."
                sleep 5
                ((attempt++))
            fi
            
            if [[ $attempt -gt $max_attempts ]]; then
                log_error "$service failed to become healthy within timeout"
                docker compose $compose_files logs "$service" --tail=30
                exit 1
            fi
        done
    done
    
    # Start application services
    log_info "Starting application services..."
    docker compose $compose_files up -d
    
    log_success "Services deployed successfully"
}

# Validate deployment
validate_deployment() {
    log_info "Validating deployment..."
    
    # Wait for services to start
    sleep 30
    
    # Check API health
    local api_url="http://localhost:8000/api/v1/health/ready"
    local max_attempts=6
    local attempt=1
    
    while [[ $attempt -le $max_attempts ]]; do
        log_info "Testing API health (attempt $attempt/$max_attempts)..."
        
        if curl -f -s "$api_url" > /dev/null; then
            log_success "API is responding to health checks"
            break
        else
            if [[ $attempt -eq $max_attempts ]]; then
                log_error "API health check failed after $max_attempts attempts"
                log_error "API logs:"
                docker compose logs api --tail=20
                exit 1
            fi
            sleep 10
            ((attempt++))
        fi
    done
    
    # Check service status
    log_info "Checking service status..."
    docker compose ps
    
    # Show resource usage
    log_info "Resource usage:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}"
    
    log_success "Deployment validation completed"
}

# Comprehensive cleanup function
cleanup() {
    local clean_volumes="${1:-false}"
    
    log_info "Performing comprehensive cleanup..."
    
    # Stop and remove containers
    if docker compose ps -q 2>/dev/null | grep -q .; then
        log_info "Stopping running containers..."
        docker compose down --remove-orphans
    fi
    
    # Remove dangling containers
    local dangling=$(docker ps -a --filter "name=reagent-" --format "{{.Names}}" 2>/dev/null || true)
    if [[ -n "$dangling" ]]; then
        log_info "Removing dangling containers: $dangling"
        echo "$dangling" | xargs -r docker rm -f
    fi
    
    # Clean networks
    local networks=$(docker network ls --filter "name=reagent" --format "{{.Name}}" 2>/dev/null || true)
    if [[ -n "$networks" ]]; then
        log_info "Removing networks: $networks"
        echo "$networks" | xargs -r docker network rm 2>/dev/null || true
    fi
    
    # Clean volumes if requested
    if [[ "$clean_volumes" == "true" ]]; then
        local volumes=$(docker volume ls --filter "name=reagent-" --format "{{.Name}}" 2>/dev/null || true)
        if [[ -n "$volumes" ]]; then
            log_warning "Removing data volumes: $volumes"
            echo "$volumes" | xargs -r docker volume rm 2>/dev/null || true
        fi
    fi
    
    # Clean unused resources
    log_info "Cleaning unused Docker resources..."
    docker system prune -f
    
    log_success "Cleanup completed"
}

# Main deployment function
main() {
    log_info "Starting ReAgent Sydney deployment..."
    log_info "Environment: $ENVIRONMENT"
    log_info "Project root: $PROJECT_ROOT"
    
    check_prerequisites
    validate_configuration
    build_images
    deploy_services
    validate_deployment
    
    log_success "ReAgent Sydney deployment completed successfully!"
    log_info "API available at: http://localhost:8000"
    log_info "Grafana dashboard: http://localhost:3001 (admin/admin)"
    log_info "Prometheus metrics: http://localhost:9090"
    
    if [[ "$ENVIRONMENT" == "production" ]]; then
        log_info "Production deployment notes:"
        log_info "- Configure SSL certificates in data/ssl/"
        log_info "- Update DNS to point to this server"
        log_info "- Set up external monitoring and alerting"
        log_info "- Configure database backups"
    fi
}

# Handle script arguments
case "${1:-deploy}" in
    "deploy")
        main
        ;;
    "build")
        check_prerequisites
        build_images
        ;;
    "validate")
        validate_deployment
        ;;
    "cleanup")
        cleanup "${2:-false}"
        ;;
    "cleanup-all")
        cleanup "true"
        ;;
    "logs")
        docker compose logs -f "${2:-}"
        ;;
    "stop")
        log_info "Stopping all services..."
        docker compose down --remove-orphans
        ;;
    "restart")
        log_info "Restarting services..."
        docker compose restart "${2:-}"
        ;;
    "status")
        log_info "Current service status:"
        docker compose ps
        ;;
    *)
        log_info "Usage: $0 [deploy|build|validate|cleanup|cleanup-all|logs|stop|restart|status]"
        log_info "  deploy      - Full deployment (default)"
        log_info "  build       - Build images only"
        log_info "  validate    - Validate running deployment"
        log_info "  cleanup     - Clean up containers and networks"
        log_info "  cleanup-all - Clean up containers, networks, and volumes"
        log_info "  logs        - Show logs (optional service name)"
        log_info "  stop        - Stop all services"
        log_info "  restart     - Restart services (optional service name)"
        log_info "  status      - Show service status"
        exit 1
        ;;
esac