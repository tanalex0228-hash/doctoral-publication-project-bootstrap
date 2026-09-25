from django.db.models import Q
from .models import PublicationRecord


def is_staff_actor(user):
    return bool(user and user.is_authenticated and user.has_project_role("staff", "admin"))


def is_advisor_actor(user):
    return bool(user and user.is_authenticated and user.has_project_role("advisor"))


def is_department_member(user):
    return bool(user and user.is_authenticated and user.has_project_role("student", "advisor", "staff", "admin"))


def is_active_advisor(user, student):
    return bool(is_advisor_actor(user) and hasattr(user, "professor_profile") and
        student.advisor_relations.filter(professor=user.professor_profile, is_active=True).exists())


def can_view_publication(user, publication):
    if is_staff_actor(user): return True
    if user and user.is_authenticated and publication.owner_student.user_id == user.id: return True
    if publication.workflow_status == PublicationRecord.WorkflowStatus.APPROVED and publication.is_published:
        if publication.visibility_scope == PublicationRecord.VisibilityScope.PUBLIC: return True
        if publication.visibility_scope == PublicationRecord.VisibilityScope.DEPARTMENT: return is_department_member(user)
    return publication.visibility_scope == PublicationRecord.VisibilityScope.OWNER_ADVISOR and is_active_advisor(user, publication.owner_student)


def can_edit_publication(user, publication):
    return is_staff_actor(user) or bool(user and user.is_authenticated and publication.owner_student.user_id == user.id and publication.workflow_status in {PublicationRecord.WorkflowStatus.DRAFT, PublicationRecord.WorkflowStatus.RETURNED})


def can_review_publication(user, publication=None): return is_staff_actor(user)


def can_download_document(user, document):
    """Evidence remains private even when its parent metadata is public."""
    if not user or not user.is_authenticated:
        return False
    publication = document.publication
    return bool(
        is_staff_actor(user)
        or publication.owner_student.user_id == user.id
        or is_active_advisor(user, publication.owner_student)
    )


def visible_publications_for(user, *, include_staff_scope=True):
    """Return the records visible in the requested role context.

    The default retains the staff/admin global view used by staff workflows.
    Advisor-facing routes pass ``include_staff_scope=False`` so a multi-role
    account is still constrained to the advisor visibility contract there.
    """
    public = Q(workflow_status=PublicationRecord.WorkflowStatus.APPROVED, is_published=True, visibility_scope=PublicationRecord.VisibilityScope.PUBLIC)
    if include_staff_scope and is_staff_actor(user): return PublicationRecord.objects.all()
    if not user or not user.is_authenticated: return PublicationRecord.objects.filter(public)
    scope = public | Q(owner_student__user=user)
    if is_department_member(user): scope |= Q(workflow_status=PublicationRecord.WorkflowStatus.APPROVED, is_published=True, visibility_scope=PublicationRecord.VisibilityScope.DEPARTMENT)
    if is_advisor_actor(user) and hasattr(user, "professor_profile"):
        scope |= Q(visibility_scope=PublicationRecord.VisibilityScope.OWNER_ADVISOR, owner_student__advisor_relations__professor=user.professor_profile, owner_student__advisor_relations__is_active=True)
    return PublicationRecord.objects.filter(scope).distinct()


def public_portal_publications():
    """Public metadata requires all three independent publication gates."""
    return visible_publications_for(None)


def department_portal_publications_for(user):
    """The department portal retains object permissions, but only for published metadata."""
    if not is_department_member(user):
        return PublicationRecord.objects.none()
    records = visible_publications_for(user).filter(
        workflow_status=PublicationRecord.WorkflowStatus.APPROVED,
        is_published=True,
    )
    # A student's internal owner view is broader than the department portal;
    # staff-only records remain reserved for staff/admin in this surface.
    if not is_staff_actor(user):
        records = records.exclude(visibility_scope=PublicationRecord.VisibilityScope.STAFF_ONLY)
    return records.distinct()
