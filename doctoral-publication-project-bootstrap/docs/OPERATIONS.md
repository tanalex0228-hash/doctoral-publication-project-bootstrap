# Operations Guide

## Daily administrative work

### Create identities and profiles

1. An authorized platform administrator creates the login account in Django Admin and assigns the required project role (`student`, `advisor`, `staff`, or `admin`). Django `is_staff` alone does not grant business access.
2. Create the matching Doctoral Student Profile or Professor record with the correct institutional identifier and active status.
3. Create an active StudentAdvisor relationship, including the correct primary/co-advisor role. An inactive relationship does not grant advisor access.
4. Confirm the user lands on the expected dashboard after login.

### Maintain taxonomy

Use Django Admin to create, rename, order, activate, or deactivate Publication Types, Publication Indexes, and Research Fields. Do not create taxonomy rows for workflow states, visibility scopes, or review actions; those are controlled behavior, not administrative classifications.

### Review and publish publications

1. Staff open Review Queue and inspect submitted metadata, authors, advisor relationships, and the permission-checked evidence download.
2. Approve or return through the review action. Do not edit `workflow_status` directly in Admin, forms, or the database.
3. For approved records, configure publishing state and visibility independently. Approval does not make a record public.
4. Use Statistics and CSV only as approved-only operational evidence; they are not a graduation-decision engine.
5. Archive only the current approved record when appropriate. Archive preserves valid formal-history/statistics status while removing it from active/public surfaces.
6. Use the explicit revoke-approval action only for a governance correction. It requires a reason and confirmation, removes formal eligibility, and preserves ReviewDecision, transition, and audit evidence.
7. An approved record is corrected by creating a pending revision; do not move the current official record back to an editable state.

## Health and basic troubleshooting

```bash
curl -fsS https://your-host/healthz
```

`{"status":"ok"}` means Django can open a PostgreSQL connection. `503` means the application cannot reach PostgreSQL; check database health, network/DNS, credentials in the secret store, and container logs. Do not paste credentials into tickets or logs.

For a failed web release, check Nginx error/access logs and Gunicorn/Django standard output. Check disk capacity for PostgreSQL, private storage, static storage, and the backup destination. Keep `AuditLog` for business/governance evidence; runtime logs are separate operational diagnostics.

## Scheduled maintenance

- Run the backup procedure in [BACKUP_RESTORE.md](BACKUP_RESTORE.md) and monitor its manifest/checksums.
- Perform and record a restore drill every quarter or half-year.
- Review Django/Python/PostgreSQL dependency support at least annually; test upgrades and migrations in staging first.
- Review active accounts, advisor relationships, taxonomy deactivations, and reverse-proxy TLS configuration after organizational changes.

## Escalation boundaries

Do not repair production records with direct SQL unless an approved incident procedure requires it. Do not alter publication workflow, ownership, evidence storage keys, checksums, or audit history outside the service layer. Preserve evidence and logs before attempting recovery.
