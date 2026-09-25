import uuid
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone
from audit.services import record_event
from publications.models import PublicationRecord
from publications.permissions import can_review_publication
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
    old = publication.workflow_status
    publication.workflow_status, publication.approved_at, publication.approved_by, publication.updated_by = PublicationRecord.WorkflowStatus.APPROVED, timezone.now(), actor, actor
    publication.save(update_fields=["workflow_status", "approved_at", "approved_by", "updated_by", "updated_at"])
    rid = request_id or str(uuid.uuid4())
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, request_id=rid)
    ReviewDecision.objects.create(publication=publication, reviewer=actor, action=ReviewDecision.Action.APPROVE, visibility_after=publication.visibility_scope)
    record_event(actor=actor, action="publication.approved", target=publication, request_id=rid)
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
    if not can_review_publication(actor, publication) or publication.workflow_status != PublicationRecord.WorkflowStatus.APPROVED: raise PermissionDenied("Only staff may archive approved publications.")
    old, publication.workflow_status, publication.updated_by = publication.workflow_status, PublicationRecord.WorkflowStatus.ARCHIVED, actor
    publication.save(update_fields=["workflow_status", "updated_by", "updated_at"])
    rid = request_id or str(uuid.uuid4())
    record_transition(publication=publication, actor=actor, from_status=old, to_status=publication.workflow_status, reason=reason, request_id=rid)
    ReviewDecision.objects.create(publication=publication, reviewer=actor, action=ReviewDecision.Action.ARCHIVE, reason=reason)
    record_event(actor=actor, action="publication.archived", target=publication, request_id=rid)
    return publication
