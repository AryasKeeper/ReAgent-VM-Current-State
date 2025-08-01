# ReAgent Sydney - Production Deployment Guide

## Overview

This guide provides complete instructions for deploying ReAgent Sydney to production. The system is designed for VPS/dedicated server deployment with comprehensive monitoring, security, and backup capabilities.

## Prerequisites

### System Requirements

**Minimum Requirements:**
- 4 CPU cores
- 8GB RAM
- 100GB SSD storage
- Ubuntu 20.04+ or CentOS 8+
- Docker 20.10+
- Docker Compose 2.0+

**Recommended Requirements:**
- 8 CPU cores
- 16GB RAM
- 500GB SSD storage
- Dedicated server or high-performance VPS

### Required Software

```bash
# Install Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sudo sh get-docker.sh
sudo usermod -aG docker $USER

# Install Docker Compose
sudo curl -L "https://github.com/docker/compose/releases/latest/download/docker-compose-$(uname -s)-$(uname -m)" -o /usr/local/bin/docker-compose
sudo chmod +x /usr/local/bin/docker-compose

# Install additional tools
sudo apt update
sudo apt install -y curl wget git jq htop iotop postgresql-client redis-tools
```

### Network Requirements

- Ports 80, 443 (HTTP/HTTPS)
- Port 22 (SSH)
- All other ports should be firewalled
- Domain name with DNS pointing to server IP

## Deployment Steps

### 1. Initial Setup

```bash
# Clone repository
git clone https://github.com/your-org/ReAgent.git
cd ReAgent

# Run initial setup script
sudo ./scripts/setup-secrets.sh

# Apply system optimizations (optional but recommended)
sudo ./scripts/optimize-system.sh
```

### 2. Configuration

#### 2.1 Environment Variables

Edit `.env.production` with your specific settings:

```bash
# Copy template and edit
cp .env.production.template .env.production
nano .env.production

# Key settings to update:
EXTERNAL_IP=your.server.ip.address
ALLOWED_HOSTS=your-domain.com,www.your-domain.com
CORS_ORIGINS=https://your-domain.com

# API Keys (required)
OPENAI_API_KEY=sk-your_key_here
DOMAIN_API_KEY=your_domain_key_here
REA_API_KEY=your_rea_key_here
CORELOGIC_API_KEY=your_corelogic_key_here
NSW_LPI_API_KEY=your_nsw_lpi_key_here

# Monitoring
SMTP_HOST=smtp.your-provider.com
SMTP_USER=alerts@your-domain.com
SMTP_PASSWORD=your_smtp_password
ALERTMANAGER_WEBHOOK_URL=https://hooks.slack.com/your/webhook
```

#### 2.2 SSL Certificates

For production, replace self-signed certificates:

```bash
# Using Let's Encrypt (recommended)
sudo apt install certbot

# Get certificate
sudo certbot certonly --standalone -d your-domain.com -d www.your-domain.com

# Copy certificates to ReAgent
sudo cp /etc/letsencrypt/live/your-domain.com/fullchain.pem ./ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/privkey.pem ./ssl/
sudo cp /etc/letsencrypt/live/your-domain.com/chain.pem ./ssl/

# Set permissions
sudo chown $(whoami):$(whoami) ./ssl/*.pem
chmod 644 ./ssl/fullchain.pem ./ssl/chain.pem
chmod 600 ./ssl/privkey.pem
```

#### 2.3 Nginx Configuration

Update domain in nginx configuration:

```bash
# Edit nginx config
sed -i 's/your-domain.com/youractual-domain.com/g' config/nginx/nginx.conf
```

### 3. Performance Tuning

Run the performance tuning script:

```bash
./scripts/performance-tuning.sh
```

This will:
- Optimize database settings for your hardware
- Configure Redis for optimal caching
- Set up connection pooling
- Create monitoring queries
- Generate load testing configuration

### 4. Deploy Services

#### 4.1 Start Core Services

```bash
# Start main application stack
docker-compose -f docker-compose.prod.yml up -d

# Verify services are running
docker-compose -f docker-compose.prod.yml ps
```

#### 4.2 Start Monitoring Stack

```bash
# Start monitoring services
docker-compose -f docker-compose.monitoring.yml up -d

# Check monitoring services
docker-compose -f docker-compose.monitoring.yml ps
```

#### 4.3 Initialize Database

```bash
# Wait for PostgreSQL to be ready
sleep 30

# Run database migrations
docker exec reagent-api alembic upgrade head

# Setup TimescaleDB hypertables
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT setup_timescale_hypertables();"

# Create performance indexes
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT create_performance_indexes();"
```

### 5. Verification

#### 5.1 Health Checks

```bash
# API health
curl -f http://localhost:8000/health

# Database connectivity
docker exec reagent-postgres pg_isready -U reagent -d reagent

# Redis connectivity
docker exec reagent-redis-master redis-cli ping

# Weaviate connectivity
curl -f http://localhost:8080/v1/.well-known/ready
```

#### 5.2 Monitoring Access

- Grafana: http://your-domain.com/grafana/ (admin/your_password)
- Prometheus: http://your-domain.com/prometheus/ (internal access only)
- API Documentation: http://your-domain.com/api/docs (disable in production)

### 6. SSL/HTTPS Setup

```bash
# Test HTTPS access
curl -I https://your-domain.com/health

# Verify SSL certificate
openssl s_client -connect your-domain.com:443 -servername your-domain.com
```

## Post-Deployment Configuration

### 1. Backup Setup

#### 1.1 Automated Backups

