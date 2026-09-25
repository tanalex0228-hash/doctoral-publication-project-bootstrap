# Backup and restore

This system uses PostgreSQL and private source-document storage. A recoverable backup contains both. The supported operational procedures are the repository scripts below.

## Backup

Set `POSTGRES_DB`, `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_HOST`, `POSTGRES_PORT`, `BACKUP_DIR`, and `PRIVATE_MEDIA_ROOT`, then run:

```bash
scripts/backup_postgres.sh
```

The script writes a PostgreSQL custom dump, private-media `.tar.gz`, and a SHA-256 manifest. `BACKUP_ID` may be set for a deterministic operator label; otherwise it uses a UTC timestamp.

The additional portable metadata-plus-private-evidence export is suitable for long-term transfer and inspection:

```bash
python scripts/export_portable_data.py /secure/backups/doctoral-publications-YYYY-MM-DD
```

Keep the dump and export together, encrypted at rest, access-controlled, and retained under the institution's approved retention schedule. Verify a restore regularly; this document does not claim or configure an automated schedule.

## Restore rehearsal

Set `POSTGRES_*`, `RESTORE_DB_NAME`, `RESTORE_PRIVATE_MEDIA_ROOT`, and `ALLOW_RESTORE_OVERWRITE=yes`. The restore target must be a disposable `test_*` or `restore_*` database, must never equal `POSTGRES_DB`, and the private target directory must be empty.

```bash
scripts/restore_postgres.sh /secure/backups/ID.postgres.dump /secure/backups/ID.private-media.tar.gz
```

Then point a temporary validation environment at the restored database/private directory and run `python manage.py check` plus targeted document retrieval checks. Do not publish either private directory through a media route. Compare the backup manifest checksums and the portable export's `source_documents.json` file sizes/checksums before declaring the rehearsal successful.
