#!/usr/bin/env bash
set -euo pipefail

: "${BACKUP_SCHEDULE:=0 2 * * *}"   # default: daily 02:00
: "${WORKDIR:=/work}"

mkdir -p "$WORKDIR"

# Build a cron file for supercronic
CRONFILE="$WORKDIR/crontab"
echo "${BACKUP_SCHEDULE} /app/backup.sh >> ${WORKDIR}/backup.log 2>&1" > "$CRONFILE"
echo "Starting scheduler with: ${BACKUP_SCHEDULE}"
exec /usr/local/bin/supercronic "$CRONFILE"
