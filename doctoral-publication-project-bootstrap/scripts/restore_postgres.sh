#!/usr/bin/env sh
# Restore only into an explicitly named disposable database and empty private directory.
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

database_dump=${1:?Usage: restore_postgres.sh DATABASE_DUMP PRIVATE_MEDIA_ARCHIVE}
private_archive=${2:?Usage: restore_postgres.sh DATABASE_DUMP PRIVATE_MEDIA_ARCHIVE}

for variable_name in POSTGRES_DB POSTGRES_USER POSTGRES_PASSWORD POSTGRES_HOST POSTGRES_PORT RESTORE_DB_NAME RESTORE_PRIVATE_MEDIA_ROOT; do
    require_environment "$variable_name"
done

if [ "${ALLOW_RESTORE_OVERWRITE:-}" != "yes" ]; then
    echo "Set ALLOW_RESTORE_OVERWRITE=yes after confirming the disposable target." >&2
    exit 2
fi
case "$RESTORE_DB_NAME" in
    test_*|restore_*) ;;
    *)
        echo "RESTORE_DB_NAME must begin with test_ or restore_." >&2
        exit 2
        ;;
esac
if [ "$RESTORE_DB_NAME" = "$POSTGRES_DB" ]; then
    echo "Restore target must never equal POSTGRES_DB." >&2
    exit 2
fi
if [ ! -f "$database_dump" ] || [ ! -f "$private_archive" ]; then
    echo "Both backup files must exist before restore." >&2
    exit 2
fi

mkdir -p "$RESTORE_PRIVATE_MEDIA_ROOT"
if find "$RESTORE_PRIVATE_MEDIA_ROOT" -mindepth 1 -print -quit | grep -q .; then
    echo "RESTORE_PRIVATE_MEDIA_ROOT must be empty; this script does not delete files." >&2
    exit 2
fi

export PGPASSWORD="$POSTGRES_PASSWORD"
dropdb --if-exists --host="$POSTGRES_HOST" --port="$POSTGRES_PORT" --username="$POSTGRES_USER" "$RESTORE_DB_NAME"
createdb --host="$POSTGRES_HOST" --port="$POSTGRES_PORT" --username="$POSTGRES_USER" "$RESTORE_DB_NAME"
pg_restore \
    --host="$POSTGRES_HOST" --port="$POSTGRES_PORT" --username="$POSTGRES_USER" \
    --dbname="$RESTORE_DB_NAME" --no-owner --no-privileges --exit-on-error "$database_dump"
tar -C "$RESTORE_PRIVATE_MEDIA_ROOT" -xzf "$private_archive"

echo "Restore completed in disposable database: $RESTORE_DB_NAME"
echo "Restore completed in empty private directory: $RESTORE_PRIVATE_MEDIA_ROOT"
