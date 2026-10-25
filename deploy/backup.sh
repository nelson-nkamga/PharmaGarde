#!/bin/sh
# Sauvegarde quotidienne de la base SQLite (cron : 0 2 * * * /opt/pharmagarde/deploy/backup.sh)
set -eu
DB="${DATABASE_PATH:-/var/lib/pharmagarde/pharmagarde.db}"
DEST="${BACKUP_DIR:-/var/backups/pharmagarde}"
mkdir -p "$DEST"
sqlite3 "$DB" ".backup '$DEST/pharmagarde-$(date +%F).db'"
find "$DEST" -name 'pharmagarde-*.db' -mtime +14 -delete       # conserve 14 jours
