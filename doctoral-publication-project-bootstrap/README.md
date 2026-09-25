# Doctoral Publication Management System

Django 5.2 / PostgreSQL system for Fu Jen Catholic University Graduate Institute of Business Administration doctoral publication records, private evidence, review, visibility, and approved-only statistics.

## Local development

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Replace all example secrets and adjust the local PostgreSQL connection.
set -a; . ./.env; set +a
docker compose up -d db
.venv/bin/python manage.py migrate
.venv/bin/python manage.py test
```

PostgreSQL is mandatory for development, test, staging, and production. Django fails fast when database credentials or `DJANGO_SECRET_KEY` are missing; there is no SQLite fallback. The Compose database maps to host port `55432`; the Compose web service uses `db:5432`.

`PRIVATE_MEDIA_ROOT` is deliberately private: it has no `MEDIA_URL`, and Nginx never mounts it. The example uses host-relative `private_media` and `staticfiles`; Compose overrides them with its managed container volumes. Static assets are served by Nginx only under `/static/`.

## Environment inventory

Copy `.env.example`; do not commit `.env` or secrets. Required values are `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, and all `POSTGRES_*` connection values. `POSTGRES_TEST_DB` is an isolated, disposable test database name.

For production set `DJANGO_ENV=production`, `DJANGO_DEBUG=0`, HTTPS redirect/cookies to `1`, and configure the real hosts and CSRF origins. HSTS begins at `0` until HTTPS, all subdomains, and rollback procedures are confirmed; see [Deployment](docs/DEPLOYMENT.md).

## Release operations

- [Deployment](docs/DEPLOYMENT.md)
- [Backup and restore](docs/BACKUP_RESTORE.md)
- [Operations guide](docs/OPERATIONS.md)
- [UAT checklist](docs/UAT_CHECKLIST.md)

The source of truth remains [AGENTS.md](AGENTS.md), `docs/Database_Field_Matrix.xlsx`, and the linked Notion project.
