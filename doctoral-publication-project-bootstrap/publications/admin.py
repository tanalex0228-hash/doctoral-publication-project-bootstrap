from django.contrib import admin
from django.core.exceptions import PermissionDenied, ValidationError
from .models import (
    ConferenceDetail, ConferenceParticipantCountry, ConferencePresentationMode,
    ConferencePresentationModeAssignment, Country, JournalArticleDetail,
    PublicationAuthor, PublicationFieldAssignment, PublicationIndexAssignment,
    PublicationRecord, PublicationSDGAssignment, SustainableDevelopmentGoal,
)
from .services import set_published, set_visibility
from review.services import approve_publication, archive_publication, restore_publication, return_for_revision

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
    actions = ("approve_selected", "return_selected", "archive_selected", "publish_public_selected")

    def has_delete_permission(self, request, obj=None):
        """Records are governed through the review/archive workflow, never hard-deleted."""
        return False

    def _run_workflow_action(self, request, queryset, service, *, success, **kwargs):
        completed = 0
        failures = []
        for publication in queryset:
            try:
                service(actor=request.user, publication_id=publication.id, **kwargs)
            except (PermissionDenied, ValidationError) as error:
                failures.append(f"{publication.title}: {error}")
            else:
                completed += 1
        if completed:
            self.message_user(request, success.format(count=completed), level="SUCCESS")
        if failures:
            self.message_user(request, "；".join(failures), level="ERROR")

    @admin.action(description="核准選取成果")
    def approve_selected(self, request, queryset):
        self._run_workflow_action(request, queryset, approve_publication, success="已核准 {count} 筆成果。")

    @admin.action(description="退回選取成果（原因：管理後台退回）")
    def return_selected(self, request, queryset):
        self._run_workflow_action(request, queryset, return_for_revision, reason="管理後台退回", success="已退回 {count} 筆成果。")

    @admin.action(description="封存選取的已核准成果")
    def archive_selected(self, request, queryset):
        self._run_workflow_action(request, queryset, archive_publication, success="已封存 {count} 筆成果。")

    @admin.action(description="設為公開並在平台發佈（限已核准成果）")
    def publish_public_selected(self, request, queryset):
        completed = 0
        failures = []
        for publication in queryset:
            try:
                if publication.workflow_status == PublicationRecord.WorkflowStatus.ARCHIVED:
                    publication = restore_publication(actor=request.user, publication_id=publication.id)
                set_visibility(actor=request.user, publication_id=publication.id, visibility_scope=PublicationRecord.VisibilityScope.PUBLIC)
                set_published(actor=request.user, publication_id=publication.id, is_published=True)
            except (PermissionDenied, ValidationError) as error:
                failures.append(f"{publication.title}: {error}")
            else:
                completed += 1
        if completed:
            self.message_user(request, f"已公開並發佈 {completed} 筆成果。", level="SUCCESS")
        if failures:
            self.message_user(request, "；".join(failures), level="ERROR")

admin.site.register(PublicationIndexAssignment)
admin.site.register(PublicationFieldAssignment)
admin.site.register(PublicationSDGAssignment)
admin.site.register(Country)
admin.site.register(SustainableDevelopmentGoal)
admin.site.register(ConferencePresentationMode)
admin.site.register(ConferenceDetail)
admin.site.register(ConferenceParticipantCountry)
admin.site.register(ConferencePresentationModeAssignment)
