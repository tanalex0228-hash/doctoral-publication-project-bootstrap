from django.contrib import admin
from .models import DoctoralStudentProfile

@admin.register(DoctoralStudentProfile)
class DoctoralStudentProfileAdmin(admin.ModelAdmin):
    list_display = ("student_number", "display_name", "admission_year", "enrollment_status", "primary_field")
    search_fields = ("student_number", "display_name")
    list_filter = ("admission_year", "enrollment_status")
