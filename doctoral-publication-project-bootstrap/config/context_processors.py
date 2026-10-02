from publications.permissions import is_department_member, is_staff_actor


def project_navigation(request):
    """Expose role-derived navigation without duplicating permission logic in templates."""
    return {
        "can_access_review": is_staff_actor(request.user),
        "can_access_department_portal": is_department_member(request.user),
    }
