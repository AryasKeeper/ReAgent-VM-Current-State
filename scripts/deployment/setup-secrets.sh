#!/bin/bash

# ReAgent Sydney - Secrets Management Setup Script
# Creates secure secrets for production deployment

set -euo pipefail

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Configuration
SECRETS_DIR="./secrets"
SSL_DIR="./ssl"
BACKUP_DIR="./backups"
ENV_FILE=".env.production"

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

generate_password() {
    local length=${1:-32}
    openssl rand -base64 $length | tr -d "=+/" | cut -c1-$length
}

generate_secret_key() {
    python3 -c "import secrets; print(secrets.token_urlsafe(50))"
}

create_directory_structure() {
    log_info "Creating directory structure..."
    
    mkdir -p "$SECRETS_DIR"
    mkdir -p "$SSL_DIR"
    mkdir -p "$BACKUP_DIR"/{postgres,redis,weaviate}
    mkdir -p "./data"/{postgres,postgres_replica,redis_master,weaviate,grafana,prometheus,alertmanager,celery_beat}
    mkdir -p "./logs"/{nginx,grafana}
    
    # Set secure permissions
    chmod 700 "$SECRETS_DIR"
    chmod 755 "$SSL_DIR"
    chmod 755 "$BACKUP_DIR"
}

