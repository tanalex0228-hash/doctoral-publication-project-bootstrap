from django.contrib import admin

from publications.permissions import is_department_member, is_staff_actor


def can_access_django_admin(request):
    """Match the admin index's real module-level access, not ``is_staff`` alone."""
    if not admin.site.has_permission(request):
        return False
    return any(model_admin.has_module_permission(request) for model_admin in admin.site._registry.values())


def project_navigation(request):
    """Expose role-derived navigation without duplicating permission logic in templates."""
    return {
        "can_access_review": is_staff_actor(request.user),
        "can_access_department_portal": is_department_member(request.user),
        "can_access_admin": can_access_django_admin(request),
    }
