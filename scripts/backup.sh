#!/usr/bin/env bash
set -euo pipefail

APP_DIR="${APP_DIR:-/opt/abconstruction/Construction-Management}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"

mkdir -p "$BACKUP_DIR"

if [ -f "$APP_DIR/instance/construction.db" ]; then
  cp "$APP_DIR/instance/construction.db" "$BACKUP_DIR/construction_$STAMP.db"
fi

if [ -d "$APP_DIR/static/uploaded_files" ]; then
  tar -czf "$BACKUP_DIR/uploaded_files_$STAMP.tar.gz" -C "$APP_DIR/static" uploaded_files
fi

find "$BACKUP_DIR" -type f -mtime +30 -delete

echo "Backup completed: $BACKUP_DIR"
