from django.contrib import admin
from django.views.generic import RedirectView
from django.urls import include, path
from accounts import views as account_views
from .views import healthz

admin.site.site_header = "博士班成果管理系統管理後台"
admin.site.site_title = "博士班成果管理後台"
admin.site.index_title = "系統管理"

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", account_views.login_view, name="deployment-login"),
    path("logout/", account_views.logout_view, name="deployment-logout"),
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
