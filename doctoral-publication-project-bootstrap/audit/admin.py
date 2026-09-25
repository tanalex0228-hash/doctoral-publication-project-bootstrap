from django.contrib import admin
from .models import AuditLog

@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ("created_at", "action", "actor", "target_type", "target_id", "request_id")
    readonly_fields = ("id", "actor", "action", "target_type", "target_id", "request_id", "metadata", "created_at")
    search_fields = ("action", "target_id", "request_id")
    list_filter = ("action", "target_type")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in {"GET", "HEAD"}
