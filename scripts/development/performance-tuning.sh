#!/bin/bash

# ReAgent Sydney - Performance Tuning Script
# Optimize system performance for production workloads

set -euo pipefail

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log() {
    local level=$1
    shift
    echo -e "${GREEN}[$(date '+%Y-%m-%d %H:%M:%S')]${NC} ${level}: $*"
}

# System information gathering
gather_system_info() {
    log INFO "Gathering system information..."
    
    local total_memory=$(free -m | awk 'NR==2{printf "%.0f", $2}')
    local cpu_cores=$(nproc)
    local disk_space=$(df -h . | awk 'NR==2 {print $4}')
    
    echo "System Resources:"
    echo "- Memory: ${total_memory}MB"
    echo "- CPU Cores: $cpu_cores"
    echo "- Available Disk: $disk_space"
    echo
    
    # Store for later use
    export SYSTEM_MEMORY=$total_memory
    export SYSTEM_CORES=$cpu_cores
}

# PostgreSQL performance tuning
tune_postgresql() {
    log INFO "Applying PostgreSQL performance tuning..."
    
    # Calculate optimal settings based on system resources
    local shared_buffers=$((SYSTEM_MEMORY / 4))  # 25% of RAM
    local effective_cache_size=$((SYSTEM_MEMORY * 3 / 4))  # 75% of RAM
    local work_mem=$((SYSTEM_MEMORY / 100))  # 1% of RAM per connection
    local maintenance_work_mem=$((SYSTEM_MEMORY / 16))  # ~6% of RAM
    
    # Cap values to reasonable limits
    [[ $shared_buffers -gt 8192 ]] && shared_buffers=8192  # Max 8GB
    [[ $work_mem -lt 4 ]] && work_mem=4  # Min 4MB
    [[ $work_mem -gt 64 ]] && work_mem=64  # Max 64MB
    [[ $maintenance_work_mem -gt 2048 ]] && maintenance_work_mem=2048  # Max 2GB
    
    cat << EOF > config/postgres/performance.conf
# ReAgent Sydney - PostgreSQL Performance Settings
# Auto-generated based on system resources

# Memory settings
shared_buffers = ${shared_buffers}MB
effective_cache_size = ${effective_cache_size}MB
work_mem = ${work_mem}MB
maintenance_work_mem = ${maintenance_work_mem}MB

# Parallel query settings
max_parallel_workers_per_gather = $((SYSTEM_CORES / 2))
max_parallel_workers = $SYSTEM_CORES
max_parallel_maintenance_workers = $((SYSTEM_CORES / 4))

# Connection settings optimized for web application
max_connections = 200
shared_preload_libraries = 'timescaledb,pg_stat_statements'

# Checkpoint settings for better performance
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100

# Random page cost (SSD optimized)
random_page_cost = 1.1
effective_io_concurrency = 200

# Logging for performance monitoring
log_min_duration_statement = 1000
log_checkpoints = on
log_connections = off
log_disconnections = off
log_lock_waits = on
log_temp_files = 10MB

# Autovacuum tuning for high-churn real estate data
autovacuum_max_workers = 3
autovacuum_naptime = 1min
autovacuum_vacuum_scale_factor = 0.1
autovacuum_analyze_scale_factor = 0.05
EOF

    log INFO "PostgreSQL performance configuration created"
}

