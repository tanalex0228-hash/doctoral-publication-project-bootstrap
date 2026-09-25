from django.contrib import admin
from .services import record_event
from .models import AuditLog


class AuditedAdminMixin:
    """Boundary audit for governed administrative changes."""
    audit_label = None

    def _audit_action(self, suffix):
        return f"{self.audit_label or self.model._meta.model_name}.{suffix}"

    def save_model(self, request, obj, form, change):
        super().save_model(request, obj, form, change)
        record_event(
            actor=request.user,
            action=self._audit_action("updated" if change else "created"),
            target=obj,
            metadata={"changed_fields": sorted(form.changed_data)} if change else {},
        )

    def delete_model(self, request, obj):
        record_event(actor=request.user, action=self._audit_action("removed"), target=obj)
        super().delete_model(request, obj)

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "target_type", "target_id", "request_id")
    readonly_fields = ("id", "actor", "action", "target_type", "target_id", "request_id", "metadata", "created_at")
    search_fields = ("action", "target_id", "request_id")
    list_filter = ("action", "target_type")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in {"GET", "HEAD"}
    def has_delete_permission(self, request, obj=None): return False
