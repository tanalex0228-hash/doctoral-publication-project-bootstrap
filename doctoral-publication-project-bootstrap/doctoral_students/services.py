from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from audit.services import record_event
from publications.permissions import is_staff_actor

from .models import DoctoralStudentProfile


@transaction.atomic
def bulk_set_enrollment_status(*, actor, profiles, enrollment_status, request_id=None):
    """Change student enrollment state through one audited, staff-only operation."""
    if not is_staff_actor(actor):
        raise PermissionDenied("僅限授權 staff/admin 變更博士生學籍狀態。")
    valid_statuses = {value for value, _ in DoctoralStudentProfile.EnrollmentStatus.choices}
    if enrollment_status not in valid_statuses:
        raise ValidationError("無效的學籍狀態。")

    updated = 0
    for profile in DoctoralStudentProfile.objects.select_for_update().filter(pk__in=profiles.values("pk")):
        previous = profile.enrollment_status
        if previous == enrollment_status:
            continue
        profile.enrollment_status = enrollment_status
        profile.save(update_fields=("enrollment_status", "updated_at"))
        record_event(
            actor=actor, action="student_profile.enrollment_status_changed", target=profile,
            request_id=request_id, metadata={"previous_status": previous, "enrollment_status": enrollment_status},
        )
        updated += 1
    return updated
