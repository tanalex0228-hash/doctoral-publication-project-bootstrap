from django.contrib import admin
from .models import SourceDocument

@admin.register(SourceDocument)
class SourceDocumentAdmin(admin.ModelAdmin):
    list_display = ("original_filename", "publication", "document_type", "file_size", "uploaded_by", "uploaded_at", "is_active")
    readonly_fields = ("publication", "document_type", "original_filename", "storage_key", "mime_type", "file_size", "checksum_sha256", "uploaded_by", "uploaded_at", "is_active", "supersedes")
    search_fields = ("original_filename", "checksum_sha256")
    list_filter = ("document_type", "is_active", "mime_type")
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return request.method in {"GET", "HEAD"}
    def has_delete_permission(self, request, obj=None): return False
