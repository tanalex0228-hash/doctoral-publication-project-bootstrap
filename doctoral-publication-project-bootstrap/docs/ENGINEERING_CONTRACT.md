# Engineering Contract

## Purpose

This document is the local, repository-contained fallback contract for the doctoral publication management system. It is intentionally smaller than the full Notion Product Bible but detailed enough to keep implementation aligned when a coding agent is initialized with only repository context.

The canonical project documentation lives in Notion under **輔仁大學 商學博士班 學生文獻期刊 管理資訊系統**. This document must stay compatible with those decisions.

## System responsibility

The system records and governs doctoral academic outputs over a multi-year student lifecycle. It provides:

- student and advisor identity/relationships;
- publication metadata;
- authors and collaborators;
- journal/index classifications and research fields;
- source/supporting documents;
- submission and secretary review;
- approval/rejection/return history;
- publication visibility;
- secretary statistics and sorting;
- public/department/advisor-restricted reading;
- auditability and long-term exportability.

It does not decide whether a student satisfies graduation regulations. Staff use approved publication statistics and the underlying evidence to make that decision manually.

## Principal actors

### Student

May create and maintain their own draft/returned publication records, manage authors and documents within allowed states, submit for review, and view all of their own records.

### Advisor

May view records of students with an active advisor relationship when the publication visibility allows advisor access. Advisor access is object-scoped, not global.

### Staff / secretary

May manage students, review submissions, approve or return records, set publishing/visibility, view official statistics, and perform authorized administrative corrections.

### Admin/root

May perform platform-wide administration and high-risk maintenance. Admin/root may manage taxonomy tables. Admin/root authority must remain distinct from ordinary Django `is_staff` semantics.

### Visitor

May view only approved, published, public information.

## Core entities

### User

Authentication identity with stable identifier, email/login identity, active state, and role relationships.

### DoctoralStudentProfile

Student-specific institutional metadata such as student number, admission year, enrollment status, display name, and research field.

### Professor

Advisor identity and status.

### StudentAdvisor

Relationship between a doctoral student and professor, including primary/co-advisor role and active period. This relationship drives object-level access.

### PublicationRecord

The governed academic-output record. It exists before source files are uploaded.

Representative fields include:

- owner student;
- title;
- abstract;
- publication type;
- journal/conference name;
- language;
- research field;
- DOI/ISSN/volume/issue/pages where applicable;
- acceptance/publication dates;
- workflow status;
- publish flag;
- visibility scope;
- creator/updater and timestamps.

Exact field definitions are controlled by `Database_Field_Matrix.xlsx`.

### PublicationAuthor

Supports internal and external authors. Author records must not require every collaborator to have an application account.

Representative fields:

- display name;
- affiliation;
- order;
- corresponding-author flag;
- optional linked internal user;
- optional linked professor.

Author order must be unique within a publication.

### Taxonomy tables

At minimum:

- publication type;
- publication/journal index classification;
- research field.

Taxonomies are admin-maintained classification data. They should normally carry stable IDs/slugs, display names, active state, ordering, timestamps, and auditability.

### SourceDocument

A private evidence/source file tied to exactly one publication.

Representative metadata:

- document type;
- original filename;
- MIME type;
- storage key;
- size;
- SHA-256 checksum;
- uploader;
- upload time;
- optional replacement/version link.

### ReviewDecision / PublicationTransition

Append-oriented governance evidence for submission/review/lifecycle changes. High-value historical decisions should not be silently overwritten.

### AuditLog

Records important administrative/domain events without storing secrets such as passwords, session tokens, or file contents.

## Three independent state dimensions

Do not collapse these concepts.

### Workflow state

Controls review lifecycle:

- draft;
- submitted;
- returned;
- approved;
- archived;
- optional withdrawn if explicitly implemented.

### Publishing state

`is_published` (or equivalent) controls whether an approved record is exposed through a publication-facing surface.

### Visibility state

Controls the audience:

- public;
- department;
- owner_advisor;
- staff_only.

