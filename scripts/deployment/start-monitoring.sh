#!/bin/bash

# ReAgent Sydney - Start Monitoring System
# Comprehensive script to start all monitoring components

set -e

echo "🚀 Starting ReAgent Sydney Monitoring System"
echo "=============================================="

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    local status=$1
    local message=$2
    case $status in
        "SUCCESS")
            echo -e "${GREEN}✅ $message${NC}"
            ;;
        "WARNING")
            echo -e "${YELLOW}⚠️  $message${NC}"
            ;;
        "ERROR")
            echo -e "${RED}❌ $message${NC}"
            ;;
        "INFO")
            echo -e "ℹ️  $message"
            ;;
    esac
}

# Check if Docker is running
if ! docker info >/dev/null 2>&1; then
    print_status "ERROR" "Docker is not running. Please start Docker first."
    exit 1
fi

print_status "SUCCESS" "Docker is running"

# Check if we're in the right directory
if [[ ! -f "docker-compose.monitoring.yml" ]]; then
    print_status "ERROR" "docker-compose.monitoring.yml not found. Please run from ReAgent root directory."
    exit 1
fi

# Create necessary directories
print_status "INFO" "Creating monitoring data directories..."
mkdir -p data/{prometheus,grafana,alertmanager}
mkdir -p logs/{grafana,nginx}

# Check for environment variables
print_status "INFO" "Checking environment configuration..."

if [[ ! -f ".env" ]]; then
    print_status "WARNING" ".env file not found. Creating from template..."
    if [[ -f ".env.production.template" ]]; then
        cp .env.production.template .env
        print_status "INFO" "Please edit .env file with your configuration before continuing"
        print_status "INFO" "Press Enter when ready to continue..."
        read
    else
        print_status "ERROR" "No .env template found. Please create .env file manually."
        exit 1
    fi
fi

# Load environment variables
source .env

# Create Docker networks if they don't exist
print_status "INFO" "Creating Docker networks..."
networks=("reagent-monitoring" "reagent-backend" "reagent-frontend")

for network in "${networks[@]}"; do
    if ! docker network inspect "$network" >/dev/null 2>&1; then
        docker network create "$network"
        print_status "SUCCESS" "Created network: $network"
    else
        print_status "INFO" "Network already exists: $network"
    fi
done

# Start core infrastructure first (if not running)
print_status "INFO" "Checking core infrastructure..."

core_services=("postgres" "redis-master" "weaviate")
missing_services=()

for service in "${core_services[@]}"; do
    if ! docker ps --format "table {{.Names}}" | grep -q "reagent-$service"; then
        missing_services+=("$service")
    fi
done

if [[ ${#missing_services[@]} -gt 0 ]]; then
    print_status "WARNING" "Core services not running: ${missing_services[*]}"
    print_status "INFO" "Starting core infrastructure..."
    
    if [[ -f "docker-compose.prod.yml" ]]; then
        docker-compose -f docker-compose.prod.yml up -d postgres redis-master weaviate
        sleep 10  # Wait for services to start
        print_status "SUCCESS" "Core infrastructure started"
    else
        print_status "ERROR" "docker-compose.prod.yml not found. Please start core services first."
        exit 1
    fi
fi

# Start monitoring stack
print_status "INFO" "Starting monitoring stack..."

docker-compose -f docker-compose.monitoring.yml up -d

# Wait for services to be ready
print_status "INFO" "Waiting for services to start..."
sleep 15

# Check service health
print_status "INFO" "Checking service health..."

services=(
    "prometheus:9090:prometheus"
    "grafana:3001:grafana" 
    "alertmanager:9093:alertmanager"
)

all_healthy=true

for service_info in "${services[@]}"; do
    IFS=':' read -r service port name <<< "$service_info"
    
    if curl -f "http://localhost:$port" >/dev/null 2>&1 || 
       curl -f "http://localhost:$port/-/healthy" >/dev/null 2>&1 || 
       curl -f "http://localhost:$port/api/health" >/dev/null 2>&1; then
        print_status "SUCCESS" "$name is healthy (port $port)"
    else
        print_status "ERROR" "$name is not responding (port $port)"
        all_healthy=false
    fi
done

# Check exporters
print_status "INFO" "Checking exporters..."

exporters=(
    "postgres-exporter:9187"
    "redis-exporter:9121"
    "node-exporter:9100"
    "cadvisor:8080"
)

for exporter_info in "${exporters[@]}"; do
    IFS=':' read -r exporter port <<< "$exporter_info"
    
    if curl -f "http://localhost:$port/metrics" >/dev/null 2>&1; then
        print_status "SUCCESS" "$exporter is running (port $port)"
    else
        print_status "WARNING" "$exporter may not be responding (port $port)"
    fi
done

# Display service URLs
echo ""
print_status "INFO" "Monitoring Services URLs:"
echo "  🔍 Prometheus:    http://localhost:9090"
echo "  📊 Grafana:       http://localhost:3001 (admin/admin)"
echo "  🚨 AlertManager:  http://localhost:9093"
echo ""

# Run basic health check
print_status "INFO" "Running basic health check..."

if command -v python3 >/dev/null 2>&1; then
    if [[ -f "test_monitoring_system.py" ]]; then
        python3 test_monitoring_system.py --quick
    else
        print_status "WARNING" "Monitoring test script not found"
    fi
else
    print_status "WARNING" "Python3 not available for health check"
fi

# Final status
if [[ "$all_healthy" == true ]]; then
    echo ""
    print_status "SUCCESS" "ReAgent Sydney Monitoring System is running!"
    print_status "INFO" "Check the URLs above to access the monitoring interfaces"
    
    # Show container status
    echo ""
    echo "📦 Container Status:"
    docker ps --filter "name=reagent" --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
    
else
    echo ""
    print_status "WARNING" "Some services may not be fully healthy"
    print_status "INFO" "Check the logs for more information:"
    echo "  docker-compose -f docker-compose.monitoring.yml logs"
fi

# Provide next steps
echo ""
print_status "INFO" "Next Steps:"
echo "  1. Access Grafana at http://localhost:3001 (admin/admin)"
echo "  2. Import dashboards from monitoring/grafana/dashboards/"
echo "  3. Configure alert notifications in AlertManager"
echo "  4. Review monitoring runbooks: MONITORING_RUNBOOKS.md"
echo ""

# Optional: Start ReAgent application services
echo "Do you want to start the ReAgent application services as well? (y/N)"
read -r start_app

if [[ "$start_app" =~ ^[Yy]$ ]]; then
    print_status "INFO" "Starting ReAgent application services..."
    docker-compose -f docker-compose.prod.yml up -d
    print_status "SUCCESS" "Application services started"
    echo "  🌐 ReAgent API:   http://localhost:8001"
fi

print_status "SUCCESS" "Monitoring system setup complete!"