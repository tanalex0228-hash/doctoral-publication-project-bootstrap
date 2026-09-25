# Deployment

## Production topology

`Client → TLS terminator / Nginx → Gunicorn / Django → PostgreSQL`

`compose.yaml` supplies the local-compatible Nginx, Gunicorn, PostgreSQL, private-media volume, and static-files volume topology. Nginx mounts only the static volume. It has no `/media/` route and does not mount the private evidence volume; every evidence download remains a Django permission-checked route.

TLS may terminate at the listed Nginx instance or an institutional reverse proxy. Before enabling production mode, ensure the proxy sets `X-Forwarded-Proto` only after terminating TLS.

## Production environment

Keep the environment file in the deployment secret store, not Git. At minimum set:

```dotenv
DJANGO_ENV=production
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<long-random-secret>
DJANGO_ALLOWED_HOSTS=public.example.edu
DJANGO_CSRF_TRUSTED_ORIGINS=https://public.example.edu
DJANGO_SECURE_SSL_REDIRECT=1
DJANGO_TRUST_X_FORWARDED_PROTO=1
DJANGO_SESSION_COOKIE_SECURE=1
DJANGO_CSRF_COOKIE_SECURE=1
POSTGRES_DB=doctoral_publications
POSTGRES_TEST_DB=test_doctoral_publications
POSTGRES_USER=doctoral_app
POSTGRES_PASSWORD=<secret>
POSTGRES_HOST=<postgres-host>
POSTGRES_PORT=5432
PRIVATE_MEDIA_ROOT=/var/lib/doctoral-private-media
STATIC_ROOT=/var/lib/doctoral-static
```

Set `DJANGO_HSTS_SECONDS=0` initially. After HTTPS works for every configured host and a rollback plan exists, begin with a short value such as `3600`. Enable `DJANGO_HSTS_INCLUDE_SUBDOMAINS=1` only when every subdomain is HTTPS-ready. Preload requires both include-subdomains and at least one year; do not enable it without an explicit institutional decision.

## Release procedure

1. Build the immutable application image and deploy the reviewed `.env` through the secret manager.
2. Start PostgreSQL and verify its healthcheck. The app database role must own only the application database/schema permissions needed by Django; it must not be a PostgreSQL superuser.
3. Run migrations once as an explicit release action, not as an implicit web-start action:

   ```bash
   docker compose run --rm web python manage.py migrate
   ```

4. Start `web` and `nginx`. Web startup runs `collectstatic --noinput`; Nginx serves the shared static volume.
5. Verify `GET /healthz`, login, a permission-checked document download, and the UAT smoke items.
6. Retain the previous application image and database backup until post-release acceptance completes.

## Database and runtime checks

PostgreSQL credentials come only from environment variables. Django uses a short configurable connection timeout and `/healthz` returns `503` without connection details when PostgreSQL is unavailable. Django's test runner uses `POSTGRES_TEST_DB`; it must never point to the production database.

Confirm database encoding/timezone during provisioning:

```bash
psql --host="$POSTGRES_HOST" --port="$POSTGRES_PORT" \
  --username="$POSTGRES_USER" --dbname="$POSTGRES_DB" \
  -c 'SHOW server_encoding; SHOW TimeZone;'
```

The expected encoding is UTF8. Django stores timestamps using timezone-aware values and is configured for `Asia/Taipei`.

## Logs and security

Gunicorn and Django write runtime logs to standard output/error for collection by the container platform. Nginx access/error logs are collected separately. Runtime logs and `AuditLog` are different records: do not write passwords, session values, database credentials, access tokens, or evidence bytes to either.

Run before release:

```bash
python manage.py check
python manage.py check --deploy
python manage.py makemigrations --check --dry-run
python manage.py test
```

For the deployment-facing `check --deploy`, use the real production HTTPS variables. A development environment with HSTS disabled will intentionally report HSTS/HTTPS recommendations.
