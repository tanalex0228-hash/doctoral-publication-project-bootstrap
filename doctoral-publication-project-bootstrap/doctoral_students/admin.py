from django.contrib import admin
from audit.admin import AuditedAdminMixin
from .models import DoctoralStudentProfile

@admin.register(DoctoralStudentProfile)
class DoctoralStudentProfileAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "student_profile"
    list_display = ("student_number", "display_name", "admission_year", "enrollment_status", "primary_field")
    search_fields = ("student_number", "display_name")
    list_filter = ("admission_year", "enrollment_status")
