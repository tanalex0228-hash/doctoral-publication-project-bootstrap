# RC5 CRUD and Permission Matrix

This matrix describes the business UI policy.  “Admin” means a project `admin`
or explicit root actor, not merely Django `is_staff`.  Historical/governance
rows are append-only or deactivated rather than hard-deleted.

| Entity | Create | Read | Update | Delete / deactivate | Business UI | Django Admin | Audit |
| --- | --- | --- | --- | --- | --- | --- | --- |
| User | Admin | self / staff | self password; Admin identity | Admin deactivates | profile / staff operations | governance | high-risk |
| Role / UserRole | Admin | Admin | Admin | deactivate / revoke | none | governance | yes |
| DoctoralStudentProfile | Staff/Admin | self necessary fields; Staff | Staff/Admin | inactive, not delete | staff operations | governance | yes |
| Professor / StudentAdvisor | Staff/Admin | scoped advisor / Staff | Staff/Admin | deactivate relationship | staff operations | governance | yes |
| PublicationType / PublicationIndex / ResearchField / Country / SDG / ConferencePresentationMode | Admin | applicable users | Admin | deactivate | none | taxonomy | administrative |
| PublicationRecord | Student draft/returned; Staff for governed correction | owner; scoped advisor; Staff; public only if policy passes | Student draft/returned; Staff through service | withdraw/archive/revoke; no raw delete | student, review, advisor portals | controlled actions only | yes |
| JournalArticleDetail / ConferenceDetail | with editable parent | same parent policy | with editable parent | follows parent governance | type-specific student forms | technical only | parent event |
| PublicationAuthor | owner in draft/returned | same parent policy | owner in draft/returned | owner in draft/returned | student detail | technical only | yes |
| SourceDocument | owner in draft/returned; authorized staff | owner/scoped advisor/Staff; never public | replacement creates new version | soft-retire only while editable | student detail; review download | read-only | yes |
| ReviewDecision / PublicationTransition / AuditLog | services only | Staff/Admin; owner receives necessary status | never | never | review/detail history | read-only | intrinsic |

## Explicit boundaries

- A Django `is_staff` user without a project role has no business workflow,
  document, review, statistics, or object-wide access.
- `submitted` records are read-only to students.  Approved and archived
  records use the existing revision flow for substantive changes.
- A withdrawn draft is retained for traceability.  This deliberately replaces
  a destructive “delete draft” operation.
- Private evidence is downloaded only through the authorization-checked route;
  public and department portals expose metadata, never document bytes.