```bash
# Add backup cron job
crontab -e

# Add this line for daily backups at 2 AM
0 2 * * * /path/to/ReAgent/scripts/backup-full-system.sh
```

#### 1.2 AWS S3 Backup (Optional)

```bash
# Install AWS CLI
sudo apt install awscli

# Configure AWS credentials
aws configure

# Test S3 backup
./scripts/backup-full-system.sh
```

### 2. Monitoring Setup

#### 2.1 Slack Notifications

1. Create Slack webhook URL
2. Update ALERTMANAGER_WEBHOOK_URL in .env.production
3. Restart AlertManager: `docker-compose -f docker-compose.monitoring.yml restart alertmanager`

#### 2.2 Email Alerts

1. Configure SMTP settings in .env.production
2. Test email alerts:
   ```bash
   # Trigger test alert
   curl -X POST http://localhost:9093/api/v1/alerts \
     -H "Content-Type: application/json" \
     -d '[{"labels":{"alertname":"TestAlert","severity":"warning"}}]'
   ```

### 3. Performance Monitoring

#### 3.1 Initial Performance Baseline

```bash
# Run performance monitoring queries
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -f monitoring/queries/performance-metrics.sql

# Check system performance
./scripts/performance-tuning.sh
```

#### 3.2 Load Testing

```bash
# Install Artillery (load testing tool)
npm install -g artillery@latest

# Run load test
cd testing/load
artillery run api-load-test.js
```

## Security Checklist

### 1. Access Control

- [ ] SSH key-based authentication only
- [ ] Firewall configured (only ports 22, 80, 443 open)
- [ ] Docker daemon secured
- [ ] Strong passwords for all services
- [ ] Regular security updates applied

### 2. Application Security

- [ ] All secrets stored in files, not environment variables
- [ ] API rate limiting enabled
- [ ] CORS properly configured
- [ ] HTTPS enforced
- [ ] Security headers configured in Nginx

### 3. Database Security

- [ ] PostgreSQL access restricted to Docker network
- [ ] Database user has minimal required permissions
- [ ] Regular security updates applied
- [ ] Backup encryption enabled

## Maintenance Tasks

### Daily Tasks

- [ ] Check service health via Grafana dashboards
- [ ] Review error logs
- [ ] Monitor disk space usage
- [ ] Verify backup completion

### Weekly Tasks

- [ ] Review performance metrics
- [ ] Check for security updates
- [ ] Analyze slow query logs
- [ ] Test disaster recovery procedures

### Monthly Tasks

- [ ] Full system backup test and restore
- [ ] Performance optimization review
- [ ] Security audit
- [ ] Update dependencies

## Troubleshooting

### Common Issues

#### Services Won't Start

```bash
# Check Docker logs
docker-compose -f docker-compose.prod.yml logs

# Check system resources
htop
df -h

# Restart services
docker-compose -f docker-compose.prod.yml restart
```

#### Database Connection Issues

```bash
# Check PostgreSQL logs
docker logs reagent-postgres

# Check connection limits
docker exec -e PGPASSWORD="$(cat secrets/postgres_password.txt)" reagent-postgres \
    psql -U reagent -d reagent -c "SELECT count(*) FROM pg_stat_activity;"

# Reset connections if needed
docker restart reagent-postgres
```

#### High Memory Usage

```bash
# Check memory usage by container
docker stats

# Optimize PostgreSQL shared_buffers if needed
nano config/postgres/postgresql.conf

# Restart PostgreSQL
docker restart reagent-postgres
```

#### SSL Certificate Issues

```bash
# Check certificate expiry
openssl x509 -in ssl/fullchain.pem -text -noout | grep "Not After"

# Renew Let's Encrypt certificate
sudo certbot renew

# Update certificates
sudo cp /etc/letsencrypt/live/your-domain.com/*.pem ./ssl/
docker restart reagent-nginx
```

### Log Locations

- Application logs: `./logs/`
- Nginx logs: `./logs/nginx/`
- System performance: `/var/log/reagent-performance.log`
- Backup logs: `./logs/backup_*.log`
- Restore logs: `./logs/restore_*.log`

## Scaling Guidelines

### Vertical Scaling (Single Server)

1. Increase server resources (CPU, RAM, storage)
2. Run performance tuning script: `./scripts/performance-tuning.sh`
3. Update PostgreSQL and Redis memory settings
4. Restart services to apply new configurations

### Horizontal Scaling (Multiple Servers)

For high-availability deployment:

1. Set up PostgreSQL primary-replica configuration
2. Configure Redis Sentinel for high availability
3. Deploy multiple API servers behind load balancer
4. Use shared storage for logs and backups
5. Implement service discovery

## Support and Maintenance

### Getting Help

- Check logs first: `./logs/` directory
- Review monitoring dashboards in Grafana
- Consult this deployment guide
- Check GitHub issues and documentation

### Emergency Contacts

- System Administrator: [admin@your-domain.com]
- Database Administrator: [dba@your-domain.com]
- DevOps Team: [devops@your-domain.com]

### Emergency Procedures

#### Service Outage

1. Check system health: `docker-compose ps`
2. Review recent logs: `docker-compose logs --tail=100`
3. Restart affected services: `docker-compose restart [service]`
4. If database issues, check disaster recovery guide
5. Notify stakeholders via configured alerting

#### Data Corruption

1. Stop all services immediately
2. Run disaster recovery script: `./scripts/disaster-recovery.sh`
3. Verify data integrity post-recovery
4. Investigate root cause
5. Update backup and monitoring procedures

This deployment guide ensures ReAgent Sydney runs reliably in production with proper monitoring, security, and maintenance procedures.