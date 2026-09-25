from django.contrib import admin
from .models import PublicationTransition, ReviewDecision

@admin.register(PublicationTransition)
class PublicationTransitionAdmin(admin.ModelAdmin):
    list_display = ("publication", "from_status", "to_status", "actor", "created_at")
    readonly_fields = ("publication", "from_status", "to_status", "actor", "reason", "request_id", "created_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in {"GET", "HEAD"}

@admin.register(ReviewDecision)
class ReviewDecisionAdmin(admin.ModelAdmin):
    list_display = ("publication", "action", "reviewer", "created_at")
    readonly_fields = ("publication", "action", "reviewer", "reason", "visibility_after", "created_at")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in {"GET", "HEAD"}
