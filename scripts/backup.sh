#!/bin/bash
# ============================================
# IVS - Automated Backup Script
# Run via cron: 0 0 * * * /path/to/backup.sh
# ============================================
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
IVS_DIR="$(dirname "$SCRIPT_DIR")"
BACKUP_DIR="${IVS_BACKUP_DIR:-$IVS_DIR/backups}"
DATE=$(date +%Y%m%d_%H%M%S)
BACKUP_PATH="$BACKUP_DIR/$DATE"
RETENTION_DAYS=30

echo "[$(date)] Starting IVS backup..."

mkdir -p "$BACKUP_PATH"

# Backup database
if [ -f "$IVS_DIR/data/ivs.db" ]; then
    cp "$IVS_DIR/data/ivs.db" "$BACKUP_PATH/ivs.db"
    echo "[+] Database backed up"
fi

# Backup deployed app sources
if [ -d "$IVS_DIR/deployed_apps" ]; then
    tar -czf "$BACKUP_PATH/deployed_apps.tar.gz" -C "$IVS_DIR" deployed_apps/
    echo "[+] App sources backed up"
fi

# Backup configuration
tar -czf "$BACKUP_PATH/config.tar.gz" -C "$IVS_DIR" \
    .env docker-compose.yml caddy/ coredns/ 2>/dev/null || true
echo "[+] Configuration backed up"

# Backup Gitea data
if docker inspect ivs-gitea &>/dev/null; then
    docker exec ivs-gitea gitea dump -c /etc/gitea/app.ini -f /tmp/gitea-dump.zip 2>/dev/null || true
    docker cp ivs-gitea:/tmp/gitea-dump.zip "$BACKUP_PATH/gitea-dump.zip" 2>/dev/null || true
    echo "[+] Gitea data backed up"
fi

# Create combined archive
cd "$BACKUP_DIR"
tar -czf "ivs-backup-$DATE.tar.gz" "$DATE/"
rm -rf "$BACKUP_PATH"
echo "[+] Combined archive: ivs-backup-$DATE.tar.gz"

# Cleanup old backups
find "$BACKUP_DIR" -name "ivs-backup-*.tar.gz" -mtime +$RETENTION_DAYS -delete
echo "[+] Old backups cleaned (retention: ${RETENTION_DAYS} days)"

# Calculate size
BACKUP_SIZE=$(du -sh "$BACKUP_DIR/ivs-backup-$DATE.tar.gz" | cut -f1)
echo "[$(date)] Backup complete: $BACKUP_SIZE"
