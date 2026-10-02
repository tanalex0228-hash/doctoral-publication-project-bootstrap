from django import forms
from django.contrib import admin, messages
from django.contrib.admin.helpers import ActionForm
from django.core.exceptions import PermissionDenied, ValidationError
from audit.admin import AuditedAdminMixin
from .models import DoctoralStudentProfile
from .services import bulk_set_enrollment_status
from publications.permissions import is_staff_actor


class EnrollmentStatusActionForm(ActionForm):
    enrollment_status = forms.ChoiceField(
        label="批量設定學籍狀態為",
        choices=(("", "請選擇學籍狀態"), *DoctoralStudentProfile.EnrollmentStatus.choices),
        required=False,
    )

@admin.register(DoctoralStudentProfile)
class DoctoralStudentProfileAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "student_profile"
    list_display = ("student_number", "display_name", "admission_year", "enrollment_status", "primary_field")
    search_fields = ("student_number", "display_name")
    list_filter = ("admission_year", "enrollment_status")
    action_form = EnrollmentStatusActionForm
    actions = ("set_selected_enrollment_status",)

    def get_actions(self, request):
        actions = super().get_actions(request)
        if not is_staff_actor(request.user):
            actions.pop("set_selected_enrollment_status", None)
        return actions

    @admin.action(description="批量設定選取博士生的學籍狀態")
    def set_selected_enrollment_status(self, request, queryset):
        enrollment_status = request.POST.get("enrollment_status")
        if not enrollment_status:
            self.message_user(request, "請先選擇學籍狀態。", messages.ERROR)
            return
        try:
            updated = bulk_set_enrollment_status(
                actor=request.user, profiles=queryset, enrollment_status=enrollment_status,
            )
        except PermissionDenied:
            raise
        except ValidationError as exc:
            self.message_user(request, "; ".join(exc.messages), messages.ERROR)
            return
        self.message_user(request, f"已更新 {updated} 位博士生的學籍狀態。", messages.SUCCESS)
