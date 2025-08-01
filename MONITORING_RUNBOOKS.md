# ReAgent Sydney - Production Monitoring Runbooks

*Last Updated: 2025-07-29*

## Overview

This document provides comprehensive runbooks for monitoring and incident response for the ReAgent Sydney production environment. It covers escalation procedures, troubleshooting guides, and operational procedures for maintaining 99.9% availability.

## Table of Contents

1. [Escalation Procedures](#escalation-procedures)
2. [System Health Monitoring](#system-health-monitoring)
3. [Database Incidents](#database-incidents)
4. [Application Performance Issues](#application-performance-issues)
5. [Agent Execution Problems](#agent-execution-problems)
6. [External API Failures](#external-api-failures)
7. [Infrastructure Alerts](#infrastructure-alerts)
8. [Business Metrics Anomalies](#business-metrics-anomalies)
9. [Disaster Recovery](#disaster-recovery)
10. [Monitoring System Maintenance](#monitoring-system-maintenance)

---

## Escalation Procedures

### Alert Severity Levels

| Severity | Description | Response Time | Escalation |
|----------|-------------|---------------|------------|
| **Critical** | System down, data loss, security breach | 5 minutes | Immediate phone + PagerDuty |
| **High** | Major functionality impaired | 15 minutes | Slack + Email |
| **Medium** | Performance degradation | 30 minutes | Slack notification |
| **Low** | Minor issues, warnings | 2 hours | Daily summary email |

### On-Call Rotation

```
Primary On-Call: DevOps Engineer
Secondary On-Call: Senior Developer  
Escalation: Engineering Manager
Final Escalation: CTO

Business Hours: 9 AM - 6 PM AEST
After Hours: Automated escalation after 30 minutes
```

### Contact Information

```
Emergency Hotline: +61-XXX-XXX-XXX
Slack Channels:
  - #reagent-critical (Critical alerts)
  - #reagent-alerts (All alerts)
  - #reagent-ops (Operations)
  - #reagent-dev (Development)

Email Lists:
  - ops-team@your-domain.com
  - dev-team@your-domain.com
  - dba-team@your-domain.com
```

---

## System Health Monitoring

### Overall System Health Check

**Alert:** System Health Degraded
**Prometheus Query:** `health_check_overall_status != 1`

#### Investigation Steps

1. **Check Grafana Dashboard:**
   ```
   URL: http://localhost:3001/d/reagent-overview
   Look for: Red components, high response times
   ```

2. **Verify Core Services:**
   ```bash
   # Check Docker containers
   docker ps --filter "name=reagent" --format "table {{.Names}}\t{{.Status}}"
   
   # Check service health endpoints
   curl -f http://localhost:8001/health  # API
   curl -f http://localhost:9090/-/healthy  # Prometheus
   curl -f http://localhost:3001/api/health  # Grafana
   ```

3. **Check System Resources:**
   ```bash
   # CPU and Memory
   htop
   
   # Disk space
   df -h
   
   # Network connectivity
   netstat -tuln | grep -E "(8001|5432|6379|8080)"
   ```

#### Resolution Actions

| Issue | Action |
|-------|--------|
| High CPU | Scale horizontally, identify resource-heavy processes |
| High Memory | Restart memory-leaking services, increase swap |
| Disk Full | Clean logs, expand storage, archive old data |
| Network Issues | Check firewall, restart networking, verify DNS |

---

## Database Incidents

### PostgreSQL Connection Issues

**Alert:** PostgreSQL Down / Too Many Connections
**Prometheus Query:** `pg_up == 0` or `pg_stat_database_numbackends / pg_settings_max_connections > 0.8`

#### Investigation Steps

1. **Check Database Status:**
   ```bash
   # Connect to database
   docker exec -it reagent-postgres psql -U reagent -d reagent
   
   # Check active connections
   SELECT count(*), state FROM pg_stat_activity GROUP BY state;
   
   # Check slow queries
   SELECT query, state, query_start 
   FROM pg_stat_activity 
   WHERE state != 'idle' 
   ORDER BY query_start;
   ```

2. **Check Database Logs:**
   ```bash
   docker logs reagent-postgres --tail=100
   ```

3. **Verify Replica Status:**
   ```bash
   # Check replication lag
   docker exec -it reagent-postgres-replica psql -U reagent -c "
   SELECT EXTRACT(EPOCH FROM (now() - pg_last_xact_replay_timestamp())) as lag_seconds;"
   ```

#### Resolution Actions

1. **Connection Pool Exhaustion:**
   ```bash
   # Kill idle connections
   docker exec -it reagent-postgres psql -U reagent -c "
   SELECT pg_terminate_backend(pid) 
   FROM pg_stat_activity 
   WHERE state = 'idle' AND query_start < now() - interval '1 hour';"
   
   # Restart connection pool
   docker restart reagent-api reagent-agents
   ```

2. **Database Corruption:**
   ```bash
   # Check database integrity
   docker exec -it reagent-postgres psql -U reagent -c "
   SELECT datname, pg_database_size(datname) FROM pg_database;"
   
   # Run VACUUM if needed
   docker exec -it reagent-postgres psql -U reagent -c "VACUUM ANALYZE;"
   ```

3. **Replica Recovery:**
   ```bash
   # Restart replica
   docker restart reagent-postgres-replica
   
   # Monitor replication status
   watch -n 5 'docker exec reagent-postgres psql -U reagent -c "SELECT * FROM pg_stat_replication;"'
   ```

### Redis Cache Issues

**Alert:** Redis Down / High Memory Usage
**Prometheus Query:** `redis_up == 0` or `redis_memory_used_bytes / redis_memory_max_bytes > 0.9`

#### Investigation Steps

1. **Check Redis Status:**
   ```bash
   # Connect to Redis
   docker exec -it reagent-redis redis-cli
   
   # Get info
   INFO memory
   INFO stats
   
   # Check key statistics
   DBSIZE
   ```

2. **Monitor Memory Usage:**
   ```bash
   # Check memory usage
   docker exec -it reagent-redis redis-cli INFO memory | grep used_memory_human
   
   # Check expiration policy
   docker exec -it reagent-redis redis-cli CONFIG GET maxmemory-policy
   ```

#### Resolution Actions

1. **Memory Cleanup:**
   ```bash
   # Flush expired keys
   docker exec -it reagent-redis redis-cli FLUSHDB
   
   # Adjust memory policy
   docker exec -it reagent-redis redis-cli CONFIG SET maxmemory-policy allkeys-lru
   ```

2. **Performance Optimization:**
   ```bash
   # Enable memory optimization
   docker exec -it reagent-redis redis-cli CONFIG SET save ""
   docker exec -it reagent-redis redis-cli CONFIG SET rdbcompression yes
   ```

---

## Application Performance Issues

### High API Response Times

**Alert:** API High Response Time
**Prometheus Query:** `histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 5`

#### Investigation Steps

1. **Check API Metrics:**
   ```bash
   # Get current response times
   curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))"
   
   # Check error rates
   curl -s "http://localhost:9090/api/v1/query?query=rate(http_requests_total{status=~\"5..\"}[5m])"
   ```

2. **Check Application Logs:**
   ```bash
   # API logs
   docker logs reagent-api --tail=50 | grep -E "(ERROR|WARN|slow)"
   
   # Agent logs
   docker logs reagent-agents --tail=50 | grep -E "(timeout|error)"
   ```

3. **Database Performance:**
   ```bash
   # Check slow queries
   docker exec -it reagent-postgres psql -U reagent -c "
   SELECT query, mean_time, calls 
   FROM pg_stat_statements 
   ORDER BY mean_time DESC 
   LIMIT 10;"
   ```

#### Resolution Actions

| Cause | Solution |
|-------|----------|
| Database bottleneck | Optimize queries, add indexes, scale read replicas |
| Memory exhaustion | Restart services, increase memory limits |
| External API timeouts | Implement circuit breakers, adjust timeouts |
| High concurrent load | Scale horizontally, implement rate limiting |

### Agent Execution Failures

**Alert:** Agent Execution Failures
**Prometheus Query:** `increase(agent_executions_failed_total[10m]) > 5`

#### Investigation Steps

1. **Check Agent Status:**
   ```bash
   # Check agent containers
   docker ps --filter "name=reagent-agents"
   
   # Check agent logs
   docker logs reagent-agents --tail=100 | grep -A 5 -B 5 "FAILED"
   ```

2. **Check Agent Metrics:**
   ```bash
   # Get failure rates by agent
   curl -s "http://localhost:9090/api/v1/query?query=rate(agent_executions_failed_total[5m])"
   
   # Check execution times
   curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95, rate(agent_execution_duration_seconds_bucket[5m]))"
   ```

#### Resolution Actions

1. **Agent Recovery:**
   ```bash
   # Restart specific agent
   docker exec reagent-agents python -c "
   from src.agents.orchestrator import restart_agent
   restart_agent('listing_watcher')
   "
   
   # Full agent restart
   docker restart reagent-agents
   ```

2. **Data Pipeline Issues:**
   ```bash
   # Check data freshness
   curl -s "http://localhost:9090/api/v1/query?query=time() - last_successful_scrape_timestamp"
   
   # Trigger manual sync
   docker exec reagent-agents python -m src.agents.listing_watcher.agent --sync
   ```

---

## External API Failures

### Domain/REA API Issues

**Alert:** External API Failures
**Prometheus Query:** `increase(external_api_requests_failed_total[10m]) > 20`

#### Investigation Steps

1. **Check API Status:**
   ```bash
   # Test Domain API
   curl -H "Authorization: Bearer $DOMAIN_API_KEY" \
        "https://api.domain.com.au/v1/listings/search"
   
   # Test REA API
   curl -H "Authorization: Bearer $REA_API_KEY" \
        "https://api.realestate.com.au/listings"
   ```

2. **Check Rate Limits:**
   ```bash
   # Check quota usage
   curl -s "http://localhost:9090/api/v1/query?query=api_quota_utilization"
   
   # Check rate limit hits
   curl -s "http://localhost:9090/api/v1/query?query=increase(api_rate_limit_exceeded_total[1h])"
   ```

#### Resolution Actions

1. **Rate Limit Management:**
   ```bash
   # Adjust scraping frequency
   docker exec reagent-agents python -c "
   from src.agents.listing_watcher.config import update_scrape_interval
   update_scrape_interval(3600)  # 1 hour
   "
   ```

2. **Failover Procedures:**
   ```bash
   # Switch to backup data source
   docker exec reagent-agents python -c "
   from src.agents.listing_watcher.agent import enable_backup_source
   enable_backup_source('corelogic')
   "
   ```

---

## Infrastructure Alerts

### High System Resource Usage

**Alert:** High CPU/Memory/Disk Usage
**Prometheus Query:** `node_cpu_usage > 80` or `node_memory_usage > 85` or `node_disk_usage > 90`

#### Investigation Steps

1. **Resource Analysis:**
   ```bash
   # Top processes
   htop
   
   # Memory usage
   free -h
   
   # Disk usage
   df -h
   du -sh /var/lib/docker/
   ```

2. **Container Resource Usage:**
   ```bash
   # Docker stats
   docker stats --no-stream
   
   # Container resource limits
   docker inspect reagent-api | grep -A 10 "Memory"
   ```

#### Resolution Actions

1. **Immediate Relief:**
   ```bash
   # Clean Docker resources
   docker system prune -f
   
   # Clean logs
   journalctl --vacuum-time=7d
   find /var/log -type f -name "*.log" -mtime +7 -delete
   ```

2. **Scale Resources:**
   ```bash
   # Horizontal scaling
   docker-compose -f docker-compose.prod.yml up -d --scale api=3
   
   # Vertical scaling (update docker-compose)
   # Increase memory/CPU limits and restart
   ```

---

## Business Metrics Anomalies

### Property Data Staleness

**Alert:** Property Data Stale
**Prometheus Query:** `time() - last_successful_scrape_timestamp > 7200`

#### Investigation Steps

1. **Check Data Pipeline:**
   ```bash
   # Check scraping status
   docker exec reagent-agents python -c "
   from src.agents.listing_watcher.agent import get_last_sync_status
   print(get_last_sync_status())
   "
   ```

2. **Verify External APIs:**
   ```bash
   # Test API connectivity
   docker exec reagent-agents python -m src.services.external_apis.domain_client --test
   ```

#### Resolution Actions

1. **Force Data Refresh:**
   ```bash
   # Trigger manual sync
   docker exec reagent-agents python -c "
   from src.agents.listing_watcher.agent import force_full_sync
   force_full_sync()
   "
   ```

### Low Buyer Matching Rate

**Alert:** Low Buyer Matching Rate
**Prometheus Query:** `rate(buyer_matches_created_total[1h]) < 5`

#### Investigation Steps

1. **Check Matching Engine:**
   ```bash
   # Check buyer profiles
   docker exec reagent-postgres psql -U reagent -c "
   SELECT COUNT(*) as active_buyers FROM buyer_profiles WHERE is_active = true;
   "
   
   # Check recent properties
   docker exec reagent-postgres psql -U reagent -c "
   SELECT COUNT(*) as recent_properties FROM properties 
   WHERE created_at > NOW() - INTERVAL '24 hours';
   "
   ```

2. **Check Vector Search:**
   ```bash
   # Test Weaviate connectivity
   curl -f http://localhost:8080/v1/meta
   
   # Check vector search performance
   curl -s "http://localhost:9090/api/v1/query?query=histogram_quantile(0.95, rate(weaviate_query_duration_seconds_bucket[5m]))"
   ```

---

## Disaster Recovery

### Complete System Failure

#### Recovery Steps

1. **Assess Damage:**
   ```bash
   # Check system status
   systemctl status docker
   docker ps -a
   
   # Check data integrity
   ls -la /home/emergence-admin/Desktop/ReAgent/data/
   ```

2. **Restore from Backup:**
   ```bash
   # Restore database
   cd /home/emergence-admin/Desktop/ReAgent
   ./scripts/disaster-recovery.sh --restore-database
   
   # Restore Redis
   ./scripts/disaster-recovery.sh --restore-redis
   
   # Restore Weaviate
   ./scripts/disaster-recovery.sh --restore-weaviate
   ```

3. **Restart Services:**
   ```bash
   # Full system restart
   docker-compose -f docker-compose.prod.yml down
   docker-compose -f docker-compose.prod.yml up -d
   
   # Verify monitoring
   docker-compose -f docker-compose.monitoring.yml up -d
   ```

### Data Corruption

#### Recovery Steps

1. **Isolate Corrupted Components:**
   ```bash
   # Stop affected services
   docker stop reagent-postgres reagent-api reagent-agents
   ```

2. **Restore Clean Data:**
   ```bash
   # Restore from latest clean backup
   ./scripts/backup-postgres.sh --restore --timestamp=20250729_120000
   ```

3. **Validate Data Integrity:**
   ```bash
   # Run integrity checks
   python test_comprehensive_validation.py
   ```

---

## Monitoring System Maintenance

### Weekly Maintenance Tasks

1. **Review Alert Accuracy:**
   ```bash
   # Check false positive rate
   curl -s "http://localhost:9093/api/v1/alerts" | jq '.data | length'
   
   # Review resolved alerts
   grep "resolved" /var/log/alertmanager/alertmanager.log | tail -20
   ```

2. **Clean Old Metrics:**
   ```bash
   # Prometheus retention cleanup (automatic)
   docker exec reagent-prometheus promtool tsdb analyze /prometheus
   
   # Grafana cleanup
   docker exec reagent-grafana grafana-cli admin reset-admin-password newpassword
   ```

3. **Update Dashboards:**
   ```bash
   # Backup current dashboards
   curl -H "Authorization: Bearer $GRAFANA_TOKEN" \
        "http://localhost:3001/api/dashboards/home" \
        > dashboards_backup.json
   ```

### Monthly Maintenance Tasks

1. **Performance Review:**
   - Analyze monthly performance trends
   - Update alert thresholds based on historical data
   - Review and optimize slow database queries

2. **Capacity Planning:**
   - Review resource usage trends
   - Plan infrastructure scaling
   - Update resource limits

3. **Security Updates:**
   - Update monitoring container images
   - Review access logs
   - Update SSL certificates

---

## Emergency Contacts

```
24/7 Emergency Line: +61-XXX-XXX-XXX

Primary On-Call:
  Name: [Engineering Manager]
  Phone: +61-XXX-XXX-XXX
  Email: engineering-manager@your-domain.com

Secondary On-Call:
  Name: [Senior DevOps Engineer]  
  Phone: +61-XXX-XXX-XXX
  Email: devops@your-domain.com

Escalation:
  Name: [CTO]
  Phone: +61-XXX-XXX-XXX
  Email: cto@your-domain.com

External Support:
  Hosting Provider: [Provider Name]
  Support Line: +61-XXX-XXX-XXX
  Account ID: [Account ID]
```

---

## Important URLs

- **Grafana Dashboards:** http://localhost:3001
- **Prometheus:** http://localhost:9090  
- **AlertManager:** http://localhost:9093
- **ReAgent API:** http://localhost:8001
- **System Documentation:** https://github.com/your-org/reagent-sydney

---

*This runbook should be reviewed and updated monthly. Last review: 2025-07-29*