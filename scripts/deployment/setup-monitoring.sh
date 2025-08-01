#!/bin/bash

# ReAgent Sydney - Comprehensive Monitoring Setup Script
# Enterprise-grade monitoring infrastructure with Prometheus, Grafana, and AlertManager
# Version: 1.0
# Author: ReAgent Operations Team

set -euo pipefail

# =================================================================
# CONFIGURATION
# =================================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
MONITORING_CONFIG_DIR="$PROJECT_ROOT/monitoring"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
SETUP_LOG="/var/log/reagent/monitoring_setup_${TIMESTAMP}.log"

# Environment variables
ENVIRONMENT="${ENVIRONMENT:-production}"
GRAFANA_ADMIN_PASSWORD="${GRAFANA_ADMIN_PASSWORD:-$(openssl rand -base64 32)}"
GRAFANA_SECRET_KEY="${GRAFANA_SECRET_KEY:-$(openssl rand -base64 32)}"
SMTP_HOST="${SMTP_HOST:-}"
SMTP_PORT="${SMTP_PORT:-587}"
SMTP_USER="${SMTP_USER:-}"
SMTP_PASSWORD="${SMTP_PASSWORD:-}"
SLACK_WEBHOOK_URL="${SLACK_WEBHOOK_URL:-}"
PAGERDUTY_SERVICE_KEY="${PAGERDUTY_SERVICE_KEY:-}"

# =================================================================
# LOGGING FUNCTIONS
# =================================================================

log() {
    local level="$1"
    shift
    local message="$*"
    local timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    
    case "$level" in
        "INFO")  echo -e "${BLUE}[INFO]${NC} ${timestamp} - $message" | tee -a "$SETUP_LOG" ;;
        "WARN")  echo -e "${YELLOW}[WARN]${NC} ${timestamp} - $message" | tee -a "$SETUP_LOG" ;;
        "ERROR") echo -e "${RED}[ERROR]${NC} ${timestamp} - $message" | tee -a "$SETUP_LOG" ;;
        "SUCCESS") echo -e "${GREEN}[SUCCESS]${NC} ${timestamp} - $message" | tee -a "$SETUP_LOG" ;;
    esac
}

error_exit() {
    log "ERROR" "$1"
    exit 1
}

# =================================================================
# VALIDATION FUNCTIONS
# =================================================================

validate_prerequisites() {
    log "INFO" "Validating monitoring setup prerequisites..."
    
    # Check if running with appropriate permissions
    if [[ ! -w "$PROJECT_ROOT" ]]; then
        error_exit "Insufficient permissions to write to project directory: $PROJECT_ROOT"
    fi
    
    # Check required commands
    local required_commands=("docker" "docker-compose" "curl" "jq" "openssl")
    for cmd in "${required_commands[@]}"; do
        if ! command -v "$cmd" &> /dev/null; then
            error_exit "Required command '$cmd' not found. Please install it first."
        fi
    done
    
    # Check if Docker is running
    if ! docker info &> /dev/null; then
        error_exit "Docker daemon is not running or not accessible"
    fi
    
    # Check if ReAgent production stack is running
    if ! docker-compose -f "$PROJECT_ROOT/docker-compose.prod.yml" ps | grep -q "Up"; then
        log "WARN" "ReAgent production stack is not running. Some monitoring features may not work until it's started."
    fi
    
    log "SUCCESS" "Prerequisites validation completed successfully"
}

# =================================================================
# PROMETHEUS CONFIGURATION
# =================================================================

