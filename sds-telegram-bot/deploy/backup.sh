#!/usr/bin/env bash
# Nightly PostgreSQL backup with 14-day retention.
# cron (as root):  15 3 * * *  /opt/sds-telegram-bot/deploy/backup.sh >> /var/log/sds-bot-backup.log 2>&1
set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/sds-bot}"
KEEP_DAYS="${KEEP_DAYS:-14}"
STAMP="$(date +%Y%m%d-%H%M%S)"
mkdir -p "$BACKUP_DIR"
chmod 700 "$BACKUP_DIR"

if [ "${USE_DOCKER:-1}" = "1" ]; then
  # Docker Compose deployment
  cd /opt/sds-telegram-bot
  docker compose exec -T db pg_dump -U sds_bot -d sds_bot --format=custom > "$BACKUP_DIR/sds_bot-$STAMP.dump"
else
  # Native PostgreSQL deployment
  sudo -u postgres pg_dump -d sds_bot --format=custom > "$BACKUP_DIR/sds_bot-$STAMP.dump"
fi

chmod 600 "$BACKUP_DIR/sds_bot-$STAMP.dump"
find "$BACKUP_DIR" -name 'sds_bot-*.dump' -mtime +"$KEEP_DAYS" -delete
echo "$(date -Is) backup ok: sds_bot-$STAMP.dump"
