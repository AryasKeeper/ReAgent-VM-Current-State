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
