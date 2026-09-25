from django.contrib import admin
from audit.admin import AuditedAdminMixin

from .models import PublicationIndex, PublicationType, ResearchField


class TaxonomyAdmin(AuditedAdminMixin, admin.ModelAdmin):
    audit_label = "taxonomy"
    list_display = ("display_name", "slug", "is_active", "display_order")
    list_editable = ("is_active", "display_order")
    search_fields = ("display_name", "slug")
    ordering = ("display_order", "display_name")


admin.site.register(PublicationType, TaxonomyAdmin)
admin.site.register(PublicationIndex, TaxonomyAdmin)
admin.site.register(ResearchField, TaxonomyAdmin)
