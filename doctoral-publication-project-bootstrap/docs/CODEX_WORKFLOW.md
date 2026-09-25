# Codex Workflow — Token-Efficient Development

## Goal

Use Codex as the main implementation accelerator without repeatedly paying the context and rework cost of rediscovering the architecture.

Default working model: **GPT-5.6 Terra Medium**.

## Initialization

At the start of a coding session:

1. Read repository-root `AGENTS.md`.
2. Identify the requested feature/module.
3. Load only the relevant Notion pages for that feature.
4. Consult `docs/Database_Field_Matrix.xlsx` only for the affected tables/fields.
5. Inspect only the relevant code paths and tests before expanding repo-wide.

Avoid “read the entire repository and all Notion docs” unless the task is explicitly a full architecture/security review.

## Task template

Use a request shape similar to:

```text
Implement <feature>.

Read AGENTS.md first.
Use Notion pages: <specific page names>.
Use Database_Field_Matrix.xlsx for the affected schema.

Before editing:
1. list affected files;
2. state whether a migration is required;
3. state permission/workflow impact;
4. propose the smallest vertical slice.

Then implement code + tests.
Do not refactor unrelated modules.
Run relevant checks/tests and report results.
```

## Preferred unit of work

A task should be a coherent vertical slice rather than a disconnected layer.

Good examples:

- student creates and edits a draft publication, including ownership tests;
- student uploads a source document to an existing publication, including private download tests;
- secretary returns a submitted publication with an optional reason, including audit history;
- secretary approves a submission and the approved-only statistics update;
- advisor views an owner_advisor publication for an actively advised student.

Avoid splitting one simple feature across many sessions such as “model today, permissions tomorrow, tests later” because each session must reload context.

## When to use higher reasoning

Escalate beyond Terra Medium for:

- changing core tables or relationships after architecture freeze;
- data migration/backfill design;
- RBAC/object permission redesign;
- transaction/concurrency problems;
- document integrity or security-sensitive changes;
- cross-app refactoring;
- difficult regressions;
- release/security reviews.

Keep routine template, Bootstrap, copy, simple forms, and straightforward CRUD work on the default model.

## Context-cost controls

- Do not paste full test logs when a failing traceback and relevant lines are enough.
- Do not repeatedly ask for a full repository review after each small feature.
- Prefer stable local contracts (`AGENTS.md`, engineering contract, field matrix) over re-deriving decisions from conversation history.
- Keep taxonomy/data configuration out of code when admin-managed values may change.
- Avoid speculative abstractions; implement the current contract cleanly.
- Reuse established service/permission patterns instead of asking the model to invent a new architecture for each feature.

## Review cadence

### Per task

Run targeted tests and Django checks relevant to the changed module.

### Per milestone

Run:

```bash
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test
```

Perform one cross-module review at milestone boundaries rather than after every small change.

## Architecture freeze rule

After the architecture-first phase, the following are considered frozen unless a documented decision changes them:

- core entity boundaries;
- publication-document parentage;
- workflow state machine;
- approved-only statistics rule;
- visibility semantics;
- object-level advisor/owner authorization;
- taxonomy-vs-business-state distinction;
- private storage requirement;
- audit/traceability requirement.

A request that changes one of these must be treated as an architecture change, not a quick agile tweak.

## Completion report

At the end of each task, Codex should report:

- files changed;
- migrations added/changed;
- domain behavior changed;
- permission impact;
- tests added/changed;
- commands/tests executed and result;
- open risks or unresolved requirements.

This report becomes the cheapest context for the next related task.
