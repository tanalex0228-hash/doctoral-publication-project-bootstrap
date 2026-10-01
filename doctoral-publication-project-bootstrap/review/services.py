import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from audit.services import record_event
from publications.models import (
    ConferenceDetail, ConferenceParticipantCountry,
    ConferencePresentationModeAssignment, JournalArticleDetail,
    PublicationAuthor, PublicationRecord, PublicationSDGAssignment,
    PublicationSeries,
)
from publications.permissions import can_review_publication
from publications.querysets import is_official_publication
from .models import PublicationTransition, ReviewDecision


def record_transition(*, publication, actor, from_status, to_status, request_id, reason=""):
    return PublicationTransition.objects.create(publication=publication, actor=actor, from_status=from_status, to_status=to_status, request_id=request_id, reason=reason)


def _locked_for_review(actor, publication_id):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if not can_review_publication(actor, publication): raise PermissionDenied("Staff or admin role is required.")
    if publication.workflow_status != PublicationRecord.WorkflowStatus.SUBMITTED: raise ValidationError("Only submitted publications may be reviewed.")
    return publication


REVISION_COPY_FIELDS = (
    "publication_type", "title", "abstract", "journal_or_conference_name",
    "language", "doi", "issn", "volume", "issue",
    "pages_or_article_number", "publication_stage", "submitted_to_journal_date",
    "accepted_date", "publication_date",
)


def _replace_journal_detail(source, target):
    try:
        source_detail = source.journal_detail
    except JournalArticleDetail.DoesNotExist:
        return
    try:
        target.conference_detail.delete()
    except ConferenceDetail.DoesNotExist:
        pass
    target_detail, _ = JournalArticleDetail.objects.get_or_create(publication=target)
    for field in JournalArticleDetail._meta.fields:
        if field.name not in {"id", "publication"}:
            setattr(target_detail, field.name, getattr(source_detail, field.name))
    target_detail.full_clean()
    target_detail.save()


def _replace_conference_detail(source, target):
    try:
        source_detail = source.conference_detail
    except ConferenceDetail.DoesNotExist:
        return
    try:
        target.journal_detail.delete()
    except JournalArticleDetail.DoesNotExist:
        pass
    target_detail, _ = ConferenceDetail.objects.get_or_create(publication=target)
    for field in ConferenceDetail._meta.fields:
        if field.name not in {"id", "publication"}:
            setattr(target_detail, field.name, getattr(source_detail, field.name))
    target_detail.full_clean()
    target_detail.save()
    target_detail.participant_country_assignments.all().delete()
    ConferenceParticipantCountry.objects.bulk_create([
        ConferenceParticipantCountry(conference=target_detail, country=item.country)
        for item in source_detail.participant_country_assignments.all()
    ])
    target_detail.presentation_mode_assignments.all().delete()
    ConferencePresentationModeAssignment.objects.bulk_create([
        ConferencePresentationModeAssignment(conference=target_detail, mode=item.mode)
        for item in source_detail.presentation_mode_assignments.all()
    ])


def _merge_approved_revision(*, revision, official, actor, request_id):
    """Apply a reviewed draft to its existing official record without replacing it."""
    changed_fields = []
    for field in REVISION_COPY_FIELDS:
        source_value = getattr(revision, field)
        if getattr(official, field) != source_value:
            setattr(official, field, source_value)
            changed_fields.append(field)
    official.updated_by = actor
    official.full_clean()
    official.save()
    official.indices.set(revision.indices.all())
    official.research_fields.set(revision.research_fields.all())

    official.authors.all().delete()
    PublicationAuthor.objects.bulk_create([
        PublicationAuthor(
            publication=official, display_name=author.display_name,
            affiliation=author.affiliation, author_order=author.author_order,
            is_corresponding_author=author.is_corresponding_author,
            linked_user=author.linked_user, linked_professor=author.linked_professor,
            orcid=author.orcid,
        ) for author in revision.authors.all()
    ])
    _replace_journal_detail(revision, official)
    _replace_conference_detail(revision, official)
    official.sdg_assignments.all().delete()
    PublicationSDGAssignment.objects.bulk_create([
        PublicationSDGAssignment(publication=official, goal=item.goal)
        for item in revision.sdg_assignments.all()
    ])
    record_event(
        actor=actor, action="publication.revision_merged", target=official,
        request_id=request_id,
        metadata={"revision_id": str(revision.id), "changed_fields": changed_fields},
    )
    return changed_fields


