#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
APP_DIR="${APP_DIR:-$(cd "$SCRIPT_DIR/.." && pwd)}"
BACKUP_DIR="${BACKUP_DIR:-$APP_DIR/backups}"
STAMP="$(date +%Y%m%d_%H%M%S)"
BACKUP_KEEP="${BACKUP_KEEP:-5}"
UPLOAD_DIR="$APP_DIR/static/uploaded_files"
UPLOAD_MANIFEST="$BACKUP_DIR/uploaded_files.sha256"
NEW_UPLOAD_MANIFEST="$BACKUP_DIR/uploaded_files_$STAMP.sha256.tmp"

mkdir -p "$BACKUP_DIR"

prune_backups() {
  local pattern="$1"
  local count
  local oldest

  count="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$pattern" | wc -l | tr -d ' ')"
  while [ "$count" -gt "$BACKUP_KEEP" ]; do
    oldest="$(find "$BACKUP_DIR" -maxdepth 1 -type f -name "$pattern" | sort | head -n 1)"
    rm -f "$oldest"
    count=$((count - 1))
  done
}

if [ -f "$APP_DIR/instance/construction.db" ]; then
  cp "$APP_DIR/instance/construction.db" "$BACKUP_DIR/construction_$STAMP.db"
fi

if [ -d "$UPLOAD_DIR" ]; then
  (
    cd "$APP_DIR/static"
    find uploaded_files -type f -print0 \
      | sort -z \
      | while IFS= read -r -d '' file; do
          sha256sum "$file"
        done
  ) > "$NEW_UPLOAD_MANIFEST"

  if [ ! -s "$NEW_UPLOAD_MANIFEST" ] && [ ! -f "$UPLOAD_MANIFEST" ]; then
    mv "$NEW_UPLOAD_MANIFEST" "$UPLOAD_MANIFEST"
    echo "No uploaded files found: archive skipped."
  elif [ ! -f "$UPLOAD_MANIFEST" ] || ! cmp -s "$NEW_UPLOAD_MANIFEST" "$UPLOAD_MANIFEST"; then
    tar -czf "$BACKUP_DIR/uploaded_files_$STAMP.tar.gz" -C "$APP_DIR/static" uploaded_files
    mv "$NEW_UPLOAD_MANIFEST" "$UPLOAD_MANIFEST"
    echo "Uploaded files changed: archive created."
  else
    rm -f "$NEW_UPLOAD_MANIFEST"
    echo "Uploaded files unchanged: archive skipped."
  fi
fi

prune_backups "construction_*.db"
prune_backups "uploaded_files_*.tar.gz"

echo "Backup completed: $BACKUP_DIR"
