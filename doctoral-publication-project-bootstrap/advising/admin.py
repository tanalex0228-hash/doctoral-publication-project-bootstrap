from django.contrib import admin
from audit.admin import AuditedAdminMixin
from .models import StudentAdvisor

@admin.register(StudentAdvisor)
class StudentAdvisorAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "student_advisor"
    list_display = ("student", "professor", "advisor_role", "is_active", "start_date", "end_date")
    list_filter = ("advisor_role", "is_active")
