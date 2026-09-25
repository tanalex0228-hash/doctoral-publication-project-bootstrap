import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone
from audit.services import record_event
from review.services import record_transition
from .models import PublicationAuthor, PublicationRecord, PublicationSeries
from .querysets import is_official_publication
from .permissions import can_edit_publication, is_staff_actor


def _request_id(request_id): return request_id or str(uuid.uuid4())


@transaction.atomic
def create_publication(*, actor, owner_student, request_id=None, **fields):
    if not (is_staff_actor(actor) or owner_student.user_id == actor.id): raise PermissionDenied("Cannot create for another student.")
    series = PublicationSeries.objects.create(owner_student=owner_student)
    publication = PublicationRecord.objects.create(series=series, owner_student=owner_student, created_by=actor, updated_by=actor, **fields)
    record_transition(publication=publication, actor=actor, from_status="", to_status=PublicationRecord.WorkflowStatus.DRAFT, request_id=_request_id(request_id))
    record_event(actor=actor, action="publication.created", target=publication, request_id=request_id)
    return publication


STUDENT_EDITABLE_FIELDS = {
    "publication_type", "title", "abstract", "journal_or_conference_name", "language", "doi", "issn",
    "volume", "issue", "pages_or_article_number", "publication_stage", "submitted_to_journal_date",
    "accepted_date", "publication_date",
}


def _set_taxonomies(publication, *, indices, research_fields):
    publication.indices.set(indices)
    publication.research_fields.set(research_fields)


@transaction.atomic
def create_student_publication(*, actor, owner_student, indices=(), research_fields=(), request_id=None, **fields):
    """Create a draft plus its administrative classifications through one audited service boundary."""
    publication = create_publication(actor=actor, owner_student=owner_student, request_id=request_id, **fields)
    _set_taxonomies(publication, indices=indices, research_fields=research_fields)
    return publication


@transaction.atomic
def create_revision(*, actor, publication_id, request_id=None):
    """Create a pending relational revision without mutating the official version."""
    official = PublicationRecord.objects.select_related("series", "owner_student").select_for_update().get(pk=publication_id)
    series = PublicationSeries.objects.select_for_update().get(pk=official.series_id)
    if official.owner_student.user_id != actor.id or not is_official_publication(official):
        raise PermissionDenied("Only the owner may revise the current official version.")
    if series.versions.filter(
        is_revision=True,
        workflow_status__in={
            PublicationRecord.WorkflowStatus.DRAFT,
            PublicationRecord.WorkflowStatus.SUBMITTED,
            PublicationRecord.WorkflowStatus.RETURNED,
        },
    ).exists():
        raise ValidationError("An editable or submitted revision already exists for this publication.")
    values = {field: getattr(official, field) for field in STUDENT_EDITABLE_FIELDS}
    revision = PublicationRecord.objects.create(
        series=series,
        is_revision=True,
        owner_student=official.owner_student,
        created_by=actor,
        updated_by=actor,
        visibility_scope=official.visibility_scope,
        is_published=False,
        **values,
    )
    revision.indices.set(official.indices.all())
    revision.research_fields.set(official.research_fields.all())
    for author in official.authors.all():
        PublicationAuthor.objects.create(
            publication=revision,
            display_name=author.display_name,
            affiliation=author.affiliation,
            author_order=author.author_order,
            is_corresponding_author=author.is_corresponding_author,
            linked_user=author.linked_user,
            linked_professor=author.linked_professor,
            orcid=author.orcid,
        )
    rid = _request_id(request_id)
    record_transition(publication=revision, actor=actor, from_status="", to_status=PublicationRecord.WorkflowStatus.DRAFT, request_id=rid)
    record_event(
        actor=actor,
        action="publication.revision_created",
        target=revision,
        request_id=rid,
        metadata={"official_version_id": str(official.id)},
    )
    return revision


@transaction.atomic
def update_publication(*, actor, publication_id, indices=(), research_fields=(), request_id=None, **fields):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if not can_edit_publication(actor, publication):
        raise PermissionDenied("Publication is not editable by this actor.")
    unexpected = set(fields) - STUDENT_EDITABLE_FIELDS
    if unexpected:
        raise ValidationError(f"Protected fields cannot be changed: {', '.join(sorted(unexpected))}")
    for field, value in fields.items():
        setattr(publication, field, value)
    publication.updated_by = actor
    publication.full_clean()
    publication.save()
    _set_taxonomies(publication, indices=indices, research_fields=research_fields)
    record_event(actor=actor, action="publication.updated", target=publication, request_id=_request_id(request_id), metadata={"fields": sorted(fields)})
    return publication


def _editable_author_publication(*, actor, publication_id):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if not can_edit_publication(actor, publication):
        raise PermissionDenied("Authors can only be managed on the student's draft or returned publication.")
    return publication


@transaction.atomic
def add_author(*, actor, publication_id, request_id=None, **fields):
    publication = _editable_author_publication(actor=actor, publication_id=publication_id)
    next_order = (publication.authors.aggregate(value=Max("author_order"))["value"] or 0) + 1
    author = publication.authors.create(author_order=next_order, **fields)
    record_event(actor=actor, action="publication_author.created", target=author, request_id=_request_id(request_id))
    return author