# Redis performance tuning
tune_redis() {
    log INFO "Applying Redis performance tuning..."
    
    local redis_memory=$((SYSTEM_MEMORY / 8))  # 12.5% of RAM for Redis
    [[ $redis_memory -lt 128 ]] && redis_memory=128  # Min 128MB
    [[ $redis_memory -gt 2048 ]] && redis_memory=2048  # Max 2GB
    
    cat << EOF > config/redis/performance.conf
# ReAgent Sydney - Redis Performance Settings

# Memory management
maxmemory ${redis_memory}mb
maxmemory-policy allkeys-lru
maxmemory-samples 10

# Persistence optimization
save 900 1
save 300 10
save 60 10000
stop-writes-on-bgsave-error yes
rdbcompression yes
rdbchecksum yes

# AOF settings
appendonly yes
appendfsync everysec
no-appendfsync-on-rewrite no
auto-aof-rewrite-percentage 100
auto-aof-rewrite-min-size 64mb

# Network optimizations
tcp-backlog 511
tcp-keepalive 300
timeout 0

# Performance tuning
hash-max-ziplist-entries 512
hash-max-ziplist-value 64
list-max-ziplist-size -2
set-max-intset-entries 512
zset-max-ziplist-entries 128
zset-max-ziplist-value 64

# Threading (Redis 6.0+)
# io-threads 4
# io-threads-do-reads yes

# Client output buffer limits
client-output-buffer-limit normal 0 0 0
client-output-buffer-limit replica 256mb 64mb 60
client-output-buffer-limit pubsub 32mb 8mb 60

# Slow log
slowlog-log-slower-than 10000
slowlog-max-len 128

# Latency monitoring
latency-monitor-threshold 100
EOF

    log INFO "Redis performance configuration created"
}

# Create connection pooling configuration
setup_connection_pooling() {
    log INFO "Setting up connection pooling configuration..."
    
    # Calculate optimal pool sizes
    local db_pool_size=$((SYSTEM_CORES * 5))  # 5 connections per core
    local db_max_overflow=$((db_pool_size / 2))
    local redis_max_connections=$((SYSTEM_CORES * 3))
    
    [[ $db_pool_size -gt 50 ]] && db_pool_size=50
    [[ $redis_max_connections -gt 30 ]] && redis_max_connections=30
    
    cat << EOF > config/connection-pools.env
# ReAgent Sydney - Connection Pool Settings

# PostgreSQL connection pooling
DB_POOL_SIZE=$db_pool_size
DB_MAX_OVERFLOW=$db_max_overflow
DB_POOL_TIMEOUT=30
DB_POOL_RECYCLE=3600

# Redis connection pooling  
REDIS_MAX_CONNECTIONS=$redis_max_connections
REDIS_RETRY_ON_TIMEOUT=true
REDIS_SOCKET_KEEPALIVE=true
REDIS_SOCKET_KEEPALIVE_OPTIONS=1,3,5

# API worker configuration
API_WORKERS=$((SYSTEM_CORES * 2))
CELERY_WORKERS=$((SYSTEM_CORES))
CELERY_MAX_TASKS_PER_CHILD=1000

# Request timeouts
REQUEST_TIMEOUT=30
DATABASE_TIMEOUT=30
REDIS_TIMEOUT=5
EOF

    log INFO "Connection pooling configuration created"
}

