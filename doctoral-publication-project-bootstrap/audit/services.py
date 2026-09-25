import uuid
from .models import AuditLog


def record_event(*, actor, action, target, request_id=None, metadata=None):
    """Append an audit event; callers must never place secrets or file bytes in metadata."""
    return AuditLog.objects.create(actor=actor, action=action, target_type=target._meta.label_lower,
        target_id=target.pk, request_id=request_id or str(uuid.uuid4()), metadata=metadata or {})