generate_secrets() {
    log_info "Generating production secrets..."
    
    # Database password
    if [[ ! -f "$SECRETS_DIR/postgres_password.txt" ]]; then
        generate_password 32 > "$SECRETS_DIR/postgres_password.txt"
        log_info "Generated PostgreSQL password"
    fi
    
    # Redis password
    if [[ ! -f "$SECRETS_DIR/redis_password.txt" ]]; then
        generate_password 32 > "$SECRETS_DIR/redis_password.txt"
        log_info "Generated Redis password"
    fi
    
    # Application secret key
    if [[ ! -f "$SECRETS_DIR/secret_key.txt" ]]; then
        generate_secret_key > "$SECRETS_DIR/secret_key.txt"
        log_info "Generated application secret key"
    fi
    
    # Weaviate API key
    if [[ ! -f "$SECRETS_DIR/weaviate_api_key.txt" ]]; then
        generate_password 32 > "$SECRETS_DIR/weaviate_api_key.txt"
        log_info "Generated Weaviate API key"
    fi
    
    # Grafana secret key
    if [[ ! -f "$SECRETS_DIR/grafana_secret_key.txt" ]]; then
        generate_password 32 > "$SECRETS_DIR/grafana_secret_key.txt"
        log_info "Generated Grafana secret key"
    fi
    
    # Set secure permissions on all secret files
    chmod 600 "$SECRETS_DIR"/*.txt
}

create_placeholder_api_keys() {
    log_info "Creating placeholder API key files..."
    
    # External API keys (to be filled manually)
    local api_keys=(
        "openai_api_key.txt"
        "domain_api_key.txt"
        "rea_api_key.txt"
        "corelogic_api_key.txt"
        "nsw_lpi_api_key.txt"
    )
    
    for key_file in "${api_keys[@]}"; do
        if [[ ! -f "$SECRETS_DIR/$key_file" ]]; then
            echo "REPLACE_WITH_ACTUAL_API_KEY" > "$SECRETS_DIR/$key_file"
            chmod 600 "$SECRETS_DIR/$key_file"
            log_warn "Created placeholder for $key_file - REPLACE WITH ACTUAL KEY"
        fi
    done
}

generate_ssl_certificates() {
    log_info "Setting up SSL certificate structure..."
    
    if [[ ! -f "$SSL_DIR/dhparam.pem" ]]; then
        log_info "Generating DH parameters (this may take a while)..."
        openssl dhparam -out "$SSL_DIR/dhparam.pem" 2048
        chmod 644 "$SSL_DIR/dhparam.pem"
    fi
    
    # Create self-signed certificate for development/testing
    if [[ ! -f "$SSL_DIR/fullchain.pem" ]]; then
        log_warn "Generating self-signed certificate for testing..."
        log_warn "Replace with proper certificate from Let's Encrypt or CA for production"
        
        openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
            -keyout "$SSL_DIR/privkey.pem" \
            -out "$SSL_DIR/fullchain.pem" \
            -subj "/C=AU/ST=NSW/L=Sydney/O=ReAgent/CN=reagent.local"
        
        cp "$SSL_DIR/fullchain.pem" "$SSL_DIR/chain.pem"
        chmod 644 "$SSL_DIR"/*.pem
        chmod 600 "$SSL_DIR/privkey.pem"
    fi
}

create_production_env() {
    if [[ ! -f "$ENV_FILE" ]]; then
        log_info "Creating production environment file from template..."
        cp ".env.production.template" "$ENV_FILE"
        
        # Auto-populate generated passwords
        local postgres_pass=$(cat "$SECRETS_DIR/postgres_password.txt")
        local redis_pass=$(cat "$SECRETS_DIR/redis_password.txt")
        local weaviate_key=$(cat "$SECRETS_DIR/weaviate_api_key.txt")
        local secret_key=$(cat "$SECRETS_DIR/secret_key.txt")
        local grafana_secret=$(cat "$SECRETS_DIR/grafana_secret_key.txt")
        
        sed -i "s/super_secure_postgres_password_here/$postgres_pass/g" "$ENV_FILE"
        sed -i "s/super_secure_redis_password_here/$redis_pass/g" "$ENV_FILE"
        sed -i "s/weaviate_api_key_here/$weaviate_key/g" "$ENV_FILE"
        sed -i "s/your_very_long_random_secret_key_here/$secret_key/g" "$ENV_FILE"
        sed -i "s/secure_grafana_password_here/$grafana_secret/g" "$ENV_FILE"
        
        chmod 600 "$ENV_FILE"
        log_info "Created $ENV_FILE with auto-generated passwords"
        log_warn "Review and update API keys and domain settings in $ENV_FILE"
    fi
}

setup_file_permissions() {
    log_info "Setting up file permissions..."
    
    # Set ownership if running as root
    if [[ $EUID -eq 0 ]]; then
        chown -R 1000:1000 "./data"
        chown -R 1000:1000 "./logs"
        chown -R 1000:1000 "$BACKUP_DIR"
    fi
    
    # Set secure permissions
    chmod -R 755 "./data"
    chmod -R 755 "./logs"
    chmod -R 755 "$BACKUP_DIR"
    chmod 700 "$SECRETS_DIR"
    chmod -R 600 "$SECRETS_DIR"/*.txt
}

create_backup_scripts() {
    log_info "Creating backup scripts..."
    
    cat << 'EOF' > scripts/backup-postgres.sh
#!/bin/bash
# PostgreSQL backup script for ReAgent Sydney

set -euo pipefail

BACKUP_DIR="./backups/postgres"
DATE=$(date +%Y%m%d_%H%M%S)
POSTGRES_PASSWORD=$(cat ./secrets/postgres_password.txt)

export PGPASSWORD="$POSTGRES_PASSWORD"

# Create backup
docker exec reagent-postgres pg_dump -h localhost -U reagent -d reagent > "$BACKUP_DIR/reagent_$DATE.sql"

# Compress backup
gzip "$BACKUP_DIR/reagent_$DATE.sql"

# Clean old backups (keep 30 days)
find "$BACKUP_DIR" -name "*.sql.gz" -mtime +30 -delete

echo "Backup completed: reagent_$DATE.sql.gz"
EOF

    chmod +x scripts/backup-postgres.sh
    
    cat << 'EOF' > scripts/backup-redis.sh
#!/bin/bash  
# Redis backup script for ReAgent Sydney

set -euo pipefail

BACKUP_DIR="./backups/redis"
DATE=$(date +%Y%m%d_%H%M%S)

# Create Redis backup
docker exec reagent-redis-master redis-cli --rdb /data/dump_$DATE.rdb
docker cp reagent-redis-master:/data/dump_$DATE.rdb "$BACKUP_DIR/"

# Clean old backups
find "$BACKUP_DIR" -name "*.rdb" -mtime +7 -delete

echo "Redis backup completed: dump_$DATE.rdb"
EOF

    chmod +x scripts/backup-redis.sh
}

validate_setup() {
    log_info "Validating setup..."
    
    local errors=0
    
    # Check required secrets exist
    local required_secrets=(
        "postgres_password.txt"
        "redis_password.txt"
        "secret_key.txt"
        "weaviate_api_key.txt"
    )
    
    for secret in "${required_secrets[@]}"; do
        if [[ ! -f "$SECRETS_DIR/$secret" ]]; then
            log_error "Missing required secret: $secret"
            ((errors++))
        fi
    done
    
    # Check SSL certificates
    if [[ ! -f "$SSL_DIR/fullchain.pem" ]] || [[ ! -f "$SSL_DIR/privkey.pem" ]]; then
        log_error "Missing SSL certificates"
        ((errors++))
    fi
    
    # Check environment file
    if [[ ! -f "$ENV_FILE" ]]; then
        log_error "Missing production environment file"
        ((errors++))
    fi
    
    if [[ $errors -eq 0 ]]; then
        log_info "Setup validation passed!"
        return 0
    else
        log_error "Setup validation failed with $errors errors"
        return 1
    fi
}

print_next_steps() {
    log_info "Setup completed successfully!"
    echo
    echo "Next steps:"
    echo "1. Review and update API keys in $ENV_FILE"
    echo "2. Replace self-signed SSL certificate with proper certificate"
    echo "3. Update domain settings in $ENV_FILE and nginx configuration"
    echo "4. Run: docker-compose -f docker-compose.prod.yml up -d"
    echo "5. Set up automated backups with cron jobs"
    echo
    echo "Important files created:"
    echo "- $ENV_FILE (production environment variables)"
    echo "- $SECRETS_DIR/ (secure secrets - keep private!)"
    echo "- $SSL_DIR/ (SSL certificates)"
    echo "- scripts/backup-*.sh (backup scripts)"
}

# Main execution
main() {
    log_info "Starting ReAgent Sydney production setup..."
    
    create_directory_structure
    generate_secrets
    create_placeholder_api_keys
    generate_ssl_certificates
    create_production_env
    setup_file_permissions
    create_backup_scripts
    
    if validate_setup; then
        print_next_steps
    else
        log_error "Setup failed validation. Please check errors above."
        exit 1
    fi
}

# Run main function
main "$@"