from django.urls import path

from . import views

app_name = "statistics"

urlpatterns = [
    path("", views.statistics_dashboard, name="dashboard"),
    path("students/", views.student_statistics, name="students"),
    path("students/<uuid:student_id>/", views.student_statistics_detail, name="student_detail"),
    path("export-ready/", views.export_ready_data, name="export_ready"),
    path("export.csv", views.csv_export, name="csv_export"),
]