# Create performance monitoring queries
create_performance_monitoring() {
    log INFO "Creating performance monitoring queries..."
    
    mkdir -p monitoring/queries
    
    cat << 'EOF' > monitoring/queries/performance-metrics.sql
-- ReAgent Sydney - Performance Monitoring Queries

-- Database connection monitoring
CREATE OR REPLACE VIEW active_connections AS
SELECT 
    datname,
    usename,
    application_name,
    client_addr,
    state,
    query_start,
    state_change,
    NOW() - query_start as query_duration,
    query
FROM pg_stat_activity 
WHERE state != 'idle'
ORDER BY query_start;

-- Slow query analysis
CREATE OR REPLACE VIEW slow_queries AS
SELECT 
    query,
    calls,
    total_time,
    mean_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements 
WHERE calls > 5 AND mean_time > 100
ORDER BY mean_time DESC;

-- Table bloat analysis
CREATE OR REPLACE VIEW table_bloat AS
SELECT 
    schemaname,
    tablename,
    pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size,
    n_dead_tup,
    n_live_tup,
    CASE 
        WHEN n_live_tup > 0 
        THEN round(n_dead_tup::numeric / n_live_tup::numeric * 100, 2)
        ELSE 0 
    END as dead_tuple_percent
FROM pg_stat_user_tables
WHERE n_live_tup > 0
ORDER BY dead_tuple_percent DESC;

-- Index usage analysis
CREATE OR REPLACE VIEW unused_indexes AS
SELECT 
    schemaname,
    tablename,
    indexname,
    idx_tup_read,
    idx_tup_fetch,
    pg_size_pretty(pg_relation_size(indexrelid)) as size
FROM pg_stat_user_indexes 
WHERE idx_tup_read = 0 AND idx_tup_fetch = 0
ORDER BY pg_relation_size(indexrelid) DESC;

-- Real estate specific performance metrics
CREATE OR REPLACE VIEW reagent_performance_summary AS
SELECT 
    'properties' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as new_rows_24h,
    COUNT(CASE WHEN updated_at > NOW() - INTERVAL '1 hour' THEN 1 END) as updated_rows_1h,
    pg_size_pretty(pg_total_relation_size('properties')) as table_size
FROM properties
UNION ALL
SELECT 
    'buyers' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as new_rows_24h,
    COUNT(CASE WHEN updated_at > NOW() - INTERVAL '1 hour' THEN 1 END) as updated_rows_1h,
    pg_size_pretty(pg_total_relation_size('buyers')) as table_size
FROM buyers
UNION ALL
SELECT 
    'property_matches' as table_name,
    COUNT(*) as total_rows,
    COUNT(CASE WHEN created_at > NOW() - INTERVAL '24 hours' THEN 1 END) as new_rows_24h,
    COUNT(CASE WHEN updated_at > NOW() - INTERVAL '1 hour' THEN 1 END) as updated_rows_1h,
    pg_size_pretty(pg_total_relation_size('property_matches')) as table_size
FROM property_matches;
EOF

    log INFO "Performance monitoring queries created"
}

# Create caching strategy configuration
setup_caching_strategy() {
    log INFO "Setting up caching strategy..."
    
    cat << 'EOF' > config/caching-strategy.yaml
# ReAgent Sydney - Caching Strategy Configuration

redis_cache_configs:
  # Property data caching
  properties:
    ttl: 3600  # 1 hour
    pattern: "property:{property_id}"
    serializer: "json"
    
  # Suburb data caching (longer TTL as it changes less frequently)
  suburbs:
    ttl: 86400  # 24 hours
    pattern: "suburb:{suburb}:{postcode}"
    serializer: "json"
    
  # Market trends caching
  market_trends:
    ttl: 7200  # 2 hours
    pattern: "trends:{geography}:{period}"
    serializer: "json"
    
  # Buyer preferences caching
  buyer_preferences:
    ttl: 1800  # 30 minutes
    pattern: "buyer_prefs:{buyer_id}"
    serializer: "json"
    
  # Search results caching
  search_results:
    ttl: 900   # 15 minutes
    pattern: "search:{hash}"
    serializer: "json"
    max_results: 1000
    
  # API rate limiting
  rate_limits:
    ttl: 3600  # 1 hour
    pattern: "rate_limit:{ip}:{endpoint}"
    serializer: "counter"

# Cache invalidation rules
invalidation_rules:
  property_updated:
    - "property:{property_id}"
    - "suburb:{suburb}:{postcode}"
    - "search:*"
    
  buyer_updated:
    - "buyer_prefs:{buyer_id}"
    - "property_matches:{buyer_id}:*"
    
  market_data_updated:
    - "trends:*"
    - "suburb:*"

# Cache warming strategies
cache_warming:
  popular_suburbs:
    query: "SELECT DISTINCT suburb, postcode FROM properties WHERE status = 'active' ORDER BY updated_at DESC LIMIT 100"
    pattern: "suburb:{suburb}:{postcode}"
    schedule: "0 */6 * * *"  # Every 6 hours
    
  active_buyers:
    query: "SELECT id FROM buyers WHERE status = 'active' AND last_activity > NOW() - INTERVAL '7 days' LIMIT 500"
    pattern: "buyer_prefs:{buyer_id}"
    schedule: "0 */4 * * *"  # Every 4 hours
EOF

    log INFO "Caching strategy configuration created"
}