setup_prometheus_config() {
    log "INFO" "Setting up Prometheus configuration..."
    
    local prometheus_dir="$MONITORING_CONFIG_DIR/prometheus"
    local alert_rules_dir="$prometheus_dir/alert_rules"
    
    mkdir -p "$prometheus_dir" "$alert_rules_dir"
    
    # Create main Prometheus configuration
    cat > "$prometheus_dir/prometheus.yml" << 'EOF'
# ReAgent Sydney - Prometheus Configuration
# Complete monitoring setup for production environment

global:
  scrape_interval: 15s
  evaluation_interval: 15s
  external_labels:
    environment: 'production'
    service: 'reagent-sydney'
    region: 'sydney'

# Load alerting rules
rule_files:
  - "/etc/prometheus/alert_rules/*.yml"

# AlertManager configuration
alerting:
  alertmanagers:
    - static_configs:
        - targets:
          - alertmanager:9093
      timeout: 10s
      api_version: v2

# Scrape configuration
scrape_configs:
  # Prometheus self-monitoring
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
    scrape_interval: 30s
    metrics_path: /metrics

  # ReAgent API monitoring
  - job_name: 'reagent-api'
    static_configs:
      - targets: ['api:8001']
    scrape_interval: 15s
    metrics_path: /metrics
    scrape_timeout: 10s
    params:
      format: ['prometheus']

  # ReAgent Agents monitoring
  - job_name: 'reagent-agents'
    static_configs:
      - targets: ['agents:8002']
    scrape_interval: 30s
    metrics_path: /metrics
    scrape_timeout: 10s

  # PostgreSQL monitoring
  - job_name: 'postgresql-primary'
    static_configs:
      - targets: ['postgres-exporter:9187']
    scrape_interval: 30s
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'postgres-primary'

  # PostgreSQL replica monitoring
  - job_name: 'postgresql-replica'
    static_configs:
      - targets: ['postgres-replica-exporter:9187']
    scrape_interval: 30s
    relabel_configs:
      - source_labels: [__address__]
        target_label: instance
        replacement: 'postgres-replica'

  # Redis monitoring
  - job_name: 'redis'
    static_configs:
      - targets: ['redis-exporter:9121']
    scrape_interval: 30s

  # Nginx monitoring
  - job_name: 'nginx'
    static_configs:
      - targets: ['nginx-exporter:9113']
    scrape_interval: 30s

  # Celery task queue monitoring
  - job_name: 'celery'
    static_configs:
      - targets: ['celery-exporter:9540']
    scrape_interval: 30s

  # System metrics monitoring
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
    scrape_interval: 30s

  # Container metrics monitoring
  - job_name: 'cadvisor'
    static_configs:
      - targets: ['cadvisor:8080']
    scrape_interval: 30s
    metrics_path: /metrics

  # Weaviate vector database monitoring
  - job_name: 'weaviate'
    static_configs:
      - targets: ['weaviate:8080']
    scrape_interval: 30s
    metrics_path: /metrics
    scrape_timeout: 10s

# Remote write configuration (optional - for long-term storage)
# remote_write:
#   - url: "https://your-remote-prometheus-endpoint/api/v1/write"
#     basic_auth:
#       username: "your-username"
#       password: "your-password"

# Storage configuration
storage:
  tsdb:
    retention.time: 30d
    retention.size: 10GB
    wal-compression: true
EOF

    log "SUCCESS" "Prometheus configuration created successfully"
}

