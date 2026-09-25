from django.contrib import admin
from audit.admin import AuditedAdminMixin
from .models import Professor

@admin.register(Professor)
class ProfessorAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "professor"
