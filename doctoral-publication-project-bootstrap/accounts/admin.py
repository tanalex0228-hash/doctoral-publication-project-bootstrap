from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from audit.admin import AuditedAdminMixin
from .models import Role, User, UserRole

@admin.register(User)
class AuditedUserAdmin(AuditedAdminMixin, UserAdmin):
    audit_label = "account"
    def has_delete_permission(self, request, obj=None): return False


@admin.register(Role)
class RoleAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "role"


@admin.register(UserRole)
class UserRoleAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "user_role"
    list_display = ("user", "role")
