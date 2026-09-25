import uuid
from django.conf import settings
from django.db import models


class AuditLog(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_events")
    action = models.CharField(max_length=100, db_index=True)
    target_type = models.CharField(max_length=100, db_index=True)
    target_id = models.UUIDField(null=True, blank=True, db_index=True)
    request_id = models.CharField(max_length=128, db_index=True)
    metadata = models.JSONField(default=dict)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        indexes = [models.Index(fields=["target_type", "target_id", "created_at"], name="idx_audit_target_time"), models.Index(fields=["actor", "created_at"], name="idx_audit_actor_time")]
        verbose_name = "稽核紀錄"
        verbose_name_plural = "稽核紀錄"
