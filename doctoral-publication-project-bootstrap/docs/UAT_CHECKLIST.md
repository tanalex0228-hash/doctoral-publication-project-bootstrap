# User Acceptance Checklist

Use a non-production UAT environment and representative accounts. For each item, mark **Pass** or **Fail**, add the tester/date, and write an observation in **Notes**. Do not upload real sensitive evidence unless the environment is approved for it.

## Student

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Log in as a student and open My Publications. | Only the student's own draft, submitted, returned, and approved records are shown. |  |  |
| Create a publication, choose taxonomy values, add authors, and save as draft. | The new publication is saved; administrative classifications come from selectable lists. |  |  |
| Add, reorder, edit, and remove an external co-author. | Author order is retained and no account is required for the external author. |  |  |
| Upload a PDF/JPG/PNG to an existing draft publication. | Upload succeeds only after the parent publication exists; the file is listed but has no public URL. |  |  |
| Submit a complete publication. | It moves to submitted and core fields are no longer editable. |  |  |
| Return a submitted publication, edit it, and resubmit. | Returned is editable by its owner; the return reason and prior review history remain visible. |  |  |
| Create a revision from an approved publication. | A separate pending revision is created; the current official version remains unchanged. |  |  |
| Have staff return the revision. | The prior official version remains visible and counted; only the revision becomes editable. |  |  |
| Have staff approve the revision. | The revision becomes the sole current official version; the former version is retained as history. |  |  |
| Open another student's copied publication URL. | The record is not disclosed or editable. |  |  |

## Advisor

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Log in as an advisor and open the advisor dashboard. | Only active advisees are listed. |  |  |
| Open an active advisee and a publication allowed to the advisor. | Metadata and permitted private evidence downloads are available. |  |  |
| Open a still-active StudentAdvisor relationship with a past `end_date`. | Advisor access remains available; `end_date` is historical metadata only. |  |  |
| Open an inactive advising relationship or an archived Professor account. | Advisor access and private-document access are denied. |  |  |
| Change an advisee or publication URL to an unrelated student. | The unrelated record is not disclosed. |  |  |
| Attempt to approve or return a publication. | Advisor has no review decision action. |  |  |

## Secretary / Staff

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Open Review Queue, search/filter/sort, and move to page two where applicable. | Only submitted records appear and query options remain after pagination. |  |  |
| Review a submitted record, download evidence, then approve it. | Approval is recorded; the record becomes eligible for approved-only statistics but is not automatically public. |  |  |
| Return a submitted record with and without a reason. | The student can revise and resubmit; review history remains visible. |  |  |
| Set an approved record's publishing state and visibility. | Publishing and approval remain independent; visibility controls the allowed audience. |  |  |
| Export filtered statistics as CSV. | Only approved records matching filters appear; Chinese opens correctly in Excel and formula-looking text is safe. |  |  |
| Archive an approved record. | It disappears from active review/public portals, remains a formal historical statistic and remains in Archive with audit/history. |  |  |
| Revoke approval with a reason and confirmation. | It leaves formal statistics and all publication-facing surfaces; review/transition/audit history remains. |  |  |
| Create and submit a revision for an approved record. | The prior official version remains visible/countable until the revision is approved. |  |  |
| Approve a submitted revision. | The new revision becomes the current official record; the old version does not remain in active/public/statistics results. |  |  |
| Export portable metadata and private-file manifest in the UAT environment. | Export contains governed metadata, review/audit history and document manifest; private files remain outside public media routes. |  |  |
| Check A approved, B archived, C revoked, D submitted, E returned, F replaced revision in dashboard, student detail, filters and CSV. | A/B appear; C/D/E do not; F includes only its current official version. |  |  |

## Admin

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Use Django Admin to add/edit/deactivate/reorder taxonomy values. | Publication Type, Publication Index, and Research Field changes are available to forms without code changes. |  |  |
| Verify a user with only Django `is_staff` and no project role. | The account does not receive staff review, statistics, or archive business access. |  |  |
| Check `/healthz` and review release logs. | Health is OK when PostgreSQL is available; logs expose no passwords, tokens, or document content. |  |  |
| Review legacy `department` mapping before production migration. | Confirm it historically meant current + graduated students + faculty/staff; otherwise record an exception before deployment. |  |  |

## Public visitor

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Browse the public publication portal and apply search/filter/sort. | Only approved, published, public metadata is displayed. |  |  |
| Open a copied UUID for a private, department, unpublished, or archived record. | It is not disclosed. |  |  |
| Look for supporting-document links on public pages. | Public pages do not expose private evidence files or direct media URLs. |  |  |

## Visibility matrix

Create one **published, current official** publication for each scope. Execute this table with dedicated UAT identities; record the actual result in `docs/UAT_RESULTS.md`.

| Scope | Anonymous | Current student | Graduated student | Unrelated student | Owner | Faculty / Professor | Authorized advisor | Staff / Admin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| public | Allow | Allow | Allow | Allow | Allow | Allow | Allow | Allow |
| department_all | Deny | Allow | Allow | Allow | Allow | Allow | Allow | Allow |
| department_current | Deny | Allow | Deny | Allow | Allow | Allow | Allow | Allow |
| owner_faculty | Deny | Deny | Deny | Deny | Allow | Allow | Allow as an active Professor identity | Allow |
| owner_advisor | Deny | Deny | Deny | Deny | Allow | Deny unless authorized advisor | Allow | Allow |
| staff_only | Deny | Deny | Deny | Deny | Deny unless staff/admin | Deny unless staff/admin | Deny unless staff/admin | Allow |

For each allowed metadata result, separately verify private-document access. Evidence downloads remain deliberately stricter than metadata: owner, authorized advisor, and staff/admin only.

## Release controls

- Perform backup → disposable restore database/private directory → health check → authenticated smoke test before production release.
- Use only the dedicated staging/UAT database and synthetic documents for this checklist.
- Record product defects, UX issues, data issues, documentation issues, and new requests in `UAT_RESULTS.md`. New requests require PM decision before implementation.