@transaction.atomic
def approve_publication(*, actor, publication_id, request_id=None):
    publication = _locked_for_review(actor, publication_id)
    series = PublicationSeries.objects.select_for_update().get(pk=publication.series_id)
    previous_official = series.current_official_version
    old = publication.workflow_status
    publication.workflow_status, publication.approved_at, publication.approved_by, publication.updated_by = PublicationRecord.WorkflowStatus.APPROVED, timezone.now(), actor, actor
    rid = request_id or str(uuid.uuid4())
    merged_fields = []
    if publication.is_revision and previous_official:
        # A revision is an internal change request, never a second public
        # result. Keep the original entity current and merge only after review.
        merged_fields = _merge_approved_revision(
            revision=publication, official=previous_official, actor=actor,
            request_id=rid,
        )
        publication.visibility_scope = previous_official.visibility_scope
        publication.is_published = previous_official.is_published
    publication.save(update_fields=["workflow_status", "approved_at", "approved_by", "updated_by", "visibility_scope", "is_published", "updated_at"])
    if not publication.is_revision:
        series.current_official_version = publication
        series.save(update_fields=["current_official_version", "updated_at"])
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, request_id=rid)
    ReviewDecision.objects.create(publication=publication, reviewer=actor, action=ReviewDecision.Action.APPROVE, visibility_after=publication.visibility_scope)
    record_event(
        actor=actor,
        action="publication.revision_approved" if publication.is_revision else "publication.approved",
        target=publication,
        request_id=rid,
        metadata={"merged_into_publication_id": str(previous_official.id), "changed_fields": merged_fields}
        if publication.is_revision and previous_official else None,
    )
    return publication


@transaction.atomic
def return_for_revision(*, actor, publication_id, reason="", request_id=None):
    publication = _locked_for_review(actor, publication_id)
    old = publication.workflow_status
    publication.workflow_status, publication.updated_by = PublicationRecord.WorkflowStatus.RETURNED, actor
    publication.save(update_fields=["workflow_status", "updated_by", "updated_at"])
    rid = request_id or str(uuid.uuid4())
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, reason=reason, request_id=rid)
    ReviewDecision.objects.create(publication=publication, reviewer=actor, action=ReviewDecision.Action.RETURN, reason=reason)
    record_event(actor=actor, action="publication.returned", target=publication, request_id=rid)
    return publication


@transaction.atomic
def archive_publication(*, actor, publication_id, reason="", request_id=None):
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if not can_review_publication(actor, publication) or publication.workflow_status != PublicationRecord.WorkflowStatus.APPROVED or not is_official_publication(publication): raise PermissionDenied("Only staff may archive the current approved publication.")
    old, publication.workflow_status, publication.updated_by = publication.workflow_status, PublicationRecord.WorkflowStatus.ARCHIVED, actor
    publication.save(update_fields=["workflow_status", "updated_by", "updated_at"])
    rid = request_id or str(uuid.uuid4())
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, reason=reason, request_id=rid)
    ReviewDecision.objects.create(publication=publication, reviewer=actor, action=ReviewDecision.Action.ARCHIVE, reason=reason)
    record_event(actor=actor, action="publication.archived", target=publication, request_id=rid)
    return publication


@transaction.atomic
def restore_publication(*, actor, publication_id, request_id=None):
    """Restore a current archived official record before re-publishing it."""
    publication = PublicationRecord.objects.select_for_update().get(pk=publication_id)
    if (
        not can_review_publication(actor, publication)
        or publication.workflow_status != PublicationRecord.WorkflowStatus.ARCHIVED
        or not is_official_publication(publication)
    ):
        raise PermissionDenied("Only staff may restore the current archived publication.")
    old = publication.workflow_status
    publication.workflow_status = PublicationRecord.WorkflowStatus.APPROVED
    publication.updated_by = actor
    publication.save(update_fields=["workflow_status", "updated_by", "updated_at"])
    rid = request_id or str(uuid.uuid4())
    record_transition(
        publication=publication, actor=actor, from_status=old,
        to_status=publication.workflow_status, request_id=rid,
        reason="重新公開前恢復核准狀態",
    )
    record_event(actor=actor, action="publication.restored", target=publication, request_id=rid)
    return publication


@transaction.atomic
def revoke_approval(*, actor, publication_id, reason="", request_id=None):
    """Invalidate a current approval without erasing its governance history."""
    publication = PublicationRecord.objects.select_for_update().select_related("series").get(pk=publication_id)
    series = PublicationSeries.objects.select_for_update().get(pk=publication.series_id)
    if (
        not can_review_publication(actor, publication)
        or publication.workflow_status not in {PublicationRecord.WorkflowStatus.APPROVED, PublicationRecord.WorkflowStatus.ARCHIVED}
        or not is_official_publication(publication)
    ):
        raise PermissionDenied("Only staff may revoke the current official approval.")
    old = publication.workflow_status
    publication.workflow_status = PublicationRecord.WorkflowStatus.REVOKED
    publication.approval_revoked_at = timezone.now()
    publication.approval_revoked_by = actor
    publication.is_published = False
    publication.updated_by = actor
    publication.save(update_fields=[
        "workflow_status", "approval_revoked_at", "approval_revoked_by",
        "is_published", "updated_by", "updated_at",
    ])
    series.current_official_version = None
    series.save(update_fields=["current_official_version", "updated_at"])
    rid = request_id or str(uuid.uuid4())
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, reason=reason, request_id=rid)
    ReviewDecision.objects.create(publication=publication, reviewer=actor, action=ReviewDecision.Action.REVOKE, reason=reason)
    record_event(actor=actor, action="publication.approval_revoked", target=publication, request_id=rid, metadata={"reason": reason})
    return publication
