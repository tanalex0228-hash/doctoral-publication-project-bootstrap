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
| Open another student's copied publication URL. | The record is not disclosed or editable. |  |  |

## Advisor

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Log in as an advisor and open the advisor dashboard. | Only active advisees are listed. |  |  |
| Open an active advisee and a publication allowed to the advisor. | Metadata and permitted private evidence downloads are available. |  |  |
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
| Archive an approved record. | It disappears from active review/public portals, remains in Archive with audit/history, and no restore action appears. |  |  |

## Admin

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Use Django Admin to add/edit/deactivate/reorder taxonomy values. | Publication Type, Publication Index, and Research Field changes are available to forms without code changes. |  |  |
| Verify a user with only Django `is_staff` and no project role. | The account does not receive staff review, statistics, or archive business access. |  |  |
| Check `/healthz` and review release logs. | Health is OK when PostgreSQL is available; logs expose no passwords, tokens, or document content. |  |  |

## Public visitor

| Operation steps | Expected result | Pass / Fail | Notes |
| --- | --- | --- | --- |
| Browse the public publication portal and apply search/filter/sort. | Only approved, published, public metadata is displayed. |  |  |
| Open a copied UUID for a private, department, unpublished, or archived record. | It is not disclosed. |  |  |
| Look for supporting-document links on public pages. | Public pages do not expose private evidence files or direct media URLs. |  |  |
