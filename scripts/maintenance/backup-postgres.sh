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