setup_alert_rules() {
    log "INFO" "Setting up Prometheus alert rules..."
    
    local alert_rules_dir="$MONITORING_CONFIG_DIR/prometheus/alert_rules"
    mkdir -p "$alert_rules_dir"
    
    # Create comprehensive alert rules for ReAgent
    cat > "$alert_rules_dir/reagent_alerts.yml" << 'EOF'
# ReAgent Sydney - Comprehensive Alert Rules
# Production-ready alerting for all system components

groups:
  # =================================================================
  # APPLICATION HEALTH ALERTS
  # =================================================================
  - name: reagent_application
    rules:
      - alert: ReAgentAPIDown
        expr: up{job="reagent-api"} == 0
        for: 1m
        labels:
          severity: critical
          service: api
          team: platform
        annotations:
          summary: "ReAgent API is down"
          description: "ReAgent API has been down for more than 1 minute"
          runbook_url: "https://docs.reagent.com/runbooks/api-down"

      - alert: ReAgentAgentsDown
        expr: up{job="reagent-agents"} == 0
        for: 2m
        labels:
          severity: critical
          service: agents
          team: platform
        annotations:
          summary: "ReAgent Agents orchestrator is down"
          description: "ReAgent Agents orchestrator has been down for more than 2 minutes"

      - alert: ReAgentAPIHighErrorRate
        expr: rate(http_requests_total{job="reagent-api",status=~"5.."}[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
          service: api
          team: platform
        annotations:
          summary: "High error rate in ReAgent API"
          description: "ReAgent API error rate is {{ $value | humanizePercentage }} over the last 5 minutes"

      - alert: ReAgentAPISlowResponse
        expr: histogram_quantile(0.95, rate(http_request_duration_seconds_bucket{job="reagent-api"}[5m])) > 2
        for: 10m
        labels:
          severity: warning
          service: api
          team: platform
        annotations:
          summary: "ReAgent API slow response times"
          description: "95th percentile response time is {{ $value }}s over the last 5 minutes"

  # =================================================================
  # DATABASE HEALTH ALERTS
  # =================================================================
  - name: reagent_database
    rules:
      - alert: PostgreSQLDown
        expr: up{job=~"postgresql-.*"} == 0
        for: 1m
        labels:
          severity: critical
          service: database
          team: platform
        annotations:
          summary: "PostgreSQL instance is down"
          description: "PostgreSQL {{ $labels.instance }} has been down for more than 1 minute"

      - alert: PostgreSQLHighConnections
        expr: pg_stat_database_numbackends{job=~"postgresql-.*"} / pg_settings_max_connections{job=~"postgresql-.*"} > 0.8
        for: 5m
        labels:
          severity: warning
          service: database
          team: platform
        annotations:
          summary: "PostgreSQL high connection usage"
          description: "PostgreSQL {{ $labels.instance }} is using {{ $value | humanizePercentage }} of available connections"

      - alert: PostgreSQLReplicationLag
        expr: pg_replication_lag{job="postgresql-replica"} > 30
        for: 5m
        labels:
          severity: warning
          service: database
          team: platform
        annotations:
          summary: "PostgreSQL replication lag is high"
          description: "Replication lag is {{ $value }}s for replica {{ $labels.instance }}"

      - alert: PostgreSQLDiskSpaceHigh
        expr: (pg_database_size_bytes{job=~"postgresql-.*"} / 1024 / 1024 / 1024) > 50
        for: 10m
        labels:
          severity: warning
          service: database
          team: platform
        annotations:
          summary: "PostgreSQL database size is large"
          description: "Database {{ $labels.datname }} is {{ $value }}GB in size"

  # =================================================================
  # REDIS CACHE ALERTS
  # =================================================================
  - name: reagent_redis
    rules:
      - alert: RedisDown
        expr: up{job="redis"} == 0
        for: 1m
        labels:
          severity: critical
          service: cache
          team: platform
        annotations:
          summary: "Redis is down"
          description: "Redis has been down for more than 1 minute"

      - alert: RedisHighMemoryUsage
        expr: redis_memory_used_bytes{job="redis"} / redis_memory_max_bytes{job="redis"} > 0.9
        for: 5m
        labels:
          severity: warning
          service: cache
          team: platform
        annotations:
          summary: "Redis high memory usage"
          description: "Redis is using {{ $value | humanizePercentage }} of available memory"

      - alert: RedisHighConnectionCount
        expr: redis_connected_clients{job="redis"} > 100
        for: 10m
        labels:
          severity: warning
          service: cache
          team: platform
        annotations:
          summary: "Redis high connection count"
          description: "Redis has {{ $value }} connected clients"

  # =================================================================
  # VECTOR DATABASE ALERTS
  # =================================================================
  - name: reagent_weaviate
    rules:
      - alert: WeaviateDown
        expr: up{job="weaviate"} == 0
        for: 2m
        labels:
          severity: critical
          service: vector-db
          team: platform
        annotations:
          summary: "Weaviate vector database is down"
          description: "Weaviate has been down for more than 2 minutes"

      - alert: WeaviateHighQueryLatency
        expr: histogram_quantile(0.95, rate(weaviate_query_duration_seconds_bucket[5m])) > 1
        for: 10m
        labels:
          severity: warning
          service: vector-db
          team: platform
        annotations:
          summary: "Weaviate high query latency"
          description: "95th percentile query latency is {{ $value }}s"

  # =================================================================
  # SYSTEM RESOURCE ALERTS
  # =================================================================
  - name: reagent_system
    rules:
      - alert: HighCPUUsage
        expr: 100 - (avg by(instance) (irate(node_cpu_seconds_total{mode="idle"}[5m])) * 100) > 80
        for: 10m
        labels:
          severity: warning
          service: system
          team: platform
        annotations:
          summary: "High CPU usage"
          description: "CPU usage is {{ $value }}% on {{ $labels.instance }}"

      - alert: HighMemoryUsage
        expr: (1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100 > 85
        for: 10m
        labels:
          severity: warning
          service: system
          team: platform
        annotations:
          summary: "High memory usage"
          description: "Memory usage is {{ $value }}% on {{ $labels.instance }}"

      - alert: LowDiskSpace
        expr: (1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100 > 85
        for: 15m
        labels:
          severity: warning
          service: system
          team: platform
        annotations:
          summary: "Low disk space"
          description: "Disk usage is {{ $value }}% on {{ $labels.instance }} ({{ $labels.mountpoint }})"

      - alert: CriticalDiskSpace
        expr: (1 - (node_filesystem_avail_bytes{fstype!="tmpfs"} / node_filesystem_size_bytes{fstype!="tmpfs"})) * 100 > 95
        for: 5m
        labels:
          severity: critical
          service: system
          team: platform
        annotations:
          summary: "Critical disk space"
          description: "Disk usage is {{ $value }}% on {{ $labels.instance }} ({{ $labels.mountpoint }})"

  # =================================================================
  # BUSINESS LOGIC ALERTS
  # =================================================================
  - name: reagent_business
    rules:
      - alert: LowPropertyIngestRate
        expr: rate(reagent_properties_ingested_total[30m]) < 0.1
        for: 30m
        labels:
          severity: warning
          service: ingestion
          team: data
        annotations:
          summary: "Low property ingestion rate"
          description: "Property ingestion rate is {{ $value }} properties/second over the last 30 minutes"

      - alert: HighBuyerMatchingLatency
        expr: histogram_quantile(0.95, rate(reagent_buyer_matching_duration_seconds_bucket[10m])) > 5
        for: 15m
        labels:
          severity: warning
          service: matching
          team: ml
        annotations:
          summary: "High buyer matching latency"
          description: "95th percentile buyer matching latency is {{ $value }}s"

      - alert: AgentTaskFailureRate
        expr: rate(reagent_agent_tasks_failed_total[15m]) / rate(reagent_agent_tasks_total[15m]) > 0.1
        for: 10m
        labels:
          severity: warning
          service: agents
          team: platform
        annotations:
          summary: "High agent task failure rate"
          description: "Agent task failure rate is {{ $value | humanizePercentage }} over the last 15 minutes"

  # =================================================================
  # EXTERNAL API ALERTS
  # =================================================================
  - name: reagent_external_apis
    rules:
      - alert: DomainAPIHighErrorRate
        expr: rate(reagent_external_api_errors_total{api="domain"}[10m]) / rate(reagent_external_api_requests_total{api="domain"}[10m]) > 0.1
        for: 10m
        labels:
          severity: warning
          service: external-api
          team: integrations
        annotations:
          summary: "High Domain API error rate"
          description: "Domain API error rate is {{ $value | humanizePercentage }}"

      - alert: REAAPIRateLimitApproaching
        expr: reagent_external_api_rate_limit_remaining{api="rea"} / reagent_external_api_rate_limit_total{api="rea"} < 0.2
        for: 5m
        labels:
          severity: warning
          service: external-api
          team: integrations
        annotations:
          summary: "REA API rate limit approaching"
          description: "REA API has {{ $value | humanizePercentage }} of rate limit remaining"
EOF

    log "SUCCESS" "Alert rules configured successfully"
}

# =================================================================
# ALERTMANAGER CONFIGURATION
# =================================================================

setup_alertmanager_config() {
    log "INFO" "Setting up AlertManager configuration..."
    
    local alertmanager_dir="$MONITORING_CONFIG_DIR/alertmanager"
    mkdir -p "$alertmanager_dir/templates"
    
    # Create AlertManager configuration
    cat > "$alertmanager_dir/alertmanager.yml" << EOF
# ReAgent Sydney - AlertManager Configuration
# Enterprise-grade alert routing and notification

global:
  smtp_smarthost: '${SMTP_HOST}:${SMTP_PORT}'
  smtp_from: 'reagent-alerts@reagent.com'
  smtp_auth_username: '${SMTP_USER}'
  smtp_auth_password: '${SMTP_PASSWORD}'
  smtp_require_tls: true

# Alert routing configuration
route:
  group_by: ['alertname', 'service', 'severity']
  group_wait: 10s
  group_interval: 10s
  repeat_interval: 12h
  receiver: 'default'
  routes:
    # Critical alerts - immediate notification
    - match:
        severity: critical
      receiver: 'critical-alerts'
      group_wait: 10s
      repeat_interval: 5m
    
    # Database alerts - specialized handling
    - match:
        service: database
      receiver: 'database-team'
      group_interval: 5m
    
    # Business logic alerts - data team
    - match:
        team: data
      receiver: 'data-team'
      group_interval: 15m
    
    # External API alerts - integrations team
    - match:
        team: integrations
      receiver: 'integrations-team'
      group_interval: 10m

# Notification receivers
receivers:
  - name: 'default'
    email_configs:
      - to: 'ops-team@reagent.com'
        subject: 'ReAgent Alert: {{ .GroupLabels.alertname }}'
        body: |
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Labels: {{ range .Labels.SortedPairs }}{{ .Name }}={{ .Value }} {{ end }}
          {{ end }}

  - name: 'critical-alerts'
    email_configs:
      - to: 'ops-team@reagent.com,platform-team@reagent.com'
        subject: '[CRITICAL] ReAgent Alert: {{ .GroupLabels.alertname }}'
        body: |
          🚨 CRITICAL ALERT 🚨
          
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Severity: {{ .Labels.severity }}
          Service: {{ .Labels.service }}
          Started: {{ .StartsAt }}
          {{ if .Labels.runbook_url }}
          Runbook: {{ .Labels.runbook_url }}
          {{ end }}
          {{ end }}
EOF

    # Add Slack webhook configuration if provided
    if [[ -n "$SLACK_WEBHOOK_URL" ]]; then
        cat >> "$alertmanager_dir/alertmanager.yml" << EOF
    slack_configs:
      - api_url: '${SLACK_WEBHOOK_URL}'
        channel: '#reagent-alerts'
        title: 'ReAgent Critical Alert'
        text: |
          {{ range .Alerts }}
          {{ .Annotations.summary }}
          {{ .Annotations.description }}
          {{ end }}
EOF
    fi

    # Add PagerDuty configuration if provided
    if [[ -n "$PAGERDUTY_SERVICE_KEY" ]]; then
        cat >> "$alertmanager_dir/alertmanager.yml" << EOF
    pagerduty_configs:
      - service_key: '${PAGERDUTY_SERVICE_KEY}'
        description: |
          {{ range .Alerts }}
          {{ .Annotations.summary }}
          {{ end }}
EOF
    fi

    # Continue with other receivers
    cat >> "$alertmanager_dir/alertmanager.yml" << 'EOF'

  - name: 'database-team'
    email_configs:
      - to: 'database-team@reagent.com'
        subject: 'ReAgent Database Alert: {{ .GroupLabels.alertname }}'
        body: |
          Database Alert Details:
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          Instance: {{ .Labels.instance }}
          {{ end }}

  - name: 'data-team'
    email_configs:
      - to: 'data-team@reagent.com'
        subject: 'ReAgent Data Pipeline Alert: {{ .GroupLabels.alertname }}'
        body: |
          Data Pipeline Alert:
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          {{ end }}

  - name: 'integrations-team'
    email_configs:
      - to: 'integrations-team@reagent.com'
        subject: 'ReAgent External API Alert: {{ .GroupLabels.alertname }}'
        body: |
          External API Integration Alert:
          {{ range .Alerts }}
          Alert: {{ .Annotations.summary }}
          Description: {{ .Annotations.description }}
          API: {{ .Labels.api }}
          {{ end }}

# Inhibition rules - prevent redundant alerts
inhibit_rules:
  - source_match:
      severity: 'critical'
    target_match:
      severity: 'warning'
    equal: ['alertname', 'service', 'instance']
EOF

    log "SUCCESS" "AlertManager configuration created successfully"
}

# =================================================================
# GRAFANA CONFIGURATION
# =================================================================

setup_grafana_config() {
    log "INFO" "Setting up Grafana configuration..."
    
    local grafana_dir="$MONITORING_CONFIG_DIR/grafana"
    local provisioning_dir="$grafana_dir/provisioning"
    local dashboards_dir="$grafana_dir/dashboards"
    
    mkdir -p "$provisioning_dir/datasources" "$provisioning_dir/dashboards" "$provisioning_dir/notifiers"
    mkdir -p "$dashboards_dir/infrastructure" "$dashboards_dir/application" "$dashboards_dir/business" "$dashboards_dir/realestate"
    
    # Create datasource configuration
    cat > "$provisioning_dir/datasources/prometheus.yml" << 'EOF'
# ReAgent Sydney - Grafana Datasource Configuration

apiVersion: 1

datasources:
  - name: Prometheus
    type: prometheus
    access: proxy
    url: http://prometheus:9090
    isDefault: true
    editable: false
    jsonData:
      timeInterval: "15s"
      queryTimeout: "300s"
      httpMethod: "POST"
    version: 1

  - name: PostgreSQL
    type: postgres
    access: proxy
    url: postgres:5432
    database: reagent
    user: reagent
    secureJsonData:
      password: ${POSTGRES_PASSWORD}
    jsonData:
      sslmode: "disable"
      maxOpenConns: 5
      maxIdleConns: 2
      connMaxLifetime: 14400
    version: 1
EOF

    # Create dashboard provisioning configuration
    cat > "$provisioning_dir/dashboards/dashboard.yml" << 'EOF'
# ReAgent Sydney - Dashboard Provisioning Configuration

apiVersion: 1

providers:
  - name: 'Infrastructure Dashboards'
    orgId: 1
    folder: 'Infrastructure'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 300
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards/infrastructure

  - name: 'Application Dashboards'
    orgId: 1
    folder: 'Application'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 300
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards/application

  - name: 'Business Dashboards'
    orgId: 1
    folder: 'Business'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 300
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards/business

  - name: 'Real Estate Dashboards'
    orgId: 1
    folder: 'Real Estate'
    type: file
    disableDeletion: false
    updateIntervalSeconds: 300
    allowUiUpdates: true
    options:
      path: /var/lib/grafana/dashboards/realestate
EOF

    # Store Grafana credentials in secrets
    echo "$GRAFANA_ADMIN_PASSWORD" > "$PROJECT_ROOT/secrets/grafana_admin_password.txt"
    echo "$GRAFANA_SECRET_KEY" > "$PROJECT_ROOT/secrets/grafana_secret_key.txt"
    chmod 600 "$PROJECT_ROOT/secrets/grafana_admin_password.txt" "$PROJECT_ROOT/secrets/grafana_secret_key.txt"
    
    log "SUCCESS" "Grafana configuration created successfully"
}

# =================================================================
# EXPORTERS CONFIGURATION
# =================================================================

setup_exporters_config() {
    log "INFO" "Setting up metrics exporters configuration..."
    
    local exporters_dir="$MONITORING_CONFIG_DIR/exporters"
    mkdir -p "$exporters_dir"
    
    # PostgreSQL exporter custom queries
    cat > "$exporters_dir/postgres-queries.yaml" << 'EOF'
# ReAgent Sydney - PostgreSQL Custom Metrics Queries

# Database-specific metrics for ReAgent
reagent_database_metrics:
  query: |
    SELECT 
      schemaname,
      tablename,
      n_tup_ins as inserts,
      n_tup_upd as updates,
      n_tup_del as deletes,
      n_live_tup as live_tuples,
      n_dead_tup as dead_tuples,
      last_vacuum,
      last_autovacuum,
      last_analyze,
      last_autoanalyze
    FROM pg_stat_user_tables
    WHERE schemaname = 'public'
  metrics:
    - schemaname:
        usage: "LABEL"
        description: "Schema name"
    - tablename:
        usage: "LABEL"
        description: "Table name"
    - inserts:
        usage: "COUNTER"
        description: "Number of rows inserted"
    - updates:
        usage: "COUNTER"
        description: "Number of rows updated"
    - deletes:
        usage: "COUNTER"
        description: "Number of rows deleted"
    - live_tuples:
        usage: "GAUGE"
        description: "Number of live tuples"
    - dead_tuples:
        usage: "GAUGE"
        description: "Number of dead tuples"

# TimescaleDB hypertable metrics
timescaledb_hypertables:
  query: |
    SELECT 
      hypertable_schema,
      hypertable_name,
      num_chunks,
      compression_enabled,
      compressed_chunks,
      uncompressed_chunks
    FROM timescaledb_information.hypertables h
    LEFT JOIN (
      SELECT 
        hypertable_schema,
        hypertable_name,
        count(*) FILTER (WHERE compression_status = 'Compressed') as compressed_chunks,
        count(*) FILTER (WHERE compression_status != 'Compressed') as uncompressed_chunks
      FROM timescaledb_information.chunks
      GROUP BY hypertable_schema, hypertable_name
    ) c USING (hypertable_schema, hypertable_name)
  metrics:
    - hypertable_schema:
        usage: "LABEL"
        description: "Hypertable schema"
    - hypertable_name:
        usage: "LABEL"
        description: "Hypertable name"
    - num_chunks:
        usage: "GAUGE"
        description: "Number of chunks"
    - compression_enabled:
        usage: "GAUGE"
        description: "Whether compression is enabled"
    - compressed_chunks:
        usage: "GAUGE"
        description: "Number of compressed chunks"
    - uncompressed_chunks:
        usage: "GAUGE"
        description: "Number of uncompressed chunks"

# Property data quality metrics
property_data_quality:
  query: |
    SELECT 
      'properties' as table_name,
      COUNT(*) as total_records,
      COUNT(*) FILTER (WHERE price IS NOT NULL) as records_with_price,
      COUNT(*) FILTER (WHERE bedrooms IS NOT NULL) as records_with_bedrooms,
      COUNT(*) FILTER (WHERE bathrooms IS NOT NULL) as records_with_bathrooms,
      COUNT(*) FILTER (WHERE property_type IS NOT NULL) as records_with_type,
      COUNT(*) FILTER (WHERE address IS NOT NULL) as records_with_address,
      COUNT(*) FILTER (WHERE created_at > NOW() - INTERVAL '24 hours') as recent_records
    FROM properties
  metrics:
    - table_name:
        usage: "LABEL"
        description: "Table name"
    - total_records:
        usage: "GAUGE"
        description: "Total number of property records"
    - records_with_price:
        usage: "GAUGE"
        description: "Records with price data"
    - records_with_bedrooms:
        usage: "GAUGE"
        description: "Records with bedroom data"
    - records_with_bathrooms:
        usage: "GAUGE"
        description: "Records with bathroom data"
    - records_with_type:
        usage: "GAUGE"
        description: "Records with property type"
    - records_with_address:
        usage: "GAUGE"
        description: "Records with address data"
    - recent_records:
        usage: "GAUGE"
        description: "Records created in last 24 hours"

# Agent performance metrics
agent_performance:
  query: |
    SELECT 
      agent_name,
      status,
      COUNT(*) as task_count,
      AVG(EXTRACT(EPOCH FROM (completed_at - started_at))) as avg_duration_seconds
    FROM agent_tasks 
    WHERE started_at > NOW() - INTERVAL '1 hour'
    GROUP BY agent_name, status
  metrics:
    - agent_name:
        usage: "LABEL"
        description: "Agent name"
    - status:
        usage: "LABEL"
        description: "Task status"
    - task_count:
        usage: "GAUGE"
        description: "Number of tasks"
    - avg_duration_seconds:
        usage: "GAUGE"
        description: "Average task duration in seconds"
EOF

    log "SUCCESS" "Exporters configuration created successfully"
}

# =================================================================
# DEPLOYMENT FUNCTIONS
# =================================================================

deploy_monitoring_stack() {
    log "INFO" "Deploying monitoring stack..."
    
    cd "$PROJECT_ROOT"
    
    # Ensure monitoring networks exist
    if ! docker network ls | grep -q "reagent-monitoring"; then
        docker network create reagent-monitoring --driver bridge --subnet=172.22.0.0/16
        log "INFO" "Created monitoring network"
    fi
    
    # Deploy monitoring services
    docker-compose -f docker-compose.monitoring.yml up -d
    
    # Wait for services to be ready
    local services=("prometheus:9090" "alertmanager:9093" "grafana:3000")
    local max_wait=300
    local wait_time=0
    
    for service_info in "${services[@]}"; do
        local service_name="${service_info%%:*}"
        local port="${service_info##*:}"
        
        log "INFO" "Waiting for $service_name to be ready..."
        
        local service_ready=false
        local attempts=0
        local max_attempts=$((max_wait / 10))
        
        while [[ $attempts -lt $max_attempts ]]; do
            if curl -sf "http://localhost:$port" >/dev/null 2>&1; then
                service_ready=true
                break
            fi
            sleep 10
            ((attempts++))
        done
        
        if [[ "$service_ready" == "true" ]]; then
            log "SUCCESS" "$service_name is ready and responding"
        else
            log "ERROR" "$service_name failed to become ready within timeout"
            return 1
        fi
    done
    
    log "SUCCESS" "Monitoring stack deployed successfully"
}

# =================================================================
# DASHBOARD CREATION
# =================================================================

create_system_overview_dashboard() {
    log "INFO" "Creating system overview dashboard..."
    
    local dashboard_file="$MONITORING_CONFIG_DIR/grafana/dashboards/infrastructure/system-overview.json"
    
    # Create a basic system overview dashboard JSON
    cat > "$dashboard_file" << 'EOF'
{
  "dashboard": {
    "id": null,
    "title": "ReAgent Sydney - System Overview",
    "tags": ["reagent", "infrastructure", "overview"],
    "style": "dark",
    "timezone": "Australia/Sydney",
    "editable": true,
    "graphTooltip": 1,
    "time": {
      "from": "now-1h",
      "to": "now"
    },
    "refresh": "30s",
    "panels": [
      {
        "id": 1,
        "title": "System CPU Usage",
        "type": "stat",
        "targets": [
          {
            "expr": "100 - (avg(irate(node_cpu_seconds_total{mode=\"idle\"}[5m])) * 100)",
            "legendFormat": "CPU Usage"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 0, "y": 0}
      },
      {
        "id": 2,
        "title": "System Memory Usage",
        "type": "stat",
        "targets": [
          {
            "expr": "(1 - (node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)) * 100",
            "legendFormat": "Memory Usage"
          }
        ],
        "gridPos": {"h": 8, "w": 6, "x": 6, "y": 0}
      },
      {
        "id": 3,
        "title": "Service Health Status",
        "type": "stat",
        "targets": [
          {
            "expr": "up",
            "legendFormat": "{{job}}"
          }
        ],
        "gridPos": {"h": 8, "w": 12, "x": 12, "y": 0}
      }
    ]
  }
}
EOF
    
    log "SUCCESS" "System overview dashboard created"
}

# =================================================================
# VALIDATION FUNCTIONS
# =================================================================

validate_monitoring_deployment() {
    log "INFO" "Validating monitoring deployment..."
    
    # Check service health
    local services=(
        "prometheus:9090:/metrics"
        "alertmanager:9093:/-/healthy" 
        "grafana:3000:/api/health"
    )
    
    local validation_errors=0
    
    for service_info in "${services[@]}"; do
        local service_name="${service_info%%:*}"
        local port_path="${service_info#*:}"
        local port="${port_path%%:*}"
        local path="${port_path#*:}"
        
        local url="http://localhost:$port$path"
        
        if curl -sf "$url" >/dev/null 2>&1; then
            log "SUCCESS" "$service_name health check passed"
        else
            log "ERROR" "$service_name health check failed (URL: $url)"
            ((validation_errors++))
        fi
    done
    
    # Test Prometheus queries
    log "INFO" "Testing Prometheus query functionality..."
    local test_query="up"
    local prometheus_query_url="http://localhost:9090/api/v1/query?query=$test_query"
    
    if curl -sf "$prometheus_query_url" | jq -e '.status == "success"' >/dev/null 2>&1; then
        log "SUCCESS" "Prometheus query test passed"
    else
        log "ERROR" "Prometheus query test failed"
        ((validation_errors++))
    fi
    
    # Test AlertManager configuration
    log "INFO" "Testing AlertManager configuration..."
    local alertmanager_config_url="http://localhost:9093/api/v1/status/config"
    
    if curl -sf "$alertmanager_config_url" >/dev/null 2>&1; then
        log "SUCCESS" "AlertManager configuration test passed"
    else
        log "ERROR" "AlertManager configuration test failed"
        ((validation_errors++))
    fi
    
    if [[ $validation_errors -eq 0 ]]; then
        log "SUCCESS" "All monitoring validation checks passed"
        return 0
    else
        log "ERROR" "Monitoring validation failed with $validation_errors errors"
        return 1
    fi
}

# =================================================================
# MAIN EXECUTION FLOW
# =================================================================

main() {
    local start_time=$(date +%s)
    
    log "INFO" "Starting ReAgent Sydney monitoring setup..."
    log "INFO" "Environment: $ENVIRONMENT"
    log "INFO" "Project root: $PROJECT_ROOT"
    log "INFO" "Monitoring config directory: $MONITORING_CONFIG_DIR"
    
    # Create log directory
    mkdir -p "$(dirname "$SETUP_LOG")"
    
    # Execute setup phases
    if validate_prerequisites; then
        if setup_prometheus_config && setup_alert_rules; then
            if setup_alertmanager_config; then
                if setup_grafana_config && setup_exporters_config; then
                    if deploy_monitoring_stack; then
                        if create_system_overview_dashboard; then
                            if validate_monitoring_deployment; then
                                local end_time=$(date +%s)
                                local duration=$((end_time - start_time))
                                
                                log "SUCCESS" "🎉 ReAgent Sydney monitoring setup completed successfully!"
                                log "SUCCESS" "Total setup time: ${duration} seconds"
                                log "SUCCESS" "Grafana dashboard: http://localhost:3001 (admin/$(cat $PROJECT_ROOT/secrets/grafana_admin_password.txt))"
                                log "SUCCESS" "Prometheus metrics: http://localhost:9090"
                                log "SUCCESS" "AlertManager: http://localhost:9093"
                                log "SUCCESS" "Setup log: $SETUP_LOG"
                                
                                echo -e "\n${GREEN}=== MONITORING ACCESS POINTS ===${NC}"
                                echo "- Grafana: http://localhost:3001"
                                echo "- Prometheus: http://localhost:9090"
                                echo "- AlertManager: http://localhost:9093"
                                
                                echo -e "\n${BLUE}=== NEXT STEPS ===${NC}"
                                echo "1. Access Grafana and import additional dashboards"
                                echo "2. Configure notification channels in AlertManager"
                                echo "3. Set up SSL certificates for external access"
                                echo "4. Configure backup for monitoring data"
                                echo "5. Test alert rules by triggering test alerts"
                                
                                exit 0
                            fi
                        fi
                    fi
                fi
            fi
        fi
    fi
    
    log "ERROR" "Monitoring setup failed at some stage"
    exit 1
}

# =================================================================
# SCRIPT EXECUTION
# =================================================================

# Help function
show_help() {
    cat << EOF
ReAgent Sydney Monitoring Setup Script

Usage: $0 [OPTIONS]

Options:
    -h, --help              Show this help message
    -e, --environment ENV   Set environment (default: production)
    --smtp-host HOST        SMTP server hostname
    --smtp-port PORT        SMTP server port (default: 587)
    --smtp-user USER        SMTP username
    --smtp-password PASS    SMTP password
    --slack-webhook URL     Slack webhook URL for notifications
    --pagerduty-key KEY     PagerDuty service key
    --grafana-password PASS Custom Grafana admin password

Examples:
    $0                                          # Basic monitoring setup
    $0 --smtp-host smtp.gmail.com              # Setup with email notifications
    $0 --slack-webhook https://hooks.slack.com # Setup with Slack notifications

EOF
}

# Parse command line arguments
while [[ $# -gt 0 ]]; do
    case $1 in
        -h|--help)
            show_help
            exit 0
            ;;
        -e|--environment)
            ENVIRONMENT="$2"
            shift 2
            ;;
        --smtp-host)
            SMTP_HOST="$2"
            shift 2
            ;;
        --smtp-port)
            SMTP_PORT="$2"
            shift 2
            ;;
        --smtp-user)
            SMTP_USER="$2"
            shift 2
            ;;
        --smtp-password)
            SMTP_PASSWORD="$2"
            shift 2
            ;;
        --slack-webhook)
            SLACK_WEBHOOK_URL="$2"
            shift 2
            ;;
        --pagerduty-key)
            PAGERDUTY_SERVICE_KEY="$2"
            shift 2
            ;;
        --grafana-password)
            GRAFANA_ADMIN_PASSWORD="$2"
            shift 2
            ;;
        *)
            error_exit "Unknown option: $1. Use --help for usage information."
            ;;
    esac
done

# Execute main setup
main "$@"