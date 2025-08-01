# ReAgent Sydney - Operational Runbooks

## Table of Contents

1. [Daily Operations](#daily-operations)
2. [Emergency Response](#emergency-response)
3. [System Monitoring](#system-monitoring)
4. [Backup and Recovery](#backup-and-recovery)
5. [Performance Optimization](#performance-optimization)
6. [Security Operations](#security-operations)
7. [Database Management](#database-management)
8. [Agent Management](#agent-management)

---

## Daily Operations

### Morning Health Check (5 minutes)

**Frequency:** Daily at 9:00 AM AEST  
**Responsibility:** Operations Team

#### Checklist

```bash
# 1. Check service status
docker-compose -f docker-compose.prod.yml ps

# 2. Verify all services are healthy
curl -f http://localhost:8000/health
curl -f http://localhost:8080/v1/.well-known/ready  # Weaviate
docker exec reagent-redis-master redis-cli ping

# 3. Check overnight alerts
# - Review Slack #reagent-alerts channel
# - Check Grafana dashboards for anomalies
# - Review error logs from past 24 hours

# 4. Verify backup completion
ls -la ./backups/*/reagent_$(date -d "yesterday" +%Y%m%d)_*

# 5. Check disk space
df -h

# 6. Review key business metrics
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM reagent_performance_summary;"
```

#### Expected Results
- All services show "Up" status
- Health checks return 200 OK
- Backup files exist from previous night
- Disk usage below 80%
- No critical alerts in monitoring

#### Escalation
If any check fails, proceed to [Emergency Response](#emergency-response) procedures.

---

## Emergency Response

### Service Outage Response

**Maximum Response Time:** 15 minutes  
**Target Resolution Time:** 60 minutes

#### Severity Levels

**P1 - Critical (Complete service outage)**
- API returning 5xx errors or not responding
- Database unavailable
- Multiple services down

**P2 - High (Degraded service)**
- Single service failure with workaround available
- Performance degradation affecting users
- Non-critical component failure

**P3 - Medium (Minor impact)**
- Monitoring alerts but service functional
- Non-user-facing issues
- Scheduled maintenance required

#### Response Procedures

##### P1 - Critical Incident Response

```bash
# 1. Immediate Assessment (2 minutes)
echo "=== INCIDENT START: $(date) ===" >> incident.log

# Check service status
docker-compose -f docker-compose.prod.yml ps >> incident.log

# Check recent logs for errors
docker-compose -f docker-compose.prod.yml logs --tail=50 >> incident.log

# Check system resources
echo "System Resources:" >> incident.log
free -h >> incident.log
df -h >> incident.log

# 2. Quick Recovery Attempt (5 minutes)
# Try restarting failed services
docker-compose -f docker-compose.prod.yml restart [failed-service]

# If API is down, restart entire stack
docker-compose -f docker-compose.prod.yml down
docker-compose -f docker-compose.prod.yml up -d

# 3. Verify Recovery (3 minutes)
sleep 30
curl -f http://localhost:8000/health

# If recovery fails, proceed to disaster recovery
if [ $? -ne 0 ]; then
    echo "Quick recovery failed, initiating disaster recovery" >> incident.log
    ./scripts/disaster-recovery.sh latest
fi

# 4. Post-Incident (5 minutes)
# Document incident
echo "=== INCIDENT END: $(date) ===" >> incident.log
# Notify stakeholders
# Schedule post-mortem if P1 lasted > 30 minutes
```

##### Database Emergency Recovery

```bash
# 1. Assess database status
docker exec reagent-postgres pg_isready -U reagent -d reagent

# 2. Check for corruption
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT datname, pg_database_size(datname) FROM pg_database WHERE datname='reagent';"

# 3. If corruption detected, restore from backup
./scripts/disaster-recovery.sh postgresql latest

# 4. Verify data integrity post-recovery
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT COUNT(*) FROM properties WHERE created_at > NOW() - INTERVAL '24 hours';"
```

### Performance Emergency Response

**Trigger:** Response time > 10 seconds or CPU > 90% for 5+ minutes

```bash
# 1. Identify bottleneck
docker stats --no-stream

# 2. Check slow queries
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM slow_queries LIMIT 10;"

# 3. Check blocked processes
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '30 seconds';"

# 4. Emergency optimization
# Kill long-running queries if safe
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '5 minutes';"

# Restart services if needed
docker-compose -f docker-compose.prod.yml restart api agents
```

---

## System Monitoring

### Key Metrics to Monitor

#### Application Metrics
- API response time (95th percentile < 5 seconds)
- Error rate (< 1%)
- Request rate (baseline established during load testing)
- Agent execution success rate (> 95%)

#### Infrastructure Metrics
- CPU usage (< 80% sustained)
- Memory usage (< 85%)
- Disk usage (< 80%)
- Network I/O
- Container health status

#### Business Metrics
- Property listings processed per hour
- Buyer matches created per day
- Data freshness (properties updated within 2 hours)
- External API response times

### Monitoring Queries

```sql
-- Daily performance summary
SELECT 
    DATE(created_at) as date,
    COUNT(*) as new_properties,
    COUNT(CASE WHEN status = 'active' THEN 1 END) as active_listings,
    AVG(price_guide) as avg_price
FROM properties 
WHERE created_at > NOW() - INTERVAL '7 days'
GROUP BY DATE(created_at)
ORDER BY date DESC;

-- Agent performance check
SELECT 
    agent_name,
    COUNT(*) as executions_last_hour,
    AVG(duration_seconds) as avg_duration,
    COUNT(CASE WHEN status = 'Failed' THEN 1 END) as failures
FROM agent_executions 
WHERE started_at > NOW() - INTERVAL '1 hour'
GROUP BY agent_name;

-- Database performance
SELECT 
    query,
    calls,
    mean_time,
    rows,
    100.0 * shared_blks_hit / nullif(shared_blks_hit + shared_blks_read, 0) AS hit_percent
FROM pg_stat_statements 
WHERE calls > 100 AND mean_time > 50
ORDER BY mean_time DESC 
LIMIT 10;
```

### Alert Response Procedures

#### High CPU Alert
1. Check `docker stats` for resource usage
2. Identify high-CPU containers
3. Review recent code deployments
4. Scale horizontally if needed
5. Optimize queries if database-related

#### High Memory Alert
1. Check for memory leaks in application logs
2. Review PostgreSQL shared_buffers setting
3. Check Redis memory usage
4. Restart services if memory leak detected

#### Disk Space Alert
1. Clean old log files: `find ./logs -name "*.log" -mtime +7 -delete`
2. Rotate backup files: `find ./backups -name "*" -mtime +30 -delete`
3. Check database size growth
4. Add storage if trend indicates need

#### Database Connection Limit
1. Check connection count: `SELECT count(*) FROM pg_stat_activity;`
2. Identify long-running connections
3. Adjust connection pool settings
4. Restart application if needed

---

## Backup and Recovery

### Backup Verification Procedures

**Frequency:** Daily after backup completion

```bash
# 1. Verify backup files exist
ls -la ./backups/*/reagent_$(date +%Y%m%d)_*

# 2. Check backup file sizes (should be consistent)
du -h ./backups/*/reagent_$(date +%Y%m%d)_*

# 3. Test backup integrity
# PostgreSQL backup test
backup_file=$(ls ./backups/postgres/reagent_$(date +%Y%m%d)_*.sql.gz | head -1)
if [ -f "$backup_file" ]; then
    gunzip -t "$backup_file" && echo "PostgreSQL backup integrity: OK"
fi

# Redis backup test
backup_file=$(ls ./backups/redis/dump_$(date +%Y%m%d)_*.rdb.gz | head -1)
if [ -f "$backup_file" ]; then
    gunzip -t "$backup_file" && echo "Redis backup integrity: OK"
fi

# 4. Log backup verification results
echo "$(date): Backup verification completed" >> ./logs/backup-verification.log
```

### Monthly Disaster Recovery Test

**Frequency:** First Sunday of each month  
**Duration:** 2-4 hours  
**Requirements:** Staging environment or maintenance window

```bash
# 1. Create test environment
mkdir -p /tmp/reagent-dr-test
cd /tmp/reagent-dr-test

# 2. Copy production backups
cp -r /path/to/production/backups ./

# 3. Run disaster recovery
/path/to/production/scripts/disaster-recovery.sh full latest

# 4. Verify recovery
# - Check all services start successfully
# - Verify data integrity
# - Test key application functions
# - Document any issues found

# 5. Cleanup test environment
cd /
rm -rf /tmp/reagent-dr-test

# 6. Update disaster recovery procedures based on findings
```

### Backup Retention Policy

- **Daily backups:** Retained for 30 days
- **Weekly backups:** Retained for 12 weeks
- **Monthly backups:** Retained for 12 months
- **Yearly backups:** Retained for 7 years (compliance requirement)

---

## Performance Optimization

### Weekly Performance Review

**Frequency:** Every Monday at 10:00 AM  
**Duration:** 30 minutes

#### Performance Analysis Checklist

```bash
# 1. Review slow query log
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM slow_queries WHERE calls > 10 ORDER BY mean_time DESC LIMIT 20;"

# 2. Check index usage
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM unused_indexes;"

# 3. Analyze table bloat
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM table_bloat WHERE dead_tuple_percent > 10;"

# 4. Review cache hit ratios
docker exec reagent-redis-master redis-cli info stats | grep keyspace

# 5. Check API response times from monitoring
# Review Grafana dashboards for trends
```

#### Optimization Actions

**High CPU Usage:**
```bash
# Optimize PostgreSQL configuration
./scripts/performance-tuning.sh

# Add database indexes for frequent queries
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_properties_search ON properties (suburb, property_type, status) WHERE status = 'active';"
```

**High Memory Usage:**
```bash
# Tune PostgreSQL memory settings
nano config/postgres/postgresql.conf
# Adjust shared_buffers, work_mem based on usage patterns

# Optimize Redis memory
nano config/redis/redis.conf
# Adjust maxmemory, maxmemory-policy settings
```

**Slow Queries:**
```bash
# Identify and optimize problematic queries
# Add appropriate indexes
# Consider query rewriting
# Update table statistics: ANALYZE;
```

### Load Testing Procedures

**Frequency:** Before major releases and monthly  

```bash
# 1. Prepare test environment
cd testing/load

# 2. Update test scenarios based on production traffic patterns
nano api-load-test.js

# 3. Run load test
artillery run api-load-test.js --output report.json

# 4. Generate HTML report
artillery report report.json

# 5. Analyze results and identify performance bottlenecks
# 6. Implement optimizations
# 7. Re-test to verify improvements
```

---

## Security Operations

### Daily Security Checks

```bash
# 1. Check for failed login attempts
sudo journalctl -u ssh --since "24 hours ago" | grep "Failed password"

# 2. Review Docker security
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
    -v /usr/local/bin/docker:/usr/local/bin/docker \
    aquasec/trivy image reagent-api:latest

# 3. Check SSL certificate expiry
openssl x509 -in ssl/fullchain.pem -text -noout | grep "Not After"

# 4. Review access logs for anomalies
tail -100 logs/nginx/access.log | grep -E "(40[0-9]|50[0-9])"

# 5. Verify secret file permissions
ls -la secrets/
# Should show 600 permissions (rw-------)
```

### Weekly Security Tasks

```bash
# 1. Update system packages
sudo apt update && sudo apt upgrade -y

# 2. Update Docker images
docker-compose -f docker-compose.prod.yml pull
docker-compose -f docker-compose.prod.yml up -d

# 3. Review firewall rules
sudo ufw status verbose

# 4. Check for CVE alerts for used software
# 5. Review user access and remove unnecessary accounts
# 6. Backup and rotate log files
```

### Security Incident Response

**Trigger:** Unusual activity detected, security alerts, suspected breach

```bash
# 1. Immediate containment
# Block suspicious IP addresses
sudo ufw deny from [suspicious-ip]

# Isolate affected containers if needed
docker pause [container-name]

# 2. Evidence collection
# Copy relevant logs
cp -r logs/ /secure/incident-$(date +%Y%m%d)/
cp /var/log/auth.log /secure/incident-$(date +%Y%m%d)/

# 3. Analysis
# Review access patterns
# Check for data exfiltration
# Identify attack vectors

# 4. Recovery
# Patch vulnerabilities
# Update passwords/keys if compromised
# Restore from clean backups if needed

# 5. Post-incident
# Document incident
# Update security procedures
# Notify stakeholders if required
```

---

## Database Management

### Daily Database Maintenance

```bash
# 1. Check database size and growth
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT pg_size_pretty(pg_database_size('reagent'));"

# 2. Monitor connection usage
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT count(*), state FROM pg_stat_activity GROUP BY state;"

# 3. Check for blocked queries
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM pg_stat_activity WHERE state = 'active' AND query_start < NOW() - INTERVAL '2 minutes';"

# 4. Review autovacuum activity
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT schemaname, tablename, last_vacuum, last_autovacuum, last_analyze, last_autoanalyze FROM pg_stat_user_tables WHERE schemaname = 'public';"
```

### Weekly Database Tasks

```bash
# 1. Update table statistics
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "ANALYZE;"

# 2. Reindex fragmented indexes (if needed)
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "REINDEX INDEX CONCURRENTLY idx_properties_suburb_postcode;"

# 3. Clean up old data (based on retention policy)
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "DELETE FROM agent_logs WHERE timestamp < NOW() - INTERVAL '90 days';"

# 4. Check TimescaleDB chunk status
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT * FROM timescaledb_information.chunks WHERE hypertable_name IN ('property_price_history', 'agent_executions');"
```

### Database Schema Changes

**Process for production schema changes:**

1. **Preparation**
   ```bash
   # Create migration script
   docker exec reagent-api alembic revision --autogenerate -m "description"
   
   # Review generated migration
   nano alembic/versions/[revision_id]_description.py
   ```

2. **Testing**
   ```bash
   # Test on staging environment
   docker exec reagent-api alembic upgrade head
   
   # Verify application functionality
   # Run automated tests
   ```

3. **Production Deployment**
   ```bash
   # Create database backup before migration
   ./scripts/backup-full-system.sh postgresql
   
   # Apply migration during maintenance window
   docker exec reagent-api alembic upgrade head
   
   # Verify migration success
   docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
       psql -U reagent -d reagent -c "SELECT version_num FROM alembic_version;"
   ```

---

## Agent Management

### Agent Health Monitoring

```bash
# 1. Check agent execution status
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT agent_name, COUNT(*) as executions, AVG(duration_seconds) as avg_duration, COUNT(CASE WHEN status = 'Failed' THEN 1 END) as failures FROM agent_executions WHERE started_at > NOW() - INTERVAL '24 hours' GROUP BY agent_name;"

# 2. Review agent logs for errors
docker logs reagent-agents --tail=100 | grep ERROR

# 3. Check external API rate limits
# Monitor API usage to avoid hitting limits
# Review rate limiting metrics in monitoring dashboards
```

### Agent Configuration Updates

```bash
# 1. Update agent configurations
nano src/agents/[agent_name]/config.py

# 2. Restart agents to apply changes
docker-compose -f docker-compose.prod.yml restart agents

# 3. Monitor agent performance after changes
# Watch execution times and success rates
# Verify no increase in error rates
```

### Agent Performance Optimization

```bash
# 1. Identify slow agents
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT agent_name, AVG(duration_seconds) as avg_duration FROM agent_executions WHERE started_at > NOW() - INTERVAL '7 days' GROUP BY agent_name ORDER BY avg_duration DESC;"

# 2. Review agent resource usage
docker stats reagent-agents

# 3. Optimize agent configurations
# Adjust batch sizes, timeouts, concurrency levels
# Update caching strategies
# Optimize database queries in agent tools

# 4. Test changes in staging environment first
# Monitor performance improvements
# Deploy to production during low-traffic periods
```

### Emergency Agent Procedures

**Agent Completely Failed:**
```bash
# 1. Check agent container status
docker ps | grep agents

# 2. Review agent logs
docker logs reagent-agents --tail=500

# 3. Restart agent service
docker-compose -f docker-compose.prod.yml restart agents

# 4. If restart fails, check configuration
# Verify environment variables
# Check database connectivity
# Validate external API credentials
```

**Agent Producing Bad Data:**
```bash
# 1. Immediately stop agent
docker-compose -f docker-compose.prod.yml stop agents

# 2. Identify and quarantine bad data
# Mark affected records for review
# Prevent bad data from being used

# 3. Fix agent logic
# Deploy corrected code
# Test thoroughly before restart

# 4. Clean up bad data if necessary
# Run data correction scripts
# Verify data integrity
```

This operational runbook provides comprehensive procedures for maintaining ReAgent Sydney in production, ensuring reliable operation and quick resolution of issues.