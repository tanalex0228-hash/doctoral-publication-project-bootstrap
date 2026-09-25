# AGENTS.md

## Project identity
This repository implements the **Fu Jen Catholic University Graduate Institute of Business Administration doctoral publication management system**.

The system manages doctoral students, advisors, publication records, authors, supporting/source documents, secretary review, visibility, audit history, and approved-publication statistics.

This is a long-lived institutional information system. The expected operational horizon is 20–30 years. Optimize for correctness, traceability, permission safety, migration safety, and maintainability before convenience or novelty.

## Source of truth
Before making changes, use the following priority order:

1. This `AGENTS.md`.
2. The project Notion page `輔仁大學 商學博士班 學生文獻期刊 管理資訊系統` and its child pages.
3. `docs/ENGINEERING_CONTRACT.md`.
4. `docs/Database_Field_Matrix.xlsx`.
5. Existing code and tests.

When Notion and code disagree, do not silently guess. Identify the conflict and follow the latest explicit project decision. Do not reread every Notion page for every task; load only the pages relevant to the current change unless performing an architecture/security review.

## Product non-goals
Do **not** add the following unless a later explicit project decision says otherwise:

- graduation-eligibility rules engine;
- AI extraction, RAG, embeddings, pgvector, Knowledge Graph, or LLM-dependent core behavior;
- microservices;
- Redis/Celery as mandatory infrastructure for the MVP;
- automatic advisor/publication recommendations.

## Architecture baseline
Use a Django 5.2 modular monolith with PostgreSQL.

Preferred presentation stack: Django Templates + Bootstrap 5, with small amounts of HTMX only where it clearly reduces complexity.

Production baseline: Nginx + Gunicorn + private file storage. Docker Compose or systemd is acceptable. The application must not depend on a specific deployment topology.

Suggested Django apps:

- `accounts`
- `doctoral_students`
- `professors`
- `advising`
- `publications`
- `documents`
- `review`
- `statistics`
- `dashboard`
- `public_site`
- `config`

Business rules belong in service/domain layers, not templates or JavaScript.

## Core domain rules
These rules are frozen unless a documented architecture decision changes them:

1. A student creates a `PublicationRecord` before uploading any source/supporting document.
2. `SourceDocument` cannot exist without a parent publication.
3. Only secretary-approved publications count in official statistics.
4. `approved`, `published`, and `public` are different concepts.
5. Keep `workflow_status`, `is_published`, and `visibility_scope` separate.
6. Students cannot directly set a publication to `approved`.
7. Sensitive authorization is always enforced on the backend.
8. Private files must never be exposed through a directly browsable public media path.
9. Review decisions, lifecycle transitions, and high-risk administrative changes must be auditable.
10. Historical institutional data should normally be archived/deactivated rather than hard-deleted.

## Workflow
Canonical workflow:

`draft -> submitted -> returned -> submitted -> approved -> archived`

Optional withdrawal may exist only if explicitly implemented by the specification.

All lifecycle transitions must:

- run through a service function;
- use a database transaction;
- use row locking when a race could create duplicate or inconsistent decisions;
- record the actor, reason/context, timestamp, and transition/review history;
- have tests for legal and illegal transitions.

Never update governed status fields directly from a form, view, admin action, or queryset update.

## Visibility and object permissions
Visibility values are behavior-bearing states and must not be admin-extensible taxonomy values.

Canonical scopes:

- `public`: anyone may view an approved/published record intended for public display;
- `department`: authorized departmental students/faculty/staff;
- `owner_advisor`: publication owner + active advisor(s) + staff/admin;
- `staff_only`: staff/admin only.

Role alone is insufficient. `owner_advisor` requires object-level authorization through the student/advisor relationship.

Do not treat Django `is_staff` as equivalent to project-wide staff data access.

For protected resources, prefer non-disclosing authorization behavior where appropriate; do not leak the existence of private records via predictable IDs or different error messages.

## Taxonomy vs business state
Admin/root users may create, rename, order, activate, or deactivate **pure classification data**, such as:

- publication type;
- publication/journal index classification;
- research field;
- future administrative classification lists.

Do not hard-code these categories when they are expected to evolve administratively.

Do **not** make behavior-bearing states admin-extensible, including:

- workflow states;
- visibility scopes;
- review actions;
- permission states.

Rule of thumb: if adding a value changes application behavior, it belongs in code/state-machine logic. If it only classifies data, it belongs in taxonomy tables.

## Documents
Supported MVP formats: PDF, JPG/JPEG, PNG.

Every upload must validate file extension, MIME type, and size, and compute a SHA-256 checksum.

Store file metadata and an opaque storage key in the database. Downloads must pass through a permission-checked backend route.

Do not silently replace provenance-critical fields such as parent publication, uploader, checksum, or storage identity. If a document is replaced, preserve a traceable version/replacement relationship or a fully audited replacement operation.

## Statistics
Official statistics must be derived from approved publication records only.

Do not trust a frontend flag or cached client-side state to decide whether a publication counts.

Secretary-facing statistics may filter/sort by student, admission year, publication type, journal/index category, author role, advisor, language, publication year/date, and other fields defined in the field matrix.

The system provides evidence and counts; it does not automatically decide graduation eligibility.

## Data modeling rules
Prefer explicit relational columns and foreign keys for governed data. Do not hide core business fields in JSON.

Use stable UUID identifiers for core entities unless the existing schema explicitly specifies otherwise.

Use database constraints and indexes for invariants that the database can enforce.

Avoid destructive schema rewrites when an additive migration is sufficient.

## Development method
The project uses two phases:

### Phase A: architecture-first rapid development
Freeze the domain model, permissions, workflow, document governance, review/audit behavior, and deployment skeleton before optimizing UI details.

### Phase B: agile iteration
After the architecture is stable, iterate quickly on UI, field presentation, filters, dashboards, wording, and secretary/student workflow details.

If an agile request changes a frozen domain rule, schema boundary, permission model, or workflow, treat it as an architecture change: document the decision first and then implement it deliberately.

## Codex task procedure
For each task:

1. Read this file.
2. Read only the Notion pages and local docs relevant to the task.
3. Identify affected models, services, permissions, migrations, tests, templates, and deployment/config files.
4. State the smallest implementation plan before broad changes.
5. Implement the smallest coherent vertical slice.
6. Add/update tests in the same change.
7. Run the relevant checks/tests.
8. Summarize changed files, behavior, migrations, and remaining risks.

Avoid opportunistic unrelated refactors.

## Required quality gates
At minimum, before a milestone/release:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Use narrower tests during iteration, but do not skip the full suite before milestone integration.

Critical test coverage must include:

- student A cannot read/edit student B private records;
- advisor access is limited to active advised students and allowed visibility;
- students cannot approve their own records;
- illegal workflow jumps fail;
- only approved publications appear in official statistics;
- private document downloads require authorization;
- direct public media access does not bypass permissions;
- staff/admin actions create audit evidence where required.

## Model usage guidance
Default development model: **GPT-5.6 Terra Medium**.

Escalate to higher reasoning for schema/migration redesign, RBAC/object permissions, transactions/concurrency, document-integrity changes, cross-app refactors, difficult regressions, architecture freeze reviews, and security gates.

Do not spend high reasoning budget on routine templates, labels, Bootstrap spacing, or simple CRUD once the domain contract is stable.

## Change discipline
Never weaken permissions just to make tests pass.
Never duplicate server-side business rules in JavaScript.
Never invent missing requirements when they affect schema, permissions, or lifecycle. Surface the ambiguity instead.
Never introduce a new framework/service merely because it is convenient for one task.