# Create system optimization script
create_system_optimization() {
    log INFO "Creating system optimization script..."
    
    cat << 'EOF' > scripts/optimize-system.sh
#!/bin/bash

# ReAgent Sydney - System-level Optimizations

set -euo pipefail

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

optimize_kernel_parameters() {
    log "Optimizing kernel parameters..."
    
    # Create sysctl configuration for ReAgent
    cat << 'SYSCTL' > /etc/sysctl.d/99-reagent.conf
# ReAgent Sydney - Kernel Optimizations

# Network performance
net.core.rmem_max = 134217728
net.core.wmem_max = 134217728
net.ipv4.tcp_rmem = 4096 16384 134217728
net.ipv4.tcp_wmem = 4096 16384 134217728
net.core.netdev_max_backlog = 5000
net.ipv4.tcp_window_scaling = 1
net.ipv4.tcp_timestamps = 1
net.ipv4.tcp_sack = 1

# File handle limits
fs.file-max = 65536
fs.nr_open = 1048576

# Virtual memory settings
vm.swappiness = 10
vm.dirty_ratio = 15
vm.dirty_background_ratio = 5
vm.overcommit_memory = 1

# PostgreSQL optimizations
kernel.shmmax = 4294967296
kernel.shmall = 1048576
kernel.shmmni = 4096
kernel.sem = 250 32000 100 128

# Redis optimizations
vm.overcommit_memory = 1
net.core.somaxconn = 65535
SYSCTL

    # Apply settings
    sysctl -p /etc/sysctl.d/99-reagent.conf || log "WARNING: Could not apply all sysctl settings"
}

optimize_file_limits() {
    log "Optimizing file descriptor limits..."
    
    # Create limits configuration
    cat << 'LIMITS' > /etc/security/limits.d/99-reagent.conf
# ReAgent Sydney - File Descriptor Limits

* soft nofile 65536
* hard nofile 65536
* soft nproc 32768
* hard nproc 32768

postgres soft nofile 65536
postgres hard nofile 65536

redis soft nofile 65536
redis hard nofile 65536
LIMITS
}

optimize_docker() {
    log "Optimizing Docker configuration..."
    
    # Create Docker daemon configuration
    mkdir -p /etc/docker
    cat << 'DOCKER' > /etc/docker/daemon.json
{
  "log-driver": "json-file",
  "log-opts": {
    "max-size": "100m",
    "max-file": "3"
  },
  "storage-driver": "overlay2",
  "live-restore": true,
  "userland-proxy": false,
  "experimental": false,
  "metrics-addr": "127.0.0.1:9323",
  "default-ulimits": {
    "nofile": {
      "Hard": 65536,
      "Name": "nofile",
      "Soft": 65536
    }
  }
}
DOCKER

    # Restart Docker to apply changes
    systemctl restart docker || log "WARNING: Could not restart Docker"
}

create_performance_monitoring() {
    log "Setting up performance monitoring..."
    
    # Create performance monitoring script
    cat << 'MONITOR' > /usr/local/bin/reagent-monitor
#!/bin/bash

# ReAgent Performance Monitor
LOG_FILE="/var/log/reagent-performance.log"

{
    echo "=== ReAgent Performance Report - $(date) ==="
    
    echo "System Load:"
    uptime
    
    echo "Memory Usage:"
    free -h
    
    echo "Disk Usage:"
    df -h
    
    echo "Docker Container Stats:"
    docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}\t{{.BlockIO}}"
    
    echo "PostgreSQL Connections:"
    docker exec reagent-postgres psql -U reagent -d reagent -c "SELECT count(*) as active_connections FROM pg_stat_activity WHERE state = 'active';" 2>/dev/null || echo "N/A"
    
    echo "Redis Info:"
    docker exec reagent-redis-master redis-cli info memory | grep used_memory_human 2>/dev/null || echo "N/A"
    
    echo "=== End Report ==="
    echo
} >> "$LOG_FILE"

# Rotate log if it gets too large
if [[ -f "$LOG_FILE" && $(stat -f%z "$LOG_FILE" 2>/dev/null || stat -c%s "$LOG_FILE") -gt 10485760 ]]; then
    mv "$LOG_FILE" "$LOG_FILE.old"
fi
MONITOR

    chmod +x /usr/local/bin/reagent-monitor
    
    # Create cron job for monitoring
    echo "*/5 * * * * /usr/local/bin/reagent-monitor" | crontab -
}

