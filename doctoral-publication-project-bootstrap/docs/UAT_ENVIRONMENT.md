# UAT / staging environment

Use a dedicated PostgreSQL database and private-media directory. Never point these variables at production data or production evidence storage.

## Local demo

1. Copy `.env.example` to a local `.env`, use a long local-only `DJANGO_SECRET_KEY`, set `DJANGO_ENV=development` and keep `DJANGO_DEBUG=0`.
2. Start the local PostgreSQL container and apply migrations:

   ```bash
   set -a; . ./.env; set +a
   docker compose up -d db
   .venv/bin/python manage.py migrate
   ```

3. Choose a non-production password outside Git and seed the deterministic UAT dataset:

   ```bash
   export UAT_SEED_PASSWORD='<choose-a-local-password>'
   .venv/bin/python manage.py seed_uat
   docker compose up -d web nginx
   ```

4. Open `http://localhost:8080/accounts/login/`. Seeded usernames are `uat-student-a`, `uat-student-b`, `uat-graduated`, `uat-advisor-a`, `uat-advisor-b`, `uat-secretary`, `uat-admin`, `uat-django-staff-only`, and `uat-multi-role`. They use the password supplied only through `UAT_SEED_PASSWORD` on first seed.

The command refuses `DJANGO_ENV=production`. It is idempotent, so it can safely be run again with the same UAT database. For a full local reset only, stop the UAT Compose stack and remove its local volumes, then migrate and seed again. Never use that reset procedure against shared staging or production.

## Shared staging

Use distinct values, for example `POSTGRES_DB=doctoral_publications_uat`, a separate `POSTGRES_TEST_DB`, and a distinct `PRIVATE_MEDIA_ROOT`. Set `DJANGO_ENV=staging`, `DJANGO_DEBUG=0`, a valid random secret, explicit UAT hosts/CSRF origins, and production-like TLS/cookie settings. Use the same `seed_uat` command only after confirming those paths and database names are UAT-only.

## Smoke and restore

Before human UAT, run `python manage.py check`, migration consistency, tests, `/healthz`, login, public portal and a permission-checked private-document download. Record only actually executed human cases in `UAT_RESULTS.md`.

Use `scripts/backup_postgres.sh` and `scripts/restore_postgres.sh` only with UAT paths and a disposable `restore_*` database. Record the drill outcome in `UAT_RESULTS.md`.
