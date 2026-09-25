from django.contrib import admin
from .models import PublicationAuthor, PublicationFieldAssignment, PublicationIndexAssignment, PublicationRecord

class PublicationAuthorInline(admin.TabularInline):
    model = PublicationAuthor
    extra = 0

@admin.register(PublicationRecord)
class PublicationRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_student", "publication_type", "workflow_status", "is_published", "visibility_scope", "publication_date")
    list_filter = ("workflow_status", "is_published", "visibility_scope", "publication_type")
    search_fields = ("title", "doi", "journal_or_conference_name", "owner_student__student_number")
    inlines = (PublicationAuthorInline,)
    readonly_fields = ("normalized_title", "normalized_doi", "workflow_status", "is_published", "visibility_scope", "submitted_at", "approved_at", "approved_by")

admin.site.register(PublicationIndexAssignment)
admin.site.register(PublicationFieldAssignment)
