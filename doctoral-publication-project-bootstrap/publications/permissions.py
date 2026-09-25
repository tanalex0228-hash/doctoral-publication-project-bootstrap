"""Central object-permission policy for governed publication resources."""

from django.db.models import Q

from doctoral_students.models import DoctoralStudentProfile
from professors.models import Professor

from .models import PublicationRecord
from .querysets import is_official_publication, official_publications


def is_staff_actor(user):
    return bool(user and user.is_authenticated and user.has_project_role("staff", "admin"))


def is_advisor_actor(user):
    return bool(user and user.is_authenticated and user.has_project_role("advisor"))


def _student_profile(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.doctoral_profile
    except DoctoralStudentProfile.DoesNotExist:
        return None


def _professor_profile(user):
    if not user or not user.is_authenticated:
        return None
    try:
        return user.professor_profile
    except Professor.DoesNotExist:
        return None


def is_current_student(user):
    profile = _student_profile(user)
    return bool(profile and profile.enrollment_status == profile.EnrollmentStatus.ACTIVE)


def is_graduated_student(user):
    profile = _student_profile(user)
    return bool(profile and profile.enrollment_status == profile.EnrollmentStatus.GRADUATED)


def is_faculty_actor(user):
    professor = _professor_profile(user)
    return bool(professor and professor.status == professor.Status.ACTIVE)


def is_department_all_member(user):
    return bool(is_staff_actor(user) or is_faculty_actor(user) or is_current_student(user) or is_graduated_student(user))


def is_department_current_member(user):
    return bool(is_staff_actor(user) or is_faculty_actor(user) or is_current_student(user))


def is_department_member(user):
    """Portal-entry compatibility helper; record-level scope remains explicit."""
    return is_department_all_member(user)


def is_active_advisor(user, student):
    """Return relationship-based access; end_date is historical metadata only."""
    professor = _professor_profile(user)
    return bool(
        is_advisor_actor(user)
        and professor
        and professor.status == professor.Status.ACTIVE
        and user.is_active
        and student.advisor_relations.filter(professor=professor, is_active=True).exists()
    )


def can_view_publication(user, publication):
    """Apply the single official-version and visibility contract to one record."""
    if is_staff_actor(user):
        return True
    if user and user.is_authenticated and publication.owner_student.user_id == user.id:
        return True
    # Advisors may inspect an ordinary owner_advisor working record, but an
    # explicit revision is never externally visible before it becomes current.
    if (
        not publication.is_revision
        and publication.visibility_scope == PublicationRecord.VisibilityScope.OWNER_ADVISOR
        and is_active_advisor(user, publication.owner_student)
    ):
        return True
    if not is_official_publication(publication):
        return False

    scope = publication.visibility_scope
    if scope == PublicationRecord.VisibilityScope.PUBLIC:
        return bool(publication.is_published)
    if scope == PublicationRecord.VisibilityScope.DEPARTMENT_ALL:
        return bool(publication.is_published and is_department_all_member(user))
    if scope == PublicationRecord.VisibilityScope.DEPARTMENT_CURRENT:
        return bool(publication.is_published and is_department_current_member(user))
    if scope == PublicationRecord.VisibilityScope.OWNER_FACULTY:
        return is_faculty_actor(user)
    if scope == PublicationRecord.VisibilityScope.OWNER_ADVISOR:
        return is_active_advisor(user, publication.owner_student)
    return False  # staff_only and unknown states


def can_edit_publication(user, publication):
    return is_staff_actor(user) or bool(
        user
        and user.is_authenticated
        and publication.owner_student.user_id == user.id
        and publication.workflow_status in {
            PublicationRecord.WorkflowStatus.DRAFT,
            PublicationRecord.WorkflowStatus.RETURNED,
        }
    )


def can_review_publication(user, publication=None):
    return is_staff_actor(user)


def can_download_document(user, document):
    """Evidence is private and can never be broader than its parent record."""
    if not document.is_active or not user or not user.is_authenticated:
        return False
    publication = document.publication
    if not can_view_publication(user, publication):
        return False
    return bool(
        is_staff_actor(user)
        or publication.owner_student.user_id == user.id
        or is_active_advisor(user, publication.owner_student)
    )


def visible_publications_for(user, *, include_staff_scope=True):
    """One queryset contract for all official-record discovery surfaces."""
    if include_staff_scope and is_staff_actor(user):
        return PublicationRecord.objects.all()

    official = Q(pk__in=official_publications())
    public = official & Q(
        is_published=True,
        visibility_scope=PublicationRecord.VisibilityScope.PUBLIC,
    )
    if not user or not user.is_authenticated:
        return PublicationRecord.objects.filter(public)

    scope = public | Q(owner_student__user=user)
    if is_department_all_member(user):
        scope |= official & Q(
            is_published=True,
            visibility_scope=PublicationRecord.VisibilityScope.DEPARTMENT_ALL,
        )
    if is_department_current_member(user):
        scope |= official & Q(
            is_published=True,
            visibility_scope=PublicationRecord.VisibilityScope.DEPARTMENT_CURRENT,
        )
    if is_faculty_actor(user):
        scope |= official & Q(visibility_scope=PublicationRecord.VisibilityScope.OWNER_FACULTY)
    professor = _professor_profile(user)
    if is_advisor_actor(user) and professor and professor.status == professor.Status.ACTIVE and user.is_active:
        scope |= Q(
            is_revision=False,
            visibility_scope=PublicationRecord.VisibilityScope.OWNER_ADVISOR,
            owner_student__advisor_relations__professor=professor,
            owner_student__advisor_relations__is_active=True,
        )
    return PublicationRecord.objects.filter(scope).distinct()


def public_portal_publications():
    """Only current, active official versions belong to the public surface."""
    return official_publications().filter(
        workflow_status=PublicationRecord.WorkflowStatus.APPROVED,
        is_published=True,
        visibility_scope=PublicationRecord.VisibilityScope.PUBLIC,
    )


def department_portal_publications_for(user):
    """Published official records that the caller may see in department surfaces."""
    if not (is_department_all_member(user) or is_department_current_member(user)):
        return PublicationRecord.objects.none()
    records = visible_publications_for(user).filter(
        workflow_status=PublicationRecord.WorkflowStatus.APPROVED,
        is_published=True,
    )
    if not is_staff_actor(user):
        records = records.exclude(visibility_scope=PublicationRecord.VisibilityScope.STAFF_ONLY)
    return records.distinct()
