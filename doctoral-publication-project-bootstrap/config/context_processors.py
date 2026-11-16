from django.contrib import admin

from accounts.models import SiteConfiguration
from publications.permissions import is_department_member, is_staff_actor


def can_access_django_admin(request):
    """Match the admin index's real module-level access, not ``is_staff`` alone."""
    if not admin.site.has_permission(request):
        return False
    return any(model_admin.has_module_permission(request) for model_admin in admin.site._registry.values())


def project_navigation(request):
    """Expose role-derived navigation without duplicating permission logic in templates."""
    site_configuration = SiteConfiguration.objects.filter(pk=1).only("support_email").first()
    return {
        "can_access_review": is_staff_actor(request.user),
        "can_access_department_portal": is_department_member(request.user),
        "can_access_admin": can_access_django_admin(request),
        "support_contact_email": site_configuration.support_email if site_configuration else "",
        "can_edit_support_email": bool(request.user.is_authenticated and request.user.is_superuser),
    }
