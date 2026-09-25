from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path
from .views import healthz

urlpatterns = [
    path("admin/", admin.site.urls),
    path("accounts/", include("accounts.urls")),
    path("healthz", healthz, name="healthz"),
    path("dashboard/", include("dashboard.urls")),
    path("publications/", include("public_site.urls")),
    path("publications/", include("publications.urls")),
    path("review/", include("review.urls")),
    path("statistics/", include("reporting.urls")),
    path("", RedirectView.as_view(pattern_name="public_site:publication_list", permanent=False)),
    path("", include("documents.urls")),
]
