from django.urls import path

from . import views

app_name = "statistics"

urlpatterns = [
    path("", views.statistics_dashboard, name="dashboard"),
    path("approved/", views.approved_publication_list, name="approved"),
    path("approved.xlsx", views.approved_xlsx_export, name="approved_xlsx"),
    path("students/", views.student_statistics, name="students"),
    path("students/<uuid:student_id>/", views.student_statistics_detail, name="student_detail"),
    path("students.xlsx", views.student_statistics_xlsx_export, name="students_xlsx"),
    path("students/<uuid:student_id>/export.xlsx", views.student_statistics_detail_xlsx_export, name="student_detail_xlsx"),
    path("export-ready/", views.export_ready_data, name="export_ready"),
    path("export-ready.xlsx", views.export_ready_xlsx_export, name="export_ready_xlsx"),
    path("export.csv", views.csv_export, name="csv_export"),
    path("secretary/journal.csv", views.secretary_journal_export, name="secretary_journal_export"),
    path("secretary/conference.csv", views.secretary_conference_export, name="secretary_conference_export"),
]
