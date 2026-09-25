"""Central read contracts for governed publication state."""

from django.db.models import F

from .models import PublicationRecord


OFFICIAL_WORKFLOW_STATUSES = (
    PublicationRecord.WorkflowStatus.APPROVED,
    PublicationRecord.WorkflowStatus.ARCHIVED,
)


def official_publications():
    """The one authoritative queryset for currently valid official results.

    A historical approval remains official through archival, but a revoked
    approval or a superseded version never appears in this current contract.
    """
    return PublicationRecord.objects.filter(
        series__current_official_version_id=F("pk"),
        approval_revoked_at__isnull=True,
        workflow_status__in=OFFICIAL_WORKFLOW_STATUSES,
    )


def is_official_publication(publication):
    """Object predicate paired with :func:`official_publications`."""
    # Query rather than trusting a potentially stale ``publication.series``
    # relation cached before a concurrent review transaction switched it.
    return bool(publication.series_id) and official_publications().filter(pk=publication.pk).exists()
