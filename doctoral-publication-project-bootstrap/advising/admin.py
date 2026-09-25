from django.contrib import admin
from .models import StudentAdvisor

@admin.register(StudentAdvisor)
class StudentAdvisorAdmin(admin.ModelAdmin):
    list_display = ("student", "professor", "advisor_role", "is_active", "start_date", "end_date")
    list_filter = ("advisor_role", "is_active")
