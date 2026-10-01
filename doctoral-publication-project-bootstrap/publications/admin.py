from django.contrib import admin
from .models import (
    ConferenceDetail, ConferenceParticipantCountry, ConferencePresentationMode,
    ConferencePresentationModeAssignment, Country, JournalArticleDetail,
    PublicationAuthor, PublicationFieldAssignment, PublicationIndexAssignment,
    PublicationRecord, PublicationSDGAssignment, SustainableDevelopmentGoal,
)

class PublicationAuthorInline(admin.TabularInline):
    model = PublicationAuthor
    extra = 0


class JournalArticleDetailInline(admin.StackedInline):
    model = JournalArticleDetail
    extra = 0
    max_num = 1


class ConferenceDetailInline(admin.StackedInline):
    model = ConferenceDetail
    extra = 0
    max_num = 1

@admin.register(PublicationRecord)
class PublicationRecordAdmin(admin.ModelAdmin):
    list_display = ("title", "owner_student", "publication_type", "workflow_status", "is_published", "visibility_scope", "publication_date")
    list_filter = ("workflow_status", "is_published", "visibility_scope", "publication_type")
    search_fields = ("title", "doi", "journal_or_conference_name", "owner_student__student_number")
    inlines = (PublicationAuthorInline, JournalArticleDetailInline, ConferenceDetailInline)
    readonly_fields = ("normalized_title", "normalized_doi", "workflow_status", "is_published", "visibility_scope", "submitted_at", "approved_at", "approved_by")

admin.site.register(PublicationIndexAssignment)
admin.site.register(PublicationFieldAssignment)
admin.site.register(PublicationSDGAssignment)
admin.site.register(Country)
admin.site.register(SustainableDevelopmentGoal)
admin.site.register(ConferencePresentationMode)
admin.site.register(ConferenceDetail)
admin.site.register(ConferenceParticipantCountry)
admin.site.register(ConferencePresentationModeAssignment)
