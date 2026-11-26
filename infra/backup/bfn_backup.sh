#!/bin/sh
# Daily dump of the BlackFox database; keeps the last 14.
# Installed on the server by .github/workflows/db-backup-setup.yml and run
# by cron from the compose project directory (the home directory).
set -e

KEEP=14
DIR="$HOME/db_backups"
FILE="$DIR/daily_$(date +%Y%m%d_%H%M%S).dump"
mkdir -p "$DIR"

DB_SERVICE=$(sudo docker compose ps --services | grep -xE 'db|postgres|database' | head -n 1 || true)
if [ -n "$DB_SERVICE" ]; then
  # The database runs in the compose project: dump inside its container.
  sudo docker compose exec -T "$DB_SERVICE" \
    sh -c 'pg_dump -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' > "$FILE.part"
else
  # A database outside compose: the backend's own connection settings.
  sudo docker run --rm --network host --env-file .env postgres:17 \
    sh -c 'PGPASSWORD="$POSTGRES_PASSWORD" pg_dump -h "$DB_HOST" -p "$DB_PORT" -U "$POSTGRES_USER" -Fc "$POSTGRES_DB"' \
    > "$FILE.part"
fi

# An empty or broken dump never replaces a good one.
test -s "$FILE.part"
mv "$FILE.part" "$FILE"
chmod 600 "$FILE"
echo "$(date '+%F %T') ok $(du -h "$FILE" | cut -f1) $FILE"

# Only the daily dumps rotate; the ones made before migrations stay.
ls -1t "$DIR"/daily_*.dump | tail -n +$((KEEP + 1)) | while read -r old; do
  rm -f "$old"
done