# Main optimization function
main() {
    if [[ $EUID -eq 0 ]]; then
        optimize_kernel_parameters
        optimize_file_limits
        optimize_docker
        create_performance_monitoring
        log "System-level optimizations applied. Reboot recommended."
    else
        log "WARNING: Running as non-root. Some optimizations skipped."
        log "Run with sudo for full system optimization."
    fi
}

main "$@"
EOF

    chmod +x scripts/optimize-system.sh
    log INFO "System optimization script created"
}

# Create load testing configuration
create_load_testing() {
    log INFO "Creating load testing configuration..."
    
    mkdir -p testing/load
    
    cat << 'EOF' > testing/load/api-load-test.js
// ReAgent Sydney - API Load Testing with Artillery

module.exports = {
  config: {
    target: 'http://localhost:8000',
    phases: [
      { duration: 60, arrivalRate: 5, name: 'Warm up' },
      { duration: 120, arrivalRate: 10, name: 'Ramp up' },
      { duration: 300, arrivalRate: 20, name: 'Sustained load' },
      { duration: 60, arrivalRate: 50, name: 'Peak load' },
      { duration: 60, arrivalRate: 5, name: 'Cool down' }
    ],
    payload: {
      path: './test-data.csv',
      fields: ['suburb', 'postcode', 'property_type']
    }
  },
  scenarios: [
    {
      name: 'Property Search',
      weight: 40,
      flow: [
        { get: { url: '/api/v1/properties/search?suburb={{ suburb }}&property_type={{ property_type }}' } },
        { think: 2 }
      ]
    },
    {
      name: 'Suburb Analysis',
      weight: 30,
      flow: [
        { get: { url: '/api/v1/suburbs/{{ suburb }}/{{ postcode }}/trends' } },
        { think: 1 }
      ]
    },
    {
      name: 'Property Details',
      weight: 20,
      flow: [
        { get: { url: '/api/v1/properties/{{ $randomInt(1, 1000) }}' } },
        { think: 3 }
      ]
    },
    {
      name: 'Health Check',
      weight: 10,
      flow: [
        { get: { url: '/health' } }
      ]
    }
  ]
};
EOF

    # Create test data
    cat << 'EOF' > testing/load/test-data.csv
suburb,postcode,property_type
Bondi,2026,apartment
Surry Hills,2010,apartment
Paddington,2021,terrace
Newtown,2042,house
Manly,2095,apartment
Balmain,2041,terrace
Glebe,2037,apartment
Coogee,2034,apartment
Leichhardt,2040,house
Darlinghurst,2010,apartment
EOF

    log INFO "Load testing configuration created"
}

# Main performance tuning function
main() {
    log INFO "Starting ReAgent Sydney performance tuning..."
    
    gather_system_info
    tune_postgresql
    tune_redis
    setup_connection_pooling
    create_performance_monitoring
    setup_caching_strategy
    create_system_optimization
    create_load_testing
    
    echo
    echo -e "${GREEN}Performance tuning completed!${NC}"
    echo
    echo "Next steps:"
    echo "1. Review generated configuration files in config/"
    echo "2. Run 'sudo ./scripts/optimize-system.sh' for system-level optimizations"
    echo "3. Restart ReAgent services to apply database/Redis settings"
    echo "4. Monitor performance using the created queries and tools"
    echo "5. Run load tests with: cd testing/load && artillery run api-load-test.js"
    echo
    echo "Configuration files created:"
    echo "- config/postgres/performance.conf"
    echo "- config/redis/performance.conf"
    echo "- config/connection-pools.env"
    echo "- config/caching-strategy.yaml"
    echo "- monitoring/queries/performance-metrics.sql"
    echo "- scripts/optimize-system.sh"
    echo "- testing/load/api-load-test.js"
}

# Run main function
main "$@"