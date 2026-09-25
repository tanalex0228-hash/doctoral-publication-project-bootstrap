import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from audit.services import record_event
from publications.models import PublicationRecord, PublicationSeries
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


@transaction.atomic
def approve_publication(*, actor, publication_id, request_id=None):
    publication = _locked_for_review(actor, publication_id)
    series = PublicationSeries.objects.select_for_update().get(pk=publication.series_id)
    previous_official = series.current_official_version
    old = publication.workflow_status
    publication.workflow_status, publication.approved_at, publication.approved_by, publication.updated_by = PublicationRecord.WorkflowStatus.APPROVED, timezone.now(), actor, actor
    if publication.is_revision and previous_official:
        # Publication settings are administrative, not student-controlled. Keep
        # the prior official audience when a reviewed revision becomes current.
        publication.visibility_scope = previous_official.visibility_scope
        publication.is_published = previous_official.is_published
    publication.save(update_fields=["workflow_status", "approved_at", "approved_by", "updated_by", "visibility_scope", "is_published", "updated_at"])
    series.current_official_version = publication
    series.save(update_fields=["current_official_version", "updated_at"])
    rid = request_id or str(uuid.uuid4())
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, request_id=rid)
    ReviewDecision.objects.create(publication=publication, reviewer=actor, action=ReviewDecision.Action.APPROVE, visibility_after=publication.visibility_scope)
    record_event(
        actor=actor,
        action="publication.revision_approved" if publication.is_revision else "publication.approved",
        target=publication,
        request_id=rid,
        metadata={"replaced_official_version_id": str(previous_official.id)} if publication.is_revision and previous_official else None,
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
