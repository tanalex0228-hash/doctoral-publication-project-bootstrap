import uuid
from django.conf import settings
from django.db import models
from django.db.models import F, Q


class PublicationTransition(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey("publications.PublicationRecord", on_delete=models.PROTECT, related_name="transitions")
    from_status = models.CharField(max_length=16, db_index=True)
    to_status = models.CharField(max_length=16, db_index=True)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="publication_transitions")
    reason = models.TextField(blank=True)
    request_id = models.CharField(max_length=128, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        constraints = [models.CheckConstraint(condition=~Q(from_status=F("to_status")), name="ck_status_change")]
        indexes = [models.Index(fields=["publication", "created_at"], name="idx_pub_created")]


class ReviewDecision(models.Model):
    class Action(models.TextChoices):
        APPROVE = "approve", "核准"
        RETURN = "return", "退回"
        ARCHIVE = "archive", "封存"
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    publication = models.ForeignKey("publications.PublicationRecord", on_delete=models.PROTECT, related_name="review_decisions")
    action = models.CharField(max_length=16, choices=Action.choices, db_index=True)
    reviewer = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="review_decisions")
    reason = models.TextField(blank=True)
    visibility_after = models.CharField(max_length=16, null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    class Meta:
        indexes = [models.Index(fields=["publication", "created_at"], name="idx_review_pub_time")]
