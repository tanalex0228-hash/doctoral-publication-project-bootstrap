from django.contrib import admin
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
    path("", include("documents.urls")),
]
