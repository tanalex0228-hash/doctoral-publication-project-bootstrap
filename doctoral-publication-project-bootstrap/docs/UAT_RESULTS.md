# Formal UAT Results

## Run metadata

| Field | Value |
| --- | --- |
| Release candidate | RC2 / Formal UAT |
| Environment | Dedicated staging/UAT PostgreSQL database only |
| Tester |  |
| Date |  |
| Application revision |  |
| PostgreSQL version |  |
| Result | Not started |

Do not use production records or real sensitive evidence. Use synthetic PDF/JPG/PNG files and dedicated accounts.

## Required UAT identities and data

| Identity / record | Required setup |
| --- | --- |
| Anonymous visitor | Not logged in |
| Current student / unrelated student | Distinct active student profiles |
| Graduated student | Student profile with `enrollment_status=graduated` |
| Owner student | Owns all scenario publications |
| Faculty / professor | Active Professor identity, not advisor unless the case states otherwise |
| Authorized advisor | Active StudentAdvisor relation, including one relation whose `end_date` is in the past |
| Denied advisor | Inactive StudentAdvisor relation or archived Professor |
| Staff / admin | Project `staff` / `admin` role; a Django `is_staff`-only account as a negative control |
| Publications | A approved, B archived after approval, C revoked after approval, D submitted, E returned, F approved original plus pending/approved revision |
| Visibility records | One published current official record for each of the six visibility scopes |

## Scenario execution log

| ID | Role | Scenario | Expected | Actual / evidence | Severity | Status | Resolution |
| --- | --- | --- | --- | --- | --- | --- | --- |
| UAT-STU-01 | Owner student | Create → authors → document → submit → returned → edit → resubmit | Workflow is understandable; no unauthorized edit or file route |  |  | Open |  |
| UAT-STU-02 | Owner student | Approved → create revision → staff returns revision | Original stays official; revision alone is editable |  |  | Open |  |
| UAT-STU-03 | Owner student | Approved → create revision → staff approves revision | New version replaces original as current official |  |  | Open |  |
| UAT-STA-01 | Staff | Review queue → detail → private document → approve / return | Actions generate traceable decisions and transitions |  |  | Open |  |
| UAT-STA-02 | Staff | Revoke approved record after confirmation | Leaves official statistics/public surfaces; history remains |  |  | Open |  |
| UAT-STA-03 | Staff | Archive approved record | Leaves active/public surfaces but stays historical official statistic |  |  | Open |  |
| UAT-STA-04 | Staff | Statistics / CSV / portable export cases A–F | A/B included; C/D/E excluded; F only current version |  |  | Open |  |
| UAT-ADV-01 | Advisor | Own advisee, past end date, inactive relation, archived professor | Past end date allowed; inactive/archived denied |  |  | Open |  |
| UAT-VIS-01 | All roles | Execute six-scope matrix in UAT checklist | Actual UI behavior matches matrix; UUIDs do not bypass access |  |  | Open |  |
| UAT-DOC-01 | Owner/advisor/staff/other | Download a private document for each allowed/denied case | Backend route authorizes every download; no public media URL |  |  | Open |  |
| UAT-OPS-01 | Operator | Backup → disposable restore → health check → authenticated smoke test | Dump, archive, manifest and restored private storage validate |  |  | Open |  |

## Issue register

| ID | Category | Role | Scenario | Expected | Actual | Severity | Screenshot / evidence | Status | Resolution / PM decision |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |

Categories: `PRODUCT DEFECT`, `UX ISSUE`, `DOCUMENTATION ISSUE`, `DATA ISSUE`, `NEW REQUEST`.

Severity: `BLOCKER`, `MAJOR`, `MINOR`, `COSMETIC`. Do not implement `NEW REQUEST` items without PM scope approval.

## Legacy department mapping review

| Check | Result |
| --- | --- |
| Is there legacy production data? |  |
| Did legacy `department` mean current + graduated students + faculty/staff? |  |
| If no legacy production data exists | Record `Not Applicable` |
| If policy/data differs | Stop release migration and obtain PM/data-owner decision; do not edit the migration casually |

## Production configuration checklist

- [ ] Real long-random `DJANGO_SECRET_KEY` is in the secret store.
- [ ] `DJANGO_ALLOWED_HOSTS` and `DJANGO_CSRF_TRUSTED_ORIGINS` match the deployed domain.
- [ ] TLS termination, secure cookies and HSTS policy are approved and verified.
- [ ] PostgreSQL credentials and private storage path are production-specific and least-privilege.
- [ ] Backup destination, retention period and offsite-copy ownership are documented.
- [ ] Disposable backup/restore drill is completed and recorded.
- [ ] Production smoke test covers login, private document authorization, public portal and `/healthz`.