@transaction.atomic
def update_author(*, actor, author_id, request_id=None, **fields):
    author = PublicationAuthor.objects.select_related("publication").select_for_update().get(pk=author_id)
    _editable_author_publication(actor=actor, publication_id=author.publication_id)
    for field in ("display_name", "affiliation", "is_corresponding_author", "linked_user", "linked_professor", "orcid"):
        if field in fields:
            setattr(author, field, fields[field])
    author.full_clean()
    author.save()
    record_event(actor=actor, action="publication_author.updated", target=author, request_id=_request_id(request_id))
    return author


@transaction.atomic
def delete_author(*, actor, author_id, request_id=None):
    author = PublicationAuthor.objects.select_related("publication").select_for_update().get(pk=author_id)
    _editable_author_publication(actor=actor, publication_id=author.publication_id)
    record_event(actor=actor, action="publication_author.deleted", target=author, request_id=_request_id(request_id), metadata={"author_order": author.author_order})
    author.delete()


@transaction.atomic
def move_author(*, actor, author_id, direction, request_id=None):
    author = PublicationAuthor.objects.select_related("publication").select_for_update().get(pk=author_id)
    publication = _editable_author_publication(actor=actor, publication_id=author.publication_id)
    authors = list(publication.authors.select_for_update().order_by("author_order", "created_at"))
    current_index = next(index for index, item in enumerate(authors) if item.pk == author.pk)
    offset = -1 if direction == "up" else 1 if direction == "down" else 0
    target_index = current_index + offset
    if not offset or target_index < 0 or target_index >= len(authors):
        raise ValidationError("Author cannot be moved in that direction.")
    other = authors[target_index]
    original_order, other_order = author.author_order, other.author_order
    temporary_order = max(item.author_order for item in authors) + 1
    author.author_order = temporary_order
    author.save(update_fields=["author_order"])
    other.author_order = original_order
    other.save(update_fields=["author_order"])
    author.author_order = other_order
    author.save(update_fields=["author_order"])
    record_event(actor=actor, action="publication_author.reordered", target=author, request_id=_request_id(request_id), metadata={"direction": direction})
    return author


def validate_submission_completeness(publication):
    """Return human-readable, policy-backed gaps without mutating lifecycle state."""
    errors = []
    if not publication.title.strip():
        errors.append("請填寫成果標題。")
    if not publication.publication_type_id:
        errors.append("請選擇成果類型。")
    if not publication.authors.exists():
        errors.append("請至少新增一位作者。")
    has_evidence = publication.documents.filter(is_active=True).exists()
    if publication.is_revision and publication.series.current_official_version_id:
        has_evidence = has_evidence or publication.series.current_official_version.documents.filter(is_active=True).exists()
    if not has_evidence:
        errors.append("請至少上傳一份有效佐證文件。")
    return errors


@transaction.atomic
def submit_publication(*, actor, publication_id, request_id=None):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if not can_edit_publication(actor, publication): raise PermissionDenied("Publication is not editable by this actor.")
    if publication.workflow_status not in {PublicationRecord.WorkflowStatus.DRAFT, PublicationRecord.WorkflowStatus.RETURNED}: raise ValidationError("Only draft or returned publications can be submitted.")
    completeness_errors = validate_submission_completeness(publication)
    if completeness_errors:
        raise ValidationError(completeness_errors)
    old = publication.workflow_status
    publication.workflow_status, publication.submitted_at, publication.updated_by = PublicationRecord.WorkflowStatus.SUBMITTED, timezone.now(), actor
    publication.save(update_fields=["workflow_status", "submitted_at", "updated_by", "updated_at"])
    rid = _request_id(request_id)
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, request_id=rid)
    record_event(actor=actor, action="publication.submitted", target=publication, request_id=rid)
    return publication


@transaction.atomic
def withdraw_publication(*, actor, publication_id, request_id=None):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if publication.owner_student.user_id != actor.id or publication.workflow_status not in {PublicationRecord.WorkflowStatus.DRAFT, PublicationRecord.WorkflowStatus.RETURNED}: raise PermissionDenied("Publication cannot be withdrawn.")
    old, publication.workflow_status, publication.updated_by = publication.workflow_status, PublicationRecord.WorkflowStatus.WITHDRAWN, actor
    publication.save(update_fields=["workflow_status", "updated_by", "updated_at"])
    rid = _request_id(request_id)
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, request_id=rid)
    record_event(actor=actor, action="publication.withdrawn", target=publication, request_id=rid)
    return publication


@transaction.atomic
def set_visibility(*, actor, publication_id, visibility_scope, request_id=None):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if not is_staff_actor(actor) or publication.workflow_status != PublicationRecord.WorkflowStatus.APPROVED: raise PermissionDenied("Only staff may set visibility for approved records.")
    publication.visibility_scope, publication.updated_by = visibility_scope, actor
    publication.full_clean(); publication.save(update_fields=["visibility_scope", "updated_by", "updated_at"])
    record_event(actor=actor, action="publication.visibility_changed", target=publication, request_id=_request_id(request_id), metadata={"visibility_scope": visibility_scope})
    return publication


@transaction.atomic
def set_published(*, actor, publication_id, is_published, request_id=None):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if not is_staff_actor(actor) or publication.workflow_status != PublicationRecord.WorkflowStatus.APPROVED: raise PermissionDenied("Only staff may publish approved records.")
    publication.is_published, publication.updated_by = is_published, actor
    publication.full_clean(); publication.save(update_fields=["is_published", "updated_by", "updated_at"])
    record_event(actor=actor, action="publication.publish_changed", target=publication, request_id=_request_id(request_id), metadata={"is_published": is_published})
    return publication