A valid record can therefore be approved but not published, or approved and published but visible only to owner/advisors/staff.

## State-machine contract

Canonical transitions:

```text
draft -> submitted
submitted -> returned
returned -> submitted
submitted -> approved
approved -> archived
```

If withdrawal is implemented, it must be explicitly specified and tested.

No direct student-driven transition to `approved` is permitted.

Transitions are service-layer operations using transactions. Where two reviewers/actions could race, use row-level locking or an equivalent safe pattern.

Each governed transition should preserve actor, timestamp, previous state, next state, reason/context where appropriate, and request/audit linkage.

## Authorization contract

Authorization is evaluated using both role and object relationships.

### Owner access

A doctoral student can manage only publications owned by that student, and only while the publication's workflow permits editing.

### Advisor access

Advisor access requires an active student-advisor relationship. An advisor role alone must never expose all doctoral records.

### Staff access

Staff may access records needed for review/statistics/administration according to the project role model.

### Visibility evaluation

`owner_advisor` includes the owner, active advisor(s), staff, and admin. It must exclude unrelated students and unrelated professors.

### File access

Document authorization is at least as strict as its parent publication. A child file may be stricter; it may not become more public than the governing publication without an explicit, safe rule.

## Taxonomy contract

Classification data that may change administratively must live in database-backed taxonomy tables.

Examples:

- Journal Article / Conference Paper / Book Chapter / Other;
- SSCI / SCI / SCIE / EI / TSSCI / Scopus / future classifications;
- Finance / MIS / Management Science / future research fields.

Do not create a deployment requirement just to add a new administrative classification.

Behavior-bearing states remain code-controlled because adding one requires defined semantics, transitions, permissions, statistics behavior, and tests.

## Document contract

The upload pipeline must:

1. confirm a valid parent publication;
2. validate allowed extension;
3. validate MIME type;
4. validate configured maximum size;
5. compute SHA-256;
6. write to private storage using an opaque key;
7. persist metadata transactionally/safely;
8. create audit evidence;
9. prevent unauthenticated direct filesystem/media exposure.

Replacement must be traceable. Do not silently overwrite evidence bytes while keeping the same historical identity.

## Statistics contract

The official statistical universe is approved publication records only.

Secretary views should support practical filtering/sorting. The database should be indexed for fields used frequently in review queues and statistics.

The application does not derive a graduation verdict. It provides counts, categories, authorship facts, dates, advisor relationships, and evidence.

## Data-integrity and database rules

Use database-level uniqueness/check constraints when practical.

Examples include:

- unique student number;
- unique stable taxonomy slug;
- unique author order within a publication;
- coherent active advisor relationships;
- legal date/range constraints where unambiguous;
- indexes on workflow status, owner/student, dates, type/classification, advisor relationships, and common review/statistics filters.

Do not encode critical relational facts only in JSON.

## Long-term maintainability

The 20–30 year requirement means data and governance must survive framework generations; it does not mean one Django version runs for 30 years.

The system must remain portable through documented exports and backups.

At minimum, maintain the ability to export:

- students;
- professors;
- advisor relations;
- publications;
- authors;
- classification links;
- review/lifecycle history;
- document manifest plus original files.

Backups must include PostgreSQL and private file storage. Restore drills are part of operations, not an optional future enhancement.

## Implementation policy

### Architecture-first stage

Implement models, constraints, services, permissions, lifecycle, document governance, audit, and deployment foundation before polishing workflows.

### Agile stage

After domain freeze, iterate on forms, dashboards, sort/filter behavior, wording, and navigation. Changes that require schema/permission/workflow redesign are architecture changes, not routine UI iterations.

## Testing contract

Critical behaviors must be covered by automated tests, including:

- ownership isolation;
- advisor relationship isolation;
- visibility isolation;
- review permissions;
- legal/illegal transitions;
- approved-only statistics;
- private document authorization;
- immutable/audited governance behavior;
- taxonomy administration where applicable;
- migration consistency.

No feature is complete when only the happy-path UI works.
