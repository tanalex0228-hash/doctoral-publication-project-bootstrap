from publications.permissions import is_staff_actor


def project_navigation(request):
    """Expose role-derived navigation without duplicating permission logic in templates."""
    return {"can_access_review": is_staff_actor(request.user)}
