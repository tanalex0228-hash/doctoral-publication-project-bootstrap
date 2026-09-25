#!/usr/bin/env sh
# Create a matched PostgreSQL logical dump and private-evidence archive.
set -eu
umask 077

require_environment() {
    variable_name=$1
    eval "variable_value=\${$variable_name:-}"
    if [ -z "$variable_value" ]; then
        echo "Missing required environment variable: $variable_name" >&2
        exit 2
    fi
}

for variable_name in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT BACKUP_DIR PRIVATE_MEDIA_ROOT; do
    require_environment "$variable_name"
done

if [ ! -d "$PRIVATE_MEDIA_ROOT" ]; then
    echo "PRIVATE_MEDIA_ROOT is not a directory: $PRIVATE_MEDIA_ROOT" >&2
    exit 2
fi

backup_id=${BACKUP_ID:-$(date -u +%Y%m%dT%H%M%SZ)}
mkdir -p "$BACKUP_DIR"
database_dump="$BACKUP_DIR/${backup_id}.postgres.dump"
private_archive="$BACKUP_DIR/${backup_id}.private-media.tar.gz"
manifest="$BACKUP_DIR/${backup_id}.manifest.txt"

export PGPASSWORD="$POSTGRES_PASSWORD"
pg_dump \
    --host="$POSTGRES_HOST" --port="$POSTGRES_PORT" --username="$POSTGRES_USER" \
    --format=custom --no-owner --no-privileges --file="$database_dump" "$POSTGRES_DB"
tar -C "$PRIVATE_MEDIA_ROOT" -czf "$private_archive" .

checksum() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1"
    else
        shasum -a 256 "$1"
    fi
}

{
    printf 'backup_id=%s\n' "$backup_id"
    printf 'database=%s\n' "$POSTGRES_DB"
    printf 'created_at_utc=%s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
    checksum "$database_dump"
    checksum "$private_archive"
} > "$manifest"

echo "Backup created: $database_dump"
echo "Private evidence archive created: $private_archive"
echo "Manifest created: $manifest"
